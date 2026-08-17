"""Local Langfuse Observability and Tracing for GxP Document Drafting (Langfuse v4)."""

import logging
import os
from typing import Any, Dict, List, Optional
from langfuse import Langfuse

from gxp_rag.config import settings

logger = logging.getLogger("gxp_rag.observability")


class LangfuseTracker:
    """Local Langfuse client wrapper for GxP RAG & Agent observability."""

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.enabled = enabled if enabled is not None else settings.enable_langfuse
        self.public_key = public_key or settings.langfuse_public_key
        self.secret_key = secret_key or settings.langfuse_secret_key
        self.host = host or settings.langfuse_host

        self._client: Optional[Langfuse] = None
        if self.enabled:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize Langfuse SDK client."""
        try:
            os.environ["LANGFUSE_PUBLIC_KEY"] = self.public_key or "pk-lf-local"
            os.environ["LANGFUSE_SECRET_KEY"] = self.secret_key or "sk-lf-local"
            os.environ["LANGFUSE_HOST"] = self.host

            self._client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize local Langfuse client: {e}")
            self._client = None

    def is_connected(self) -> bool:
        """Check if Langfuse client is initialized and operational."""
        return self._client is not None and self.enabled

    def trace_drafting_session(
        self,
        doc_id: str,
        doc_type: str,
        department: str,
        prompt: str,
        user_id: str,
        user_role: str,
        model_name: str,
        session_id: Optional[str] = None,
    ) -> Any:
        """Create and return a root Langfuse agent observation for a GxP drafting operation."""
        if not self.is_connected() or not self._client:
            return None

        try:
            span = self._client.start_observation(
                name="gxp-document-drafting",
                as_type="agent",
                input={
                    "prompt": prompt,
                    "target_type": doc_type,
                    "department": department,
                    "user_id": user_id,
                    "user_role": user_role,
                },
                metadata={
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "department": department,
                    "user_role": user_role,
                    "model": model_name,
                    "framework": "Pydantic AI",
                    "regulatory_context": "21 CFR Part 11 / ALCOA+",
                    "session_id": session_id or f"session-{doc_id}",
                },
            )
            return span
        except Exception as e:
            logger.debug(f"Langfuse trace creation failed: {e}")
            return None

    def trace_qdrant_retrieval(
        self,
        trace: Any,
        query: str,
        results: List[Any],
        filters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log Qdrant vector retrieval span inside Langfuse trace."""
        if not self.is_connected() or not self._client:
            return

        try:
            retriever_span = self._client.start_observation(
                name="qdrant-semantic-search",
                as_type="retriever",
                input={"query": query, "filters": filters or {}},
                metadata={
                    "collection": settings.qdrant_collection,
                    "total_results": len(results),
                },
            )
            retriever_span.update(
                output=[
                    {
                        "doc_id": getattr(r, "doc_id", ""),
                        "title": getattr(r, "doc_title", ""),
                        "section": getattr(r, "section_heading", ""),
                        "score": getattr(r, "score", 0.0),
                    }
                    for r in results
                ]
            )
            retriever_span.end()
        except Exception as e:
            logger.debug(f"Langfuse retrieval span failed: {e}")

    def trace_agent_execution(
        self,
        trace: Any,
        model_name: str,
        prompt: str,
        output_data: Dict[str, Any],
        usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log Pydantic AI agent generation span."""
        if not self.is_connected() or not self._client:
            return

        try:
            gen_span = self._client.start_observation(
                name="pydantic-ai-gxp-agent",
                as_type="generation",
                input=prompt,
                metadata={"model": model_name, "framework": "Pydantic AI"},
            )
            gen_span.update(
                output=output_data,
                model=model_name,
                usage_details=usage,
            )
            gen_span.end()

            # Also update parent trace output if present
            if trace and hasattr(trace, "update"):
                trace.update(output={"doc_id": output_data.get("doc_id"), "status": output_data.get("status")})
                trace.end()
        except Exception as e:
            logger.debug(f"Langfuse agent generation span failed: {e}")

    def trace_compliance_evaluation(
        self,
        trace: Any,
        compliance_report: Any,
    ) -> None:
        """Log compliance evaluation and create Langfuse scores."""
        if not self.is_connected() or not self._client:
            return

        try:
            score_val = getattr(compliance_report, "compliance_score", 100.0)
            overall_compliant = getattr(compliance_report, "overall_compliant", True)
            doc_id = getattr(compliance_report, "document_id", "")

            span = self._client.start_observation(
                name="alcoa-compliance-guardrail",
                as_type="guardrail",
                input={"document_id": doc_id},
            )
            span.update(
                output={
                    "overall_compliant": overall_compliant,
                    "score": score_val,
                    "alcoa_checks_count": len(getattr(compliance_report, "alcoa_checks", [])),
                    "critical_deficiencies": getattr(compliance_report, "critical_deficiencies", []),
                }
            )
            span.end()

            # Record Langfuse quality scores
            trace_id = trace.trace_id if hasattr(trace, "trace_id") else None
            if trace_id:
                self._client.create_score(
                    trace_id=trace_id,
                    name="gxp-compliance-score",
                    value=score_val / 100.0,
                    comment=f"Overall Compliant: {overall_compliant}",
                )
                self._client.create_score(
                    trace_id=trace_id,
                    name="alcoa-data-integrity-pass",
                    value=1.0 if overall_compliant else 0.0,
                    comment="ALCOA+ checklist verification",
                )
        except Exception as e:
            logger.debug(f"Langfuse compliance span failed: {e}")

    def trace_hitl_signature(
        self,
        trace: Any,
        request_id: str,
        action: str,
        signer_name: str,
        signer_role: str,
        signature_digest: str,
    ) -> None:
        """Log 21 CFR Part 11 Electronic Signature event in Langfuse."""
        if not self.is_connected() or not self._client:
            return

        try:
            self._client.create_event(
                name="21-cfr-part-11-e-signature",
                input={"action": action, "signer": signer_name},
                metadata={
                    "request_id": request_id,
                    "action": action,
                    "signer_name": signer_name,
                    "signer_role": signer_role,
                    "sha256_digest": signature_digest,
                },
            )
        except Exception as e:
            logger.debug(f"Langfuse e-signature event failed: {e}")

    def flush(self) -> None:
        """Flush pending events to Langfuse server."""
        if self._client:
            try:
                self._client.flush()
            except Exception:
                pass


# Global singleton instance
langfuse_tracker = LangfuseTracker()
