"""Configuration settings for GxP Document Draft Agent."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application configuration settings."""

    # Storage Paths
    data_dir: Path = Field(default_factory=lambda: Path("./data"))
    qdrant_path: Path = Field(default_factory=lambda: Path("./data/qdrant_storage"))
    qdrant_url: Optional[str] = Field(default=None)  # e.g., "http://localhost:6333" for remote
    qdrant_api_key: Optional[str] = Field(default=None)
    qdrant_collection: str = "gxp_knowledge_base"
    
    # Embedding Configuration
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    
    # Audit Trail Configuration (21 CFR Part 11)
    audit_log_path: Path = Field(default_factory=lambda: Path("./data/audit_trail.jsonl"))
    
    # LLM Configuration
    # Supported prefixes:
    # - openai:gpt-4o, openai:o3-mini
    # - anthropic:claude-3-7-sonnet-latest, anthropic:claude-3-5-sonnet-latest
    # - google:gemini-2.0-flash, google:gemini-1.5-pro
    # - ollama:llama3.3, ollama:qwen2.5:72b, ollama:deepseek-r1
    # - test (TestModel)
    default_model: str = Field(
        default_factory=lambda: os.getenv("GXP_LLM_MODEL", "openai:gpt-4o")
    )
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    )
    
    # Langfuse Local Observability Configuration
    langfuse_public_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-local-gxp")
    )
    langfuse_secret_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-local-gxp")
    )
    langfuse_host: str = Field(
        default_factory=lambda: os.getenv("LANGFUSE_HOST", os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000"))
    )
    enable_langfuse: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_LANGFUSE", "true").lower() in ("true", "1", "yes")
    )
    
    # Web & Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    def ensure_directories(self) -> None:
        """Ensure all required data directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.qdrant_url:
            self.qdrant_path.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)


# Global default settings instance
settings = Settings()
