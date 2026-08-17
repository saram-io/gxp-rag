"""GxP Compliance, ALCOA+ principles, and risk assessment schemas."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RegulatoryStandard(str, Enum):
    """Supported regulatory and compliance frameworks."""
    FDA_21CFR_PART_211 = "FDA 21 CFR Part 211 (cGMP Finished Pharmaceuticals)"
    FDA_21CFR_PART_820 = "FDA 21 CFR Part 820 (Quality System Regulation / Medical Devices)"
    FDA_21CFR_PART_11 = "FDA 21 CFR Part 11 (Electronic Records & Electronic Signatures)"
    EU_ANNEX_11 = "EU GMP Annex 11 (Computerised Systems)"
    EU_GMP_VOL4 = "EudraLex Volume 4 (EU Guidelines for GMP)"
    ICH_Q9 = "ICH Q9 (Quality Risk Management)"
    ICH_Q10 = "ICH Q10 (Pharmaceutical Quality System)"
    GAMP_5 = "ISPE GAMP 5 (A Risk-Based Approach to Compliant GxP Computerized Systems)"
    ISO_13485 = "ISO 13485:2016 (Medical Devices Quality Management Systems)"
    ISO_9001 = "ISO 9001:2015 (Quality Management Systems)"


class ALCOAPrinciple(str, Enum):
    """ALCOA+ Data Integrity Principles."""
    ATTRIBUTABLE = "Attributable (Who performed/created the record)"
    LEGIBLE = "Legible (Readable and understandable throughout lifecycle)"
    CONTEMPORANEOUS = "Contemporaneous (Recorded at the time of activity execution)"
    ORIGINAL = "Original (First recording or certified true copy)"
    ACCURATE = "Accurate (Truthful, error-free, and validated)"
    COMPLETE = "Complete (All data, metadata, audit trails included)"
    CONSISTENT = "Consistent (No contradictory data or sequence violations)"
    ENDURING = "Enduring (Preserved against loss or tampering)"
    AVAILABLE = "Available (Accessible for audit and review)"


class ALCOACheck(BaseModel):
    """Check result for a specific ALCOA+ principle."""
    principle: ALCOAPrinciple
    compliant: bool = Field(..., description="Whether the draft satisfies this principle")
    evidence: str = Field(..., description="Observation or evidence in the draft")
    remediation: Optional[str] = Field(None, description="Recommended correction if non-compliant")


class RiskLevel(str, Enum):
    """Risk severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GxPRiskItem(BaseModel):
    """Failure Mode & Risk assessment item in GxP context (FMEA / ICH Q9)."""
    risk_id: str = Field(..., description="Unique Risk ID, e.g. 'RISK-01'")
    process_step: str = Field(..., description="Associated procedural step or section")
    failure_mode: str = Field(..., description="Potential failure or non-compliance event")
    gxp_impact: str = Field(..., description="Impact on product quality, patient safety, or data integrity")
    severity: RiskLevel = Field(..., description="Severity of impact")
    mitigation_controls: str = Field(..., description="Embedded controls, checks, or double-checks in the procedure")


class GxPComplianceReport(BaseModel):
    """Comprehensive GxP compliance verification report for a document draft."""
    document_id: str
    overall_compliant: bool
    compliance_score: float = Field(..., ge=0.0, le=100.0, description="Score out of 100")
    evaluated_standards: List[RegulatoryStandard]
    alcoa_checks: List[ALCOACheck]
    risk_assessment: List[GxPRiskItem] = Field(default_factory=list)
    missing_required_clauses: List[str] = Field(default_factory=list)
    critical_deficiencies: List[str] = Field(default_factory=list)
    recommendations_for_approval: List[str] = Field(default_factory=list)
