"""Tests for Human-in-the-Loop (HITL) Workflow & 21 CFR Part 11 Audit Trail."""

import tempfile
from pathlib import Path
import pytest
from gxp_rag.hitl.approval_workflow import ApprovalWorkflowManager
from gxp_rag.hitl.audit_logger import AuditLogger
from gxp_rag.schemas.audit import ApprovalStatus, UserRole
from gxp_rag.schemas.document import DocumentStatus, DocumentType, GxPDocumentDraft


def test_hitl_approval_lifecycle_and_audit_chain():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        audit_log = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path=audit_log)
        manager = ApprovalWorkflowManager(data_dir=tmp_path, audit_logger=logger)

        draft = GxPDocumentDraft(
            doc_id="SOP-LAB-101",
            title="Centrifuge High-Speed Operation",
            doc_type=DocumentType.SOP,
            version="1.0",
            department="Analytical Operations",
            purpose="Standardize centrifuge balancing and rotor inspection.",
            scope="Applies to Beckman Coulter Avanti centrifuges.",
        )

        # 1. Create Approval Request
        req = manager.create_approval_request(
            draft=draft,
            justification="Initial author release for lab operations",
            author_id="author_sarah",
        )

        assert req.status == ApprovalStatus.PENDING
        assert req.doc_id == "SOP-LAB-101"
        assert len(manager.list_approvals(status=ApprovalStatus.PENDING)) == 1

        # 2. Approve with Electronic Signature
        approved_req = manager.approve(
            request_id=req.request_id,
            signer_name="Dr. Eleanor Vance",
            user_id="qa_lead_01",
            signer_role=UserRole.QA_SPECIALIST,
            comments="Reviewed against site validation protocol and approved.",
        )

        assert approved_req.status == ApprovalStatus.APPROVED
        assert len(approved_req.signatures) == 1
        sig = approved_req.signatures[0]
        assert sig.signer_name == "Dr. Eleanor Vance"
        assert sig.signer_role == UserRole.QA_SPECIALIST
        assert len(sig.signature_digest) == 64

        # Verify updated draft state
        saved_draft = manager.get_draft("SOP-LAB-101")
        assert saved_draft is not None
        assert saved_draft.status == DocumentStatus.APPROVED

        # 3. Verify 21 CFR Part 11 Audit Trail Integrity
        integrity = logger.verify_integrity()
        assert integrity["valid"] is True
        assert integrity["total_records"] >= 2  # Request + Approval


def test_hitl_rejection_and_revision():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        logger = AuditLogger(log_path=tmp_path / "audit.jsonl")
        manager = ApprovalWorkflowManager(data_dir=tmp_path, audit_logger=logger)

        draft = GxPDocumentDraft(
            doc_id="DEV-2024-999",
            title="Unplanned Buffer Spillage",
            doc_type=DocumentType.DEVIATION_REPORT,
            version="1.0",
            department="Manufacturing",
            purpose="Document spillage",
            scope="Facility Area 2",
        )

        req = manager.create_approval_request(draft, justification="Root cause investigation")
        
        # Request Revision
        revised = manager.request_revision(
            request_id=req.request_id,
            reviewer_name="Marcus Sterling",
            user_id="qa_mgr_01",
            reviewer_role=UserRole.QA_MANAGER,
            revision_feedback="Include CAPA reference number in Section 5.0.",
        )
        assert revised.status == ApprovalStatus.REVISION_REQUESTED

        # Verify integrity
        assert logger.verify_integrity()["valid"] is True
