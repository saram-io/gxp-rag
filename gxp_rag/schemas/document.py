"""GxP Document schemas and data models."""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """GxP document classifications."""
    SOP = "SOP"  # Standard Operating Procedure
    WORK_INSTRUCTION = "WORK_INSTRUCTION"  # Work Instruction
    DEVIATION_REPORT = "DEVIATION_REPORT"  # Deviation / Non-conformance Report
    VALIDATION_PROTOCOL = "VALIDATION_PROTOCOL"  # Validation Protocol (IQ/OQ/PQ/VSR)
    CAPA = "CAPA"  # Corrective and Preventive Action
    CHANGE_CONTROL = "CHANGE_CONTROL"  # Change Control Request
    BATCH_PRODUCTION_RECORD = "BATCH_PRODUCTION_RECORD"  # BPR / MBR
    ANALYTICAL_TEST_METHOD = "ANALYTICAL_TEST_METHOD"  # Test Method / Specification
    REGULATORY_GUIDELINE = "REGULATORY_GUIDELINE"  # Regulatory Reference / Guideline


class DocumentStatus(str, Enum):
    """Document lifecycle status."""
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REJECTED = "REJECTED"
    OBSOLETE = "OBSOLETE"


class Citation(BaseModel):
    """Citation linking drafted content back to GxP source documents."""
    source_doc_id: str = Field(..., description="Unique document ID of the source document")
    source_title: str = Field(..., description="Title of the source document")
    doc_type: str = Field(default="SOP", description="Type of source document (SOP, Deviation, etc.)")
    section: Optional[str] = Field(None, description="Section or heading in source document")
    exact_quote_or_summary: str = Field(..., description="Excerpt or summary from the source supporting this draft")
    relevance_explanation: str = Field(..., description="Why this source reference applies to the current requirement")
    relevance_score: Optional[float] = Field(None, description="Similarity score from Qdrant vector retrieval")


class ProceduralStep(BaseModel):
    """Individual granular procedural step in a GxP procedure."""
    step_number: str = Field(..., description="Numbered identifier, e.g. '5.1.2'")
    action_title: str = Field(..., description="Short descriptive title of the action")
    instruction_text: str = Field(..., description="Detailed, unambiguous, imperative action statement")
    role_responsible: str = Field(..., description="Specific role authorized to perform this step")
    critical_parameters: Optional[List[str]] = Field(
        default_factory=list,
        description="Critical Process Parameters (CPPs), e.g. 'Temperature: 2-8°C', 'Agitation: 150 RPM'"
    )
    acceptance_criteria: Optional[str] = Field(
        None,
        description="Observable, verifiable pass/fail condition for this step"
    )
    verification_method: Optional[str] = Field(
        None,
        description="Documentation / sign-off method (e.g. 'Initial in batch record', 'Automated SCADA log')"
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Source documents supporting the rationale or limits of this step"
    )


class GxPSection(BaseModel):
    """A major section in a GxP document."""
    section_id: str = Field(..., description="Section number, e.g. '4.0'")
    title: str = Field(..., description="Section title, e.g. 'Equipment Preparation'")
    content: Optional[str] = Field(None, description="Narrative explanatory content")
    steps: Optional[List[ProceduralStep]] = Field(
        default_factory=list,
        description="Sequential actionable steps contained within this section"
    )
    subsections: Optional[List["GxPSection"]] = Field(
        default_factory=list,
        description="Nested subsections"
    )


class RevisionEntry(BaseModel):
    """Revision history entry for version control."""
    version: str = Field(..., description="Document version, e.g. '1.0'")
    author: str = Field(..., description="Author of this version")
    date_created: str = Field(..., description="Date of revision (YYYY-MM-DD)")
    reason_for_change: str = Field(..., description="Detailed description of changes made and justification")
    approval_reference: Optional[str] = Field(None, description="Change control or approval request ID")


