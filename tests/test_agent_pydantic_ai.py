"""Tests for Pydantic AI GxP Agent and Drafting Service."""

import pytest
from pydantic_ai.models.test import TestModel

from gxp_rag.agent.gxp_agent import GxPDraftingService, create_gxp_agent
from gxp_rag.agent.tools import GxPAgentDeps
from gxp_rag.hitl.approval_workflow import ApprovalWorkflowManager
from gxp_rag.hitl.audit_logger import AuditLogger
from gxp_rag.rag.qdrant_store import QdrantStore
from gxp_rag.schemas.audit import UserRole
from gxp_rag.schemas.document import DocumentType, GxPDocumentDraft, GxPSection, ProceduralStep


@pytest.mark.asyncio
async def test_pydantic_ai_agent_creation_and_run(tmp_path):
    qdrant = QdrantStore(location=":memory:", collection_name="test_agent_kb")
    qdrant.ingest_text(
        "### 1.0 Purpose\nCleanroom sanitization using 70% IPA with contact time of 5 minutes.",
        title="Sanitization SOP",
        doc_id="SOP-MFG-014",
    )

    logger = AuditLogger(log_path=tmp_path / "audit.jsonl")
    approval_mgr = ApprovalWorkflowManager(data_dir=tmp_path, audit_logger=logger)

    agent = create_gxp_agent(model_spec="test")

    # Sample output model for TestModel
    sample_draft = GxPDocumentDraft(
        doc_id="SOP-MFG-099",
        title="Automated Cleanroom Disinfection Procedure",
        doc_type=DocumentType.SOP,
        version="1.0",
        department="Manufacturing Operations",
        purpose="To specify cleanroom disinfection procedures.",
        scope="Applies to Grade A/B cleanroom suites.",
        procedure_sections=[
            GxPSection(
                section_id="5.0",
                title="Cleaning Procedure",
                steps=[
                    ProceduralStep(
                        step_number="5.1",
                        action_title="Apply IPA",
                        instruction_text="Apply sterile 70% IPA to work surface.",
                        role_responsible="Cleanroom Operator",
                        critical_parameters=["Contact time >= 5.0 min"],
                        acceptance_criteria="Surface remains wet for 5 minutes",
                    )
                ],
            )
        ],
    )

    # TestModel with custom output
    test_model = TestModel(custom_output_args=sample_draft.model_dump())

    deps = GxPAgentDeps(
        qdrant_store=qdrant,
        approval_manager=approval_mgr,
        audit_logger=logger,
        user_id="test_qa",
        user_role=UserRole.AUTHOR,
        target_doc_type="SOP",
        target_department="Manufacturing Operations",
    )

    with agent.override(model=test_model):
        result = await agent.run(
            "Draft cleanroom disinfection SOP using SOP-MFG-014",
            deps=deps,
        )

        assert result.output.doc_id == "SOP-MFG-099"
        assert result.output.doc_type == DocumentType.SOP
        assert len(result.output.procedure_sections) == 1


def test_compliance_evaluation_service(tmp_path):
    qdrant = QdrantStore(location=":memory:")
    logger = AuditLogger(log_path=tmp_path / "audit.jsonl")
    approval_mgr = ApprovalWorkflowManager(data_dir=tmp_path, audit_logger=logger)
    service = GxPDraftingService(
        qdrant_store=qdrant,
        approval_manager=approval_mgr,
        audit_logger=logger,
    )

    draft = GxPDocumentDraft(
        doc_id="SOP-QC-077",
        title="Analytical Balance Calibration",
        doc_type=DocumentType.SOP,
        version="1.0",
        department="Quality Control",
        purpose="Define calibration requirements for 5-decimal balances.",
        scope="All analytical balances in QC testing laboratory.",
        procedure_sections=[
            GxPSection(
                section_id="4.0",
                title="Calibration Procedure",
                steps=[
                    ProceduralStep(
                        step_number="4.1",
                        action_title="Zero Balance",
                        instruction_text="Zero and tare the balance pan.",
                        role_responsible="QC Analyst",
                        critical_parameters=["Stable zero reading ± 0.00001 g"],
                        acceptance_criteria="Zero display steady for 10 seconds",
                    )
                ],
            )
        ],
        acceptance_criteria_summary=["Calibration error <= 0.1% across all standard weights"],
    )

    report = service.evaluate_compliance(draft)
    assert report.document_id == "SOP-QC-077"
    assert report.overall_compliant is True
    assert report.compliance_score >= 80.0
    assert len(report.alcoa_checks) >= 4
