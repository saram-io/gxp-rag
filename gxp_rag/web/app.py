"""FastAPI Web Application for GxP Document Draft Agent."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from gxp_rag.agent.gxp_agent import GxPDraftingService
from gxp_rag.config import settings
from gxp_rag.hitl.approval_workflow import ApprovalWorkflowManager
from gxp_rag.hitl.audit_logger import AuditLogger
from gxp_rag.models.provider_factory import ModelProviderFactory
from gxp_rag.rag.qdrant_store import QdrantStore
from gxp_rag.schemas.audit import AuditEventType, UserRole
from gxp_rag.schemas.document import DocumentType, GxPDocumentDraft

# Setup web paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="GxP Document Draft Agent",
    description="AI GxP Document Drafting System with Pydantic AI, Qdrant RAG, and 21 CFR Part 11 HITL Approval",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Singleton Services
settings.ensure_directories()
audit_logger = AuditLogger()
approval_manager = ApprovalWorkflowManager(audit_logger=audit_logger)
qdrant_store = QdrantStore()
drafting_service = GxPDraftingService(
    qdrant_store=qdrant_store,
    approval_manager=approval_manager,
    audit_logger=audit_logger,
)


# Request Models
class DraftRequest(BaseModel):
    prompt: str
    doc_type: DocumentType = DocumentType.SOP
    department: str = "Quality Assurance"
    user_id: str = "author_01"
    user_role: UserRole = UserRole.AUTHOR
    model_spec: Optional[str] = None
    auto_request_approval: bool = False
    approval_justification: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    doc_types: Optional[List[str]] = None
    department: Optional[str] = None


class ApprovalActionRequest(BaseModel):
    request_id: str
    action: str  # "approve", "reject", "revise"
    signer_name: str
    user_id: str
    role: UserRole
    comments_or_reason: str
    signature_meaning: Optional[str] = None


class CreateApprovalRequestModel(BaseModel):
    doc_id: str
    justification: str
    author_id: str = "drafter_user"


@app.get("/api/langfuse/status")
async def get_langfuse_status():
    """Retrieve Langfuse observability status and configuration."""
    from gxp_rag.observability.langfuse_tracker import langfuse_tracker
    return {
        "enabled": settings.enable_langfuse,
        "host": settings.langfuse_host,
        "is_connected": langfuse_tracker.is_connected(),
        "public_key_configured": bool(settings.langfuse_public_key),
    }


# Routes
@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Render main application dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/presets")
async def get_presets():
    """List available LLM provider presets."""
    return {
        "default_model": settings.default_model,
        "presets": ModelProviderFactory.list_available_presets(),
    }


@app.get("/api/stats")
async def get_system_stats():
    """Retrieve global system telemetry and collection stats."""
    qdrant_stats = qdrant_store.get_stats()
    approvals = approval_manager.list_approvals()
    pending_count = sum(1 for a in approvals if a.status.value == "PENDING")
    drafts = approval_manager.list_drafts()
    audit_records = audit_logger.get_records(limit=1)

    return {
        "qdrant": qdrant_stats,
        "total_drafts": len(drafts),
        "pending_approvals": pending_count,
        "total_approvals": len(approvals),
        "has_audit_records": len(audit_records) > 0,
    }


@app.get("/api/documents")
async def list_kb_documents():
    """List all indexed GxP documents in Qdrant."""
    docs = qdrant_store.list_documents()
    return {"documents": docs}


@app.get("/api/documents/{doc_id}/chunks")
async def get_document_chunks(doc_id: str):
    """Retrieve indexed chunks for a document."""
    chunks = qdrant_store.get_document_chunks(doc_id)
    return {"doc_id": doc_id, "chunks": chunks}


@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
):
    """Upload and ingest a document into the Qdrant knowledge base."""
    # Save uploaded file to temp file
    suffix = Path(file.filename or "doc.txt").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        from gxp_rag.rag.parser import GxPDocumentParser
        parsed = GxPDocumentParser.parse_file(tmp_path)
        if doc_type:
            try:
                parsed.doc_type = DocumentType(doc_type)
            except Exception:
                pass
        if department:
            parsed.department = department

        chunks_count = qdrant_store.ingest_document(parsed)

        # Audit log ingestion
        audit_logger.log_event(
            event_type=AuditEventType.KB_INGESTION,
            user_id="qa_user",
            user_role=UserRole.QA_SPECIALIST,
            doc_id=parsed.doc_id,
            action_details={
                "filename": file.filename,
                "chunks_indexed": chunks_count,
                "doc_type": parsed.doc_type.value,
                "title": parsed.title,
            },
        )

        return {
            "success": True,
            "doc_id": parsed.doc_id,
            "title": parsed.title,
            "doc_type": parsed.doc_type.value,
            "department": parsed.department,
            "chunks_count": chunks_count,
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.post("/api/documents/delete")
async def delete_kb_document(payload: Dict[str, str]):
    """Delete a document from Qdrant."""
    doc_id = payload.get("doc_id")
    if not doc_id:
        raise HTTPException(status_code=400, detail="Missing doc_id")
    success = qdrant_store.delete_document(doc_id)
    return {"success": success, "doc_id": doc_id}


@app.post("/api/search")
async def search_kb(req: SearchRequest):
    """Search Qdrant knowledge base."""
    results = qdrant_store.search(
        query=req.query,
        limit=req.limit,
        doc_types=req.doc_types,
        department=req.department,
    )
    return {"query": req.query, "results": [r.model_dump() for r in results]}


@app.post("/api/draft")
async def generate_draft(req: DraftRequest):
    """Draft a new GxP document using Pydantic AI agent and Qdrant RAG."""
    try:
        draft = await drafting_service.draft_document(
            prompt=req.prompt,
            doc_type=req.doc_type,
            department=req.department,
            user_id=req.user_id,
            user_role=req.user_role,
            model_spec=req.model_spec,
            auto_request_approval=req.auto_request_approval,
            approval_justification=req.approval_justification,
        )

        compliance = drafting_service.evaluate_compliance(draft)

        return {
            "success": True,
            "draft": draft.model_dump(),
            "markdown": draft.to_markdown(),
            "compliance": compliance.model_dump(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compliance/check")
async def check_compliance(draft: GxPDocumentDraft):
    """Run automated compliance evaluation on a draft."""
    report = drafting_service.evaluate_compliance(draft)
    return report.model_dump()


@app.get("/api/drafts")
async def list_drafts():
    """List all saved drafts."""
    drafts = approval_manager.list_drafts()
    return {"drafts": [d.model_dump() for d in drafts]}


@app.get("/api/drafts/{doc_id}")
async def get_draft_details(doc_id: str):
    """Get single draft by doc_id."""
    draft = approval_manager.get_draft(doc_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    compliance = drafting_service.evaluate_compliance(draft)
    return {
        "draft": draft.model_dump(),
        "markdown": draft.to_markdown(),
        "compliance": compliance.model_dump(),
    }


@app.get("/api/approvals")
async def list_approvals(status: Optional[str] = None):
    """List approval requests."""
    status_enum = None
    if status:
        try:
            from gxp_rag.schemas.audit import ApprovalStatus
            status_enum = ApprovalStatus(status.upper())
        except Exception:
            pass
    approvals = approval_manager.list_approvals(status=status_enum)
    return {"approvals": [a.model_dump() for a in approvals]}


@app.post("/api/approvals/create")
async def create_approval(payload: CreateApprovalRequestModel):
    """Create a new Human-in-the-Loop approval request."""
    draft = approval_manager.get_draft(payload.doc_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    req = approval_manager.create_approval_request(
        draft=draft,
        justification=payload.justification,
        author_id=payload.author_id,
    )
    return {"success": True, "approval_request": req.model_dump()}


@app.post("/api/approvals/action")
async def perform_approval_action(req: ApprovalActionRequest):
    """Execute approval, rejection, or revision request with 21 CFR Part 11 signature."""
    try:
        if req.action == "approve":
            meaning = (
                req.signature_meaning
                or "I approve this GxP document for technical accuracy and regulatory compliance."
            )
            updated = approval_manager.approve(
                request_id=req.request_id,
                signer_name=req.signer_name,
                user_id=req.user_id,
                signer_role=req.role,
                comments=req.comments_or_reason,
                meaning=meaning,
            )
        elif req.action == "reject":
            updated = approval_manager.reject(
                request_id=req.request_id,
                reviewer_name=req.signer_name,
                user_id=req.user_id,
                reviewer_role=req.role,
                reason=req.comments_or_reason,
            )
        elif req.action == "revise":
            updated = approval_manager.request_revision(
                request_id=req.request_id,
                reviewer_name=req.signer_name,
                user_id=req.user_id,
                reviewer_role=req.role,
                revision_feedback=req.comments_or_reason,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {req.action}")

        return {"success": True, "approval_request": updated.model_dump()}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit")
async def get_audit_trail(doc_id: Optional[str] = None):
    """Retrieve audit trail records and verify cryptographic chain integrity."""
    records = audit_logger.get_records(doc_id=doc_id, limit=200)
    integrity = audit_logger.verify_integrity()
    return {
        "integrity": integrity,
        "records": [r.model_dump() for r in records],
    }


@app.post("/api/seed-sample-data")
async def seed_sample_data():
    """Ingest sample GxP data directory into Qdrant."""
    sample_dir = Path("./sample_data")
    if not sample_dir.exists():
        raise HTTPException(status_code=404, detail="sample_data directory not found")
    results = qdrant_store.ingest_directory(sample_dir)
    return {"success": True, "ingested_files": results}
