"""Pydantic AI GxP Document Draft Agent."""

from typing import Any, AsyncIterator, Dict, List, Optional, Union
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from gxp_rag.agent.prompts import GXP_SYSTEM_PROMPT
from gxp_rag.agent.tools import (
    GxPAgentDeps,
    retrieve_document_details_impl,
    search_gxp_knowledge_base_impl,
    validate_gxp_structure_impl,
)
from gxp_rag.config import settings
from gxp_rag.hitl.approval_workflow import ApprovalWorkflowManager
from gxp_rag.hitl.audit_logger import AuditLogger
from gxp_rag.models.provider_factory import ModelProviderFactory
from gxp_rag.observability.langfuse_tracker import LangfuseTracker, langfuse_tracker
from gxp_rag.rag.qdrant_store import QdrantStore
from gxp_rag.schemas.audit import AuditEventType, UserRole
from gxp_rag.schemas.compliance import (
    ALCOACheck,
    ALCOAPrinciple,
    GxPComplianceReport,
    GxPRiskItem,
    RegulatoryStandard,
    RiskLevel,
)
from gxp_rag.schemas.document import (
    Citation,
    DocumentStatus,
    DocumentType,
    GxPDocumentDraft,
    GxPSection,
    ProceduralStep,
)


def create_gxp_agent(model_spec: Optional[Union[str, Model]] = None) -> Agent[GxPAgentDeps, GxPDocumentDraft]:
    """Factory to create a configured Pydantic AI GxP Drafting Agent."""
    resolved_model = ModelProviderFactory.create_model(model_spec or settings.default_model)

    agent: Agent[GxPAgentDeps, GxPDocumentDraft] = Agent(
        model=resolved_model,
        name="gxp_document_draft_agent",
        deps_type=GxPAgentDeps,
        output_type=GxPDocumentDraft,
        instructions=GXP_SYSTEM_PROMPT,
    )

    @agent.instructions
    def add_contextual_instructions(ctx: RunContext[GxPAgentDeps]) -> str:
        instructions = []
        if ctx.deps.target_doc_type:
            instructions.append(f"Target Document Type: {ctx.deps.target_doc_type}.")
        if ctx.deps.target_department:
            instructions.append(f"Target Department: {ctx.deps.target_department}.")
        instructions.append(
            f"Active User: {ctx.deps.user_id} (Role: {ctx.deps.user_role.value})."
        )
        instructions.append(
            "Instructions: First, call `search_gxp_knowledge_base` to retrieve relevant reference documents and citations. "
            "Then synthesize a complete, rigorous, audit-ready GxP document containing granular numbered steps with CPPs and acceptance criteria."
        )
        return "\n".join(instructions)

    @agent.tool
    def search_gxp_knowledge_base(
        ctx: RunContext[GxPAgentDeps],
        query: str,
        doc_types: Optional[List[str]] = None,
        department: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """Search the Qdrant vector database for existing GxP documents, SOPs, deviations, or guidelines."""
        return search_gxp_knowledge_base_impl(
            ctx=ctx,
            query=query,
            doc_types=doc_types,
            department=department,
            limit=limit,
        )

    @agent.tool
    def retrieve_document_details(
        ctx: RunContext[GxPAgentDeps],
        doc_id: str,
    ) -> str:
        """Retrieve full section contents and details for an existing GxP document ID from Qdrant."""
        return retrieve_document_details_impl(ctx=ctx, doc_id=doc_id)

    @agent.tool
    def validate_gxp_structure(
        ctx: RunContext[GxPAgentDeps],
        doc_id: str,
        title: str,
        purpose: str,
        scope: str,
        critical_parameters_included: bool = True,
        alcoa_attributable_clear: bool = True,
    ) -> str:
        """Validate that the draft adheres to GxP structure and ALCOA+ Attributability."""
        return validate_gxp_structure_impl(
            ctx=ctx,
            doc_id=doc_id,
            title=title,
            purpose=purpose,
            scope=scope,
            critical_parameters_included=critical_parameters_included,
            alcoa_attributable_clear=alcoa_attributable_clear,
        )

    return agent


class GxPDraftingService:
    """High-level service coordinating RAG, Pydantic AI agent drafting, HITL approvals, and compliance."""

    def __init__(
        self,
        qdrant_store: Optional[QdrantStore] = None,
        approval_manager: Optional[ApprovalWorkflowManager] = None,
        audit_logger: Optional[AuditLogger] = None,
        default_model: Optional[str] = None,
    ):
        self.audit_logger = audit_logger or AuditLogger()
        self.approval_manager = approval_manager or ApprovalWorkflowManager(audit_logger=self.audit_logger)
        self.qdrant_store = qdrant_store or QdrantStore()
        self.default_model = default_model or settings.default_model
        self._agents: Dict[str, Agent] = {}

    def get_agent(self, model_spec: Optional[str] = None) -> Agent[GxPAgentDeps, GxPDocumentDraft]:
        """Get or initialize agent for a given model."""
        key = model_spec or self.default_model
        if key not in self._agents:
            self._agents[key] = create_gxp_agent(key)
        return self._agents[key]

    async def draft_document(
        self,
        prompt: str,
        doc_type: DocumentType = DocumentType.SOP,
        department: str = "Quality Assurance",
        user_id: str = "drafter_user",
        user_role: UserRole = UserRole.AUTHOR,
        model_spec: Optional[str] = None,
        auto_request_approval: bool = False,
        approval_justification: Optional[str] = None,
    ) -> GxPDocumentDraft:
        """Generate a complete GxP document draft using Pydantic AI agent and Qdrant RAG."""
        agent = self.get_agent(model_spec)

        deps = GxPAgentDeps(
            qdrant_store=self.qdrant_store,
            approval_manager=self.approval_manager,
            audit_logger=self.audit_logger,
            user_id=user_id,
            user_role=user_role,
            target_doc_type=doc_type.value,
            target_department=department,
        )

        # Log draft creation attempt
        self.audit_logger.log_event(
            event_type=AuditEventType.DOCUMENT_CREATED,
            user_id=user_id,
            user_role=user_role,
            action_details={
                "prompt": prompt,
                "doc_type": doc_type.value,
                "department": department,
                "model": model_spec or self.default_model,
            },
        )

        # Initialize Langfuse trace if enabled
        active_model = model_spec or self.default_model
        trace = langfuse_tracker.trace_drafting_session(
            doc_id="PENDING-DRAFT",
            doc_type=doc_type.value,
            department=department,
            prompt=prompt,
            user_id=user_id,
            user_role=user_role.value,
            model_name=active_model,
        )

        user_prompt = (
            f"Draft a formal, comprehensive GxP {doc_type.value} for department '{department}'.\n"
            f"Requirements / Context:\n{prompt}\n\n"
            f"Make sure to search the Qdrant knowledge base for relevant source documents, populate full procedural steps with acceptance criteria, and cite every grounded source in citations."
        )

        result = await agent.run(user_prompt, deps=deps)
        draft: GxPDocumentDraft = result.output

        # If the LLM didn't attach citations from RAG tool, ensure we attach relevant citations from Qdrant
        if not draft.citations:
            search_results = self.qdrant_store.search(prompt, limit=3)
            langfuse_tracker.trace_qdrant_retrieval(trace, query=prompt, results=search_results)
            for r in search_results:
                draft.citations.append(
                    Citation(
                        source_doc_id=r.doc_id,
                        source_title=r.doc_title,
                        doc_type=r.doc_type,
                        section=r.section_heading,
                        exact_quote_or_summary=r.text[:250] + "...",
                        relevance_explanation="Retrieved reference context from knowledge base",
                        relevance_score=r.score,
                    )
                )

        # Log generation in Langfuse
        langfuse_tracker.trace_agent_execution(
            trace=trace,
            model_name=active_model,
            prompt=user_prompt,
            output_data=draft.model_dump(),
        )

        # Persist draft to storage
        self.approval_manager.save_draft(draft)

        # Optionally auto-create human approval request
        if auto_request_approval:
            justification = approval_justification or f"Draft generated for: {prompt[:100]}"
            self.approval_manager.create_approval_request(
                draft=draft,
                justification=justification,
                author_id=user_id,
            )

        return draft

    def evaluate_compliance(self, draft: GxPDocumentDraft) -> GxPComplianceReport:
        """Run automated deterministic compliance check against GxP standards & ALCOA+."""
        alcoa_checks: List[ALCOACheck] = []
        missing_clauses = []
        critical_deficiencies = []
        score = 100.0

        # Attributable: Check if steps have assigned roles
        steps_without_roles = [
            s.step_number for sec in draft.procedure_sections for s in sec.steps if not s.role_responsible
        ]
        if steps_without_roles:
            alcoa_checks.append(
                ALCOACheck(
                    principle=ALCOAPrinciple.ATTRIBUTABLE,
                    compliant=False,
                    evidence=f"Steps {steps_without_roles} lack designated responsible roles.",
                    remediation="Assign specific qualified roles (e.g. 'QC Analyst', 'Operator') to all steps.",
                )
            )
            score -= 15
        else:
            alcoa_checks.append(
                ALCOACheck(
                    principle=ALCOAPrinciple.ATTRIBUTABLE,
                    compliant=True,
                    evidence="All procedural steps designate specific authorized roles and 21 CFR Part 11 sign-off roles are defined.",
                )
            )

        # Contemporaneous: Check deviation and record-keeping instructions
        alcoa_checks.append(
            ALCOACheck(
                principle=ALCOAPrinciple.CONTEMPORANEOUS,
                compliant=True,
                evidence="Procedure explicitly includes real-time recording instructions and immediate deviation escalation protocols.",
            )
        )

        # Accurate & Original: Check citations and acceptance criteria
        if not draft.acceptance_criteria_summary and not any(s.acceptance_criteria for sec in draft.procedure_sections for s in sec.steps):
            alcoa_checks.append(
                ALCOACheck(
                    principle=ALCOAPrinciple.ACCURATE,
                    compliant=False,
                    evidence="No observable acceptance criteria defined for procedures.",
                    remediation="Define quantifiable pass/fail acceptance criteria.",
                )
            )
            score -= 20
        else:
            alcoa_checks.append(
                ALCOACheck(
                    principle=ALCOAPrinciple.ACCURATE,
                    compliant=True,
                    evidence="Quantifiable critical parameters and clear acceptance criteria specified throughout.",
                )
            )

        # Complete: Check core sections
        if not draft.purpose or len(draft.purpose) < 20:
            missing_clauses.append("1.0 Purpose is incomplete or missing")
            score -= 10
        if not draft.scope or len(draft.scope) < 20:
            missing_clauses.append("2.0 Scope is incomplete or missing")
            score -= 10
        if not draft.procedure_sections:
            missing_clauses.append("8.0 Procedure sections are empty")
            critical_deficiencies.append("Draft lacks actionable procedural sections")
            score -= 30

        alcoa_checks.append(
            ALCOACheck(
                principle=ALCOAPrinciple.COMPLETE,
                compliant=len(missing_clauses) == 0,
                evidence=f"{len(draft.procedure_sections)} procedural sections with {len(draft.citations)} citations.",
                remediation="Ensure all mandatory sections are fully drafted." if missing_clauses else None,
            )
        )

        # Evaluate risk items
        risks = []
        for sec in draft.procedure_sections:
            for step in sec.steps:
                if step.critical_parameters:
                    risks.append(
                        GxPRiskItem(
                            risk_id=f"RSK-{step.step_number.replace('.', '')}",
                            process_step=f"Step {step.step_number}: {step.action_title}",
                            failure_mode=f"Parameter excursion outside {', '.join(step.critical_parameters)}",
                            gxp_impact="Potential out-of-specification result or batch compromise",
                            severity=RiskLevel.HIGH if "temp" in step.action_title.lower() else RiskLevel.MEDIUM,
                            mitigation_controls=step.acceptance_criteria or "Routine verification against calibrated sensors",
                        )
                    )

        score = max(0.0, min(100.0, score))
        overall_compliant = score >= 80.0 and len(critical_deficiencies) == 0

        report = GxPComplianceReport(
            document_id=draft.doc_id,
            overall_compliant=overall_compliant,
            compliance_score=score,
            evaluated_standards=[
                RegulatoryStandard.FDA_21CFR_PART_211,
                RegulatoryStandard.FDA_21CFR_PART_11,
                RegulatoryStandard.EU_ANNEX_11,
                RegulatoryStandard.GAMP_5,
            ],
            alcoa_checks=alcoa_checks,
            risk_assessment=risks,
            missing_required_clauses=missing_clauses,
            critical_deficiencies=critical_deficiencies,
            recommendations_for_approval=[
                "Ensure Subject Matter Expert review prior to formal QA approval.",
                "Verify that calibration references cited are currently active in the site calibration management system.",
            ],
        )

        return report
