"""21 CFR Part 11 Compliant Audit Logger with SHA-256 Hash Chaining."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from gxp_rag.config import settings
from gxp_rag.schemas.audit import (
    AuditEventType,
    AuditTrailRecord,
    ElectronicSignature,
    UserRole,
)


class AuditLogger:
    """Tamper-evident, append-only GxP audit trail logger."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or settings.audit_log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash: Optional[str] = self._get_latest_hash()

    def _get_latest_hash(self) -> Optional[str]:
        """Read the last record hash from the log file if it exists."""
        if not self.log_path.exists():
            return None
        last_line = None
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line
        if last_line:
            try:
                data = json.loads(last_line)
                return data.get("record_hash")
            except Exception:
                return None
        return None

    def log_event(
        self,
        event_type: AuditEventType,
        user_id: str = "system",
        user_role: Optional[UserRole] = None,
        doc_id: Optional[str] = None,
        doc_version: Optional[str] = None,
        action_details: Optional[Dict[str, Any]] = None,
        signature: Optional[ElectronicSignature] = None,
    ) -> AuditTrailRecord:
        """Log a new GxP event with cryptographic chain link."""
        event_id = str(uuid.uuid4())
        record = AuditTrailRecord(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            doc_id=doc_id,
            doc_version=doc_version,
            user_id=user_id,
            user_role=user_role,
            action_details=action_details or {},
            signature=signature,
            previous_record_hash=self._last_hash,
        )
        record.record_hash = record.compute_hash()
        self._last_hash = record.record_hash

        # Append record to JSONL file
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

        return record

    def get_records(
        self,
        doc_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        limit: int = 100,
    ) -> List[AuditTrailRecord]:
        """Retrieve audit trail records with optional filtering."""
        if not self.log_path.exists():
            return []

        records = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    rec = AuditTrailRecord(**data)
                    if doc_id and rec.doc_id != doc_id:
                        continue
                    if event_type and rec.event_type != event_type:
                        continue
                    records.append(rec)
                except Exception:
                    continue

        return records[-limit:]

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify cryptographic hash chain of the entire audit trail."""
        if not self.log_path.exists():
            return {"valid": True, "total_records": 0, "message": "Audit log is empty."}

        records = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(AuditTrailRecord(**json.loads(line)))
                    except Exception as e:
                        return {"valid": False, "error": f"Corrupted JSON record: {str(e)}"}

        prev_hash = None
        for idx, rec in enumerate(records):
            # Check previous hash match
            if rec.previous_record_hash != prev_hash:
                return {
                    "valid": False,
                    "failed_record_index": idx,
                    "event_id": rec.event_id,
                    "error": f"Chain break: previous_hash mismatch at record {idx}",
                }
            # Check current record hash computation
            expected_hash = rec.compute_hash()
            if rec.record_hash != expected_hash:
                return {
                    "valid": False,
                    "failed_record_index": idx,
                    "event_id": rec.event_id,
                    "error": f"Tampering detected: hash mismatch at record {idx}",
                }
            prev_hash = rec.record_hash

        return {
            "valid": True,
            "total_records": len(records),
            "latest_hash": prev_hash,
            "message": "Audit trail integrity successfully verified (All 21 CFR Part 11 records intact).",
        }
