"""Unit tests for GxP Schemas and Data Models."""

import pytest
from gxp_rag.schemas.document import (
    Citation,
    DocumentStatus,
    DocumentType,
    GxPDocumentDraft,
    GxPSection,
    ProceduralStep,
)
from gxp_rag.schemas.compliance import (
    ALCOAPrinciple,
    RegulatoryStandard,
    GxPComplianceReport,
)
from gxp_rag.schemas.audit import (
    AuditEventType,
    AuditTrailRecord,
    ElectronicSignature,
    UserRole,
)


def test_gxp_document_draft_creation_and_markdown():
    step1 = ProceduralStep(
        step_number="5.1",
        action_title="Sanitize Surface",
        instruction_text="Apply sterile 70% IPA to work surface using unidirectional strokes.",
        role_responsible="Cleanroom Operator",
        critical_parameters=["Wet contact time >= 5.0 minutes"],
        acceptance_criteria="Surface visibly wet for >= 5 minutes without pooling",
        verification_method="Log in Cleanroom Sanitization Log",
        citations=[
            Citation(
                source_doc_id="SOP-MFG-014",
                source_title="Cleanroom Sanitization",
                section="7.2.1",
                exact_quote_or_summary="Wipe in overlapping strokes (minimum 20% overlap).",
                relevance_explanation="Basis for wiping technique",
                relevance_score=0.92,
            )
        ],
    )

    section = GxPSection(
        section_id="5.0",
        title="Sanitization Procedure",
        content="This section details surface preparation.",
        steps=[step1],
    )

    draft = GxPDocumentDraft(
        doc_id="SOP-MFG-099",
        title="Emergency Bioburden Cleanroom Sanitization",
        doc_type=DocumentType.SOP,
        version="1.0",
        department="Manufacturing Operations",
        purpose="To define sanitization after a microbial excursion.",
        scope="Applies to ISO Class 5 filling suite in Building 4.",
        regulatory_standards=["FDA 21 CFR Part 211.67", "EU GMP Annex 1"],
        responsibilities={"Cleanroom Operator": "Execute sanitization", "QA": "Verify contact time"},
        procedure_sections=[section],
        acceptance_criteria_summary=["Zero CFU for Grade A active zones"],
        citations=step1.citations,
    )

    assert draft.doc_id == "SOP-MFG-099"
    assert draft.status == DocumentStatus.DRAFT
    assert len(draft.procedure_sections) == 1
    assert len(draft.citations) == 1

    md = draft.to_markdown()
    assert "# SOP-MFG-099: Emergency Bioburden Cleanroom Sanitization" in md
    assert "### 1.0 Purpose" in md
    assert "FDA 21 CFR Part 211.67" in md
    assert "SOP-MFG-014" in md


def test_electronic_signature_and_audit_record_hashing():
    sig = ElectronicSignature.create_signature(
        signer_name="Dr. Eleanor Vance",
        user_id="qa_lead_01",
        signer_role=UserRole.QA_SPECIALIST,
        meaning="I approve this document for GxP compliance",
        document_content="# SOP-001 Content",
    )

    assert sig.signer_name == "Dr. Eleanor Vance"
    assert len(sig.signature_digest) == 64  # SHA-256 length

    record = AuditTrailRecord(
        event_id="evt-001",
        event_type=AuditEventType.APPROVAL_GRANTED,
        doc_id="SOP-001",
        doc_version="1.0",
        user_id="qa_lead_01",
        user_role=UserRole.QA_SPECIALIST,
        action_details={"note": "Approved"},
        signature=sig,
        previous_record_hash=None,
    )

    h1 = record.compute_hash()
    record.record_hash = h1
    assert len(h1) == 64
