"""Tests for local Langfuse Observability Integration."""

import pytest
from gxp_rag.config import settings
from gxp_rag.observability.langfuse_tracker import LangfuseTracker
from gxp_rag.schemas.compliance import GxPComplianceReport, RegulatoryStandard


def test_langfuse_tracker_initialization():
    tracker = LangfuseTracker(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        host="http://localhost:3000",
        enabled=True,
    )
    assert tracker.public_key == "pk-lf-test"
    assert tracker.host == "http://localhost:3000"
    assert tracker.is_connected() is True


def test_langfuse_trace_creation_and_spans():
    tracker = LangfuseTracker(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        host="http://localhost:3000",
        enabled=True,
    )

    trace = tracker.trace_drafting_session(
        doc_id="SOP-MFG-001",
        doc_type="SOP",
        department="Manufacturing",
        prompt="Draft sanitization SOP",
        user_id="test_qa",
        user_role="QA_SPECIALIST",
        model_name="openai:gpt-4o",
    )
    assert trace is not None

    # Test Qdrant retrieval span
    tracker.trace_qdrant_retrieval(
        trace=trace,
        query="sanitization",
        results=[],
        filters={"doc_type": "SOP"},
    )

    # Test agent execution generation
    tracker.trace_agent_execution(
        trace=trace,
        model_name="openai:gpt-4o",
        prompt="Draft SOP",
        output_data={"doc_id": "SOP-MFG-001", "title": "Sanitization"},
    )

    # Test compliance evaluation span & score
    compliance = GxPComplianceReport(
        document_id="SOP-MFG-001",
        overall_compliant=True,
        compliance_score=95.0,
        evaluated_standards=[RegulatoryStandard.FDA_21CFR_PART_211],
        alcoa_checks=[],
    )
    tracker.trace_compliance_evaluation(trace, compliance)

    # Test e-signature event
    tracker.trace_hitl_signature(
        trace=trace,
        request_id="APP-001",
        action="approve",
        signer_name="Dr. Eleanor Vance",
        signer_role="QA_SPECIALIST",
        signature_digest="abcd1234ef5678",
    )

    tracker.flush()