class GxPDocumentDraft(BaseModel):
    """Complete, structured GxP Document Draft compliant with life sciences regulations."""
    
    # Document Header & Metadata
    doc_id: str = Field(..., description="Unique document identifier, e.g. 'SOP-MFG-042'")
    title: str = Field(..., description="Full descriptive document title")
    doc_type: DocumentType = Field(..., description="Type of GxP document")
    version: str = Field(default="1.0", description="Document version string")
    department: str = Field(..., description="Originating department, e.g. 'Manufacturing', 'Quality Assurance'")
    effective_date: Optional[str] = Field(None, description="Target effective date (YYYY-MM-DD)")
    review_period_months: int = Field(default=24, description="Periodic review cycle in months")
    supersedes: Optional[str] = Field(None, description="Previous document ID/version superseded by this draft")
    
    # Life-Cycle Status
    status: DocumentStatus = Field(default=DocumentStatus.DRAFT, description="Current lifecycle state")
    author: str = Field(default="AI GxP Drafting Assistant", description="Author / Drafter name")
    creation_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp")
    
    # Standard GxP Core Sections
    purpose: str = Field(..., description="Section 1.0: Precise objective and purpose of the procedure/document")
    scope: str = Field(..., description="Section 2.0: Applicability boundary, facilities, systems, and exclusions")
    regulatory_standards: List[str] = Field(
        default_factory=list,
        description="Applicable standards (e.g. 'FDA 21 CFR Part 211.67', 'EU Annex 11', 'GAMP 5')"
    )
    responsibilities: Dict[str, str] = Field(
        default_factory=dict,
        description="Role-to-responsibility mapping (e.g. {'Operator': 'Execute steps', 'QA': 'Review and approve'})"
    )
    definitions_and_abbreviations: Dict[str, str] = Field(
        default_factory=dict,
        description="Glossary of domain terms and acronyms"
    )
    safety_and_environmental_precautions: List[str] = Field(
        default_factory=list,
        description="PPE, hazard warnings, biohazard or chemical safety requirements"
    )
    prerequisites_and_materials: List[str] = Field(
        default_factory=list,
        description="Required qualified reagents, calibrated instruments, utilities, and training prerequisites"
    )
    
    # Main Procedures
    procedure_sections: List[GxPSection] = Field(
        default_factory=list,
        description="Sequential operational sections and procedural steps"
    )
    
    # Quality & Compliance Controls
    acceptance_criteria_summary: List[str] = Field(
        default_factory=list,
        description="Comprehensive summary of pass/fail criteria across all operations"
    )
    contingency_and_deviation_handling: str = Field(
        default="In the event of any unexpected result or parameter excursion, immediately halt the procedure, notify the Area Supervisor, and initiate a Deviation Report per standard QA deviation management.",
        description="Protocol for handling anomalies and reporting deviations"
    )
    
    # Provenance & Audit
    citations: List[Citation] = Field(
        default_factory=list,
        description="Complete list of all RAG source citations used to build this draft"
    )
    revision_history: List[RevisionEntry] = Field(
        default_factory=list,
        description="Version revision tracking records"
    )
    
    # Required Reviewers / Sign-off Roles
    required_signoff_roles: List[str] = Field(
        default_factory=lambda: ["Author", "Subject Matter Expert", "Quality Assurance"],
        description="Roles required to approve and execute 21 CFR Part 11 electronic signatures"
    )
    
    def to_markdown(self) -> str:
        """Convert the structured GxP draft into a standardized formatted Markdown document."""
        md_lines = []
        md_lines.append(f"# {self.doc_id}: {self.title}")
        md_lines.append("")
        md_lines.append("## Document Control & Metadata")
        md_lines.append(f"- **Document Type**: {self.doc_type.value}")
        md_lines.append(f"- **Version**: {self.version}")
        md_lines.append(f"- **Department**: {self.department}")
        md_lines.append(f"- **Status**: {self.status.value}")
        md_lines.append(f"- **Effective Date**: {self.effective_date or 'Pending Final Approval'}")
        md_lines.append(f"- **Review Period**: {self.review_period_months} Months")
        if self.supersedes:
            md_lines.append(f"- **Supersedes**: {self.supersedes}")
        md_lines.append("")
        
        md_lines.append("---")
        md_lines.append("### 1.0 Purpose")
        md_lines.append(self.purpose)
        md_lines.append("")
        
        md_lines.append("### 2.0 Scope")
        md_lines.append(self.scope)
        md_lines.append("")
        
        if self.regulatory_standards:
            md_lines.append("### 3.0 Regulatory References & Standards")
            for std in self.regulatory_standards:
                md_lines.append(f"- {std}")
            md_lines.append("")
        
        if self.responsibilities:
            md_lines.append("### 4.0 Responsibilities")
            md_lines.append("| Role | Responsibilities |")
            md_lines.append("|---|---|")
            for role, resp in self.responsibilities.items():
                md_lines.append(f"| **{role}** | {resp} |")
            md_lines.append("")
            
        if self.definitions_and_abbreviations:
            md_lines.append("### 5.0 Definitions & Abbreviations")
            for term, defn in self.definitions_and_abbreviations.items():
                md_lines.append(f"- **{term}**: {defn}")
            md_lines.append("")
            
        if self.safety_and_environmental_precautions:
            md_lines.append("### 6.0 Safety & Environmental Precautions")
            for precaution in self.safety_and_environmental_precautions:
                md_lines.append(f"- ⚠️ {precaution}")
            md_lines.append("")
            
        if self.prerequisites_and_materials:
            md_lines.append("### 7.0 Prerequisites & Required Materials")
            for item in self.prerequisites_and_materials:
                md_lines.append(f"- [ ] {item}")
            md_lines.append("")
            
        md_lines.append("### 8.0 Procedure")
        for sec in self.procedure_sections:
            md_lines.append(f"#### {sec.section_id} {sec.title}")
            if sec.content:
                md_lines.append(sec.content)
                md_lines.append("")
            if sec.steps:
                for step in sec.steps:
                    md_lines.append(f"**{step.step_number} {step.action_title}** ({step.role_responsible})")
                    md_lines.append(f"> {step.instruction_text}")
                    if step.critical_parameters:
                        md_lines.append(f"> - *Critical Parameters*: {', '.join(step.critical_parameters)}")
                    if step.acceptance_criteria:
                        md_lines.append(f"> - *Acceptance Criteria*: {step.acceptance_criteria}")
                    if step.verification_method:
                        md_lines.append(f"> - *Verification Method*: {step.verification_method}")
                    md_lines.append("")
                    
        if self.acceptance_criteria_summary:
            md_lines.append("### 9.0 Acceptance Criteria Summary")
            for crit in self.acceptance_criteria_summary:
                md_lines.append(f"- {crit}")
            md_lines.append("")
            
        md_lines.append("### 10.0 Deviation & Anomaly Handling")
        md_lines.append(self.contingency_and_deviation_handling)
        md_lines.append("")
        
        if self.citations:
            md_lines.append("### 11.0 Grounded Citations & Knowledge Base References")
            md_lines.append("| Doc ID | Source Title | Section | Evidence / Quote |")
            md_lines.append("|---|---|---|---|")
            for cit in self.citations:
                md_lines.append(f"| {cit.source_doc_id} | {cit.source_title} | {cit.section or 'N/A'} | {cit.exact_quote_or_summary} |")
            md_lines.append("")
            
        md_lines.append("### 12.0 Revision History")
        if self.revision_history:
            md_lines.append("| Version | Date | Author | Reason for Change |")
            md_lines.append("|---|---|---|---|")
            for rev in self.revision_history:
                md_lines.append(f"| {rev.version} | {rev.date_created} | {rev.author} | {rev.reason_for_change} |")
        else:
            md_lines.append(f"| 1.0 | {date.today().isoformat()} | {self.author} | Initial Draft Generation |")
        md_lines.append("")
        
        md_lines.append("### 13.0 Signatures & Approvals (21 CFR Part 11)")
        md_lines.append("| Role | Signer Name | Signature Meaning | Date / Timestamp | Status |")
        md_lines.append("|---|---|---|---|---|")
        for role in self.required_signoff_roles:
            md_lines.append(f"| {role} | ____________________ | Approval of GxP Content | ____________________ | PENDING |")
        md_lines.append("")
        
        return "\n".join(md_lines)
