"""21 CFR Part 11 Audit Trail & Human-in-the-loop approval schemas."""

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    """GxP Audit Trail Event Types."""
    DOCUMENT_CREATED = "DOCUMENT_CREATED"
    DOCUMENT_UPDATED = "DOCUMENT_UPDATED"
    KB_INGESTION = "KB_INGESTION"
    KB_QUERY = "KB_QUERY"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    DOCUMENT_EXPORTED = "DOCUMENT_EXPORTED"


class UserRole(str, Enum):
    """GxP authorized user roles."""
    AUTHOR = "AUTHOR"
    SME_REVIEWER = "SME_REVIEWER"
    QA_SPECIALIST = "QA_SPECIALIST"
    QA_MANAGER = "QA_MANAGER"
    REGULATORY_AFFAIRS = "REGULATORY_AFFAIRS"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class ElectronicSignature(BaseModel):
    """21 CFR Part 11 compliant electronic signature object."""
    signer_name: str = Field(..., description="Printed full name of the signer")
    user_id: str = Field(..., description="Unique user identification string")
    signer_role: UserRole = Field(..., description="Signer role in GxP organization")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Contemporaneous UTC timestamp of signing"
    )
    meaning: str = Field(
        ...,
        description="Formal signature declaration (e.g. 'I approve this document as author / QA reviewer')"
    )
    signature_digest: str = Field(
        ...,
        description="SHA-256 cryptographic digest of document content + signer details"
    )

    @classmethod
    def create_signature(
        cls,
        signer_name: str,
        user_id: str,
        signer_role: UserRole,
        meaning: str,
        document_content: str,
    ) -> "ElectronicSignature":
        """Compute SHA-256 signature digest."""
        ts = datetime.now(timezone.utc).isoformat()
        raw = f"{user_id}:{signer_name}:{signer_role.value}:{meaning}:{ts}:{document_content}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return cls(
            signer_name=signer_name,
            user_id=user_id,
            signer_role=signer_role,
            timestamp=ts,
            meaning=meaning,
            signature_digest=digest,
        )


class AuditTrailRecord(BaseModel):
    """Tamper-evident 21 CFR Part 11 audit trail record."""
    event_id: str = Field(..., description="Unique event identifier (UUID)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC Timestamp"
    )
    event_type: AuditEventType
    doc_id: Optional[str] = None
    doc_version: Optional[str] = None
    user_id: str = Field(default="system")
    user_role: Optional[UserRole] = None
    action_details: Dict[str, Any] = Field(default_factory=dict)
    signature: Optional[ElectronicSignature] = None
    previous_record_hash: Optional[str] = Field(
        None,
        description="Hash of previous record in chain to guarantee immutability"
    )
    record_hash: str = Field(
        default="",
        description="SHA-256 hash of this record"
    )

    def compute_hash(self) -> str:
        """Compute cryptographic hash of this audit log entry."""
        data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "doc_id": self.doc_id,
            "doc_version": self.doc_version,
            "user_id": self.user_id,
            "user_role": self.user_role.value if self.user_role else None,
            "action_details": self.action_details,
            "signature": self.signature.model_dump() if self.signature else None,
            "previous_record_hash": self.previous_record_hash,
        }
        raw_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


class ApprovalStatus(str, Enum):
    """Status of a human-in-the-loop review request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class ApprovalRequest(BaseModel):
    """Pending Human-in-the-Loop review & approval request."""
    request_id: str = Field(..., description="Approval Request ID")
    doc_id: str = Field(..., description="Document identifier")
    doc_title: str = Field(..., description="Document title")
    doc_version: str = Field(default="1.0")
    author_id: str = Field(default="AI Assistant")
    justification: str = Field(..., description="Business and compliance justification for drafting")
    required_roles: List[UserRole] = Field(
        default_factory=lambda: [UserRole.SME_REVIEWER, UserRole.QA_SPECIALIST]
    )
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_comments: Optional[str] = None
    signatures: List[ElectronicSignature] = Field(default_factory=list)
    document_snapshot: Optional[Dict[str, Any]] = None
