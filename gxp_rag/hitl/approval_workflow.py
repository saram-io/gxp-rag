"""Human-in-the-Loop (HITL) approval workflow manager for GxP document lifecycle."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from gxp_rag.config import settings
from gxp_rag.hitl.audit_logger import AuditLogger
from gxp_rag.schemas.audit import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEventType,
    ElectronicSignature,
    UserRole,
)
from gxp_rag.schemas.document import DocumentStatus, GxPDocumentDraft


class ApprovalWorkflowManager:
    """Manages pending human approval workflows, electronic signatures, and state transitions."""

    def __init__(self, data_dir: Optional[Path] = None, audit_logger: Optional[AuditLogger] = None):
        self.data_dir = data_dir or settings.data_dir
        self.approvals_file = self.data_dir / "approvals.json"
        self.drafts_dir = self.data_dir / "drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.audit_logger = audit_logger or AuditLogger()
        self._approvals: Dict[str, ApprovalRequest] = self._load_approvals()

    def _load_approvals(self) -> Dict[str, ApprovalRequest]:
        """Load stored approval requests from disk."""
        if not self.approvals_file.exists():
            return {}
        try:
            raw = json.loads(self.approvals_file.read_text(encoding="utf-8"))
            return {k: ApprovalRequest(**v) for k, v in raw.items()}
        except Exception:
            return {}

    def _save_approvals(self) -> None:
        """Persist approval requests to disk."""
        self.approvals_file.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.model_dump() for k, v in self._approvals.items()}
        self.approvals_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_draft(self, draft: GxPDocumentDraft) -> Path:
        """Persist a draft JSON document."""
        draft_file = self.drafts_dir / f"{draft.doc_id}.json"
        draft_file.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
        return draft_file

    def get_draft(self, doc_id: str) -> Optional[GxPDocumentDraft]:
        """Load draft by doc_id."""
        draft_file = self.drafts_dir / f"{doc_id}.json"
        if not draft_file.exists():
            return None
        try:
            return GxPDocumentDraft.model_validate_json(draft_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_drafts(self) -> List[GxPDocumentDraft]:
        """List all saved drafts."""
        drafts = []
        for file in self.drafts_dir.glob("*.json"):
            try:
                d = GxPDocumentDraft.model_validate_json(file.read_text(encoding="utf-8"))
                drafts.append(d)
            except Exception:
                pass
        # Sort by creation timestamp desc
        drafts.sort(key=lambda x: x.creation_timestamp, reverse=True)
        return drafts

    def create_approval_request(
        self,
        draft: GxPDocumentDraft,
        justification: str,
        author_id: str = "AI Assistant",
        required_roles: Optional[List[UserRole]] = None,
    ) -> ApprovalRequest:
        """Initiate a formal Human-in-the-Loop approval request."""
        # Save draft snapshot
        self.save_draft(draft)

        req_id = f"APP-{uuid.uuid4().hex[:8].upper()}"
        roles = required_roles or [UserRole.SME_REVIEWER, UserRole.QA_SPECIALIST]

        approval_req = ApprovalRequest(
            request_id=req_id,
            doc_id=draft.doc_id,
            doc_title=draft.title,
            doc_version=draft.version,
            author_id=author_id,
            justification=justification,
            required_roles=roles,
            status=ApprovalStatus.PENDING,
            document_snapshot=draft.model_dump(),
        )

        self._approvals[req_id] = approval_req
        self._save_approvals()

        # Update draft status
        draft.status = DocumentStatus.PENDING_APPROVAL
        self.save_draft(draft)

        # Log audit event
        self.audit_logger.log_event(
            event_type=AuditEventType.APPROVAL_REQUESTED,
            user_id=author_id,
            user_role=UserRole.AUTHOR,
            doc_id=draft.doc_id,
            doc_version=draft.version,
            action_details={
                "request_id": req_id,
                "justification": justification,
                "required_roles": [r.value for r in roles],
            },
        )

        return approval_req

    def approve(
        self,
        request_id: str,
        signer_name: str,
        user_id: str,
        signer_role: UserRole,
        comments: str,
        meaning: str = "I confirm that I have reviewed this GxP document and approve its scientific, technical, and regulatory compliance.",
    ) -> ApprovalRequest:
        """Approve a draft with a 21 CFR Part 11 Electronic Signature."""
        req = self._approvals.get(request_id)
        if not req:
            raise ValueError(f"Approval request not found: {request_id}")

        # Fetch draft
        draft = self.get_draft(req.doc_id)
        doc_content = draft.to_markdown() if draft else json.dumps(req.document_snapshot or {})

        # Create electronic signature
        e_sig = ElectronicSignature.create_signature(
            signer_name=signer_name,
            user_id=user_id,
            signer_role=signer_role,
            meaning=meaning,
            document_content=doc_content,
        )

        req.signatures.append(e_sig)
        req.status = ApprovalStatus.APPROVED
        req.reviewed_at = datetime.now(timezone.utc).isoformat()
        req.reviewed_by = f"{signer_name} ({user_id})"
        req.review_comments = comments

        self._save_approvals()

        # Update draft if exists
        if draft:
            draft.status = DocumentStatus.APPROVED
            self.save_draft(draft)

        # Log audit event with e-signature
        self.audit_logger.log_event(
            event_type=AuditEventType.APPROVAL_GRANTED,
            user_id=user_id,
            user_role=signer_role,
            doc_id=req.doc_id,
            doc_version=req.doc_version,
            action_details={
                "request_id": request_id,
                "comments": comments,
            },
            signature=e_sig,
        )

        return req

    def reject(
        self,
        request_id: str,
        reviewer_name: str,
        user_id: str,
        reviewer_role: UserRole,
        reason: str,
    ) -> ApprovalRequest:
        """Reject a draft with documented rationale."""
        req = self._approvals.get(request_id)
        if not req:
            raise ValueError(f"Approval request not found: {request_id}")

        req.status = ApprovalStatus.REJECTED
        req.reviewed_at = datetime.now(timezone.utc).isoformat()
        req.reviewed_by = f"{reviewer_name} ({user_id})"
        req.review_comments = reason

        self._save_approvals()

        draft = self.get_draft(req.doc_id)
        if draft:
            draft.status = DocumentStatus.REJECTED
            self.save_draft(draft)

        self.audit_logger.log_event(
            event_type=AuditEventType.APPROVAL_REJECTED,
            user_id=user_id,
            user_role=reviewer_role,
            doc_id=req.doc_id,
            doc_version=req.doc_version,
            action_details={
                "request_id": request_id,
                "rejection_reason": reason,
            },
        )

        return req

    def request_revision(
        self,
        request_id: str,
        reviewer_name: str,
        user_id: str,
        reviewer_role: UserRole,
        revision_feedback: str,
    ) -> ApprovalRequest:
        """Request revisions on a draft with feedback."""
        req = self._approvals.get(request_id)
        if not req:
            raise ValueError(f"Approval request not found: {request_id}")

        req.status = ApprovalStatus.REVISION_REQUESTED
        req.reviewed_at = datetime.now(timezone.utc).isoformat()
        req.reviewed_by = f"{reviewer_name} ({user_id})"
        req.review_comments = revision_feedback

        self._save_approvals()

        draft = self.get_draft(req.doc_id)
        if draft:
            draft.status = DocumentStatus.REVISION_REQUESTED
            self.save_draft(draft)

        self.audit_logger.log_event(
            event_type=AuditEventType.REVISION_REQUESTED,
            user_id=user_id,
            user_role=reviewer_role,
            doc_id=req.doc_id,
            doc_version=req.doc_version,
            action_details={
                "request_id": request_id,
                "feedback": revision_feedback,
            },
        )

        return req

    def list_approvals(self, status: Optional[ApprovalStatus] = None) -> List[ApprovalRequest]:
        """List approval requests filtered by status."""
        items = list(self._approvals.values())
        if status:
            items = [item for item in items if item.status == status]
        # Sort by creation time desc
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items

    def get_approval(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retrieve specific approval request."""
        return self._approvals.get(request_id)
