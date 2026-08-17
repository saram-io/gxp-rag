"""Pydantic AI tools and dependencies for GxP Document Drafting."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pydantic_ai import RunContext

from gxp_rag.hitl.approval_workflow import ApprovalWorkflowManager
from gxp_rag.hitl.audit_logger import AuditLogger
from gxp_rag.rag.qdrant_store import QdrantStore
from gxp_rag.schemas.audit import AuditEventType, UserRole


@dataclass
class GxPAgentDeps:
    """Dependency injection container for the Pydantic AI GxP Agent."""
    qdrant_store: QdrantStore
    approval_manager: ApprovalWorkflowManager
    audit_logger: AuditLogger
    user_id: str = "qa_user_01"
    user_role: UserRole = UserRole.AUTHOR
    target_doc_type: Optional[str] = "SOP"
    target_department: Optional[str] = "Quality Assurance"
    session_id: Optional[str] = None


def search_gxp_knowledge_base_impl(
    ctx: RunContext[GxPAgentDeps],
    query: str,
    doc_types: Optional[List[str]] = None,
    department: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Search Qdrant knowledge base for relevant SOPs, deviations, validations, or guidelines."""
    # Log query event in audit trail
    ctx.deps.audit_logger.log_event(
        event_type=AuditEventType.KB_QUERY,
        user_id=ctx.deps.user_id,
        user_role=ctx.deps.user_role,
        action_details={"query": query, "doc_types": doc_types, "limit": limit},
    )

    results = ctx.deps.qdrant_store.search(
        query=query,
        limit=limit,
        doc_types=doc_types,
        department=department,
    )

    if not results:
        return f"No relevant GxP documents found in Qdrant for query: '{query}'."

    output_lines = [f"Found {len(results)} relevant GxP context sources:"]
    for i, r in enumerate(results, 1):
        output_lines.append(
            f"--- Source #{i} [Doc ID: {r.doc_id}] ({r.doc_type}) ---"
        )
        output_lines.append(f"Title: {r.doc_title}")
        output_lines.append(f"Section: {r.section_heading or 'N/A'}")
        output_lines.append(f"Relevance Score: {r.score:.4f}")
        output_lines.append(f"Excerpt Content:\n{r.text}")
        output_lines.append("")

    return "\n".join(output_lines)


def retrieve_document_details_impl(
    ctx: RunContext[GxPAgentDeps],
    doc_id: str,
) -> str:
    """Retrieve all indexed chunks and full context for a specific document ID."""
    chunks = ctx.deps.qdrant_store.get_document_chunks(doc_id)
    if not chunks:
        return f"Document ID '{doc_id}' was not found in the Qdrant knowledge base."

    output_lines = [f"Document '{doc_id}' contains {len(chunks)} sections:"]
    for c in chunks:
        output_lines.append(f"### Chunk {c.get('chunk_index', 0)+1}: {c.get('section_heading', 'Section')}")
        output_lines.append(c.get("text", ""))
        output_lines.append("")
    return "\n".join(output_lines)


def validate_gxp_structure_impl(
    ctx: RunContext[GxPAgentDeps],
    doc_id: str,
    title: str,
    purpose: str,
    scope: str,
    critical_parameters_included: bool = True,
    alcoa_attributable_clear: bool = True,
) -> str:
    """Validate that drafted document meets mandatory GxP structural and regulatory checklist."""
    issues = []
    if not doc_id:
        issues.append("Missing formal Document ID (e.g. SOP-MFG-XXX).")
    if len(purpose) < 20:
        issues.append("Purpose section is too brief or insufficiently defined.")
    if len(scope) < 20:
        issues.append("Scope section is too brief or lacks clear facility/system boundaries.")
    if not critical_parameters_included:
        issues.append("Critical Process Parameters (CPPs) must be explicitly listed with tolerances.")
    if not alcoa_attributable_clear:
        issues.append("Every step must designate an authorized role for ALCOA+ Attributability.")

    if issues:
        return f"GxP Structure Check: ISSUES DETECTED ({len(issues)} items):\n" + "\n".join(f"- {iss}" for iss in issues)
    return "GxP Structure Check: PASSED. All core GxP sections and ALCOA+ requirements are satisfied."
