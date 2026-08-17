"""Qdrant Vector Database integration for GxP knowledge retrieval."""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http import models

from gxp_rag.config import settings
from gxp_rag.rag.chunker import GxPChunk, GxPChunker
from gxp_rag.rag.embeddings import EmbeddingService
from gxp_rag.rag.parser import GxPDocumentParser, ParsedGxPDocument


class GxPSearchResult(BaseModel):
    """Result returned from Qdrant vector retrieval."""
    chunk_id: str
    doc_id: str
    doc_title: str
    doc_type: str
    department: str
    version: str
    section_heading: Optional[str] = None
    text: str
    score: float
    file_path: Optional[str] = None


class QdrantStore:
    """Manages Qdrant vector collection for GxP documents."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        client: Optional[QdrantClient] = None,
        embedding_service: Optional[EmbeddingService] = None,
        location: Optional[str] = None,  # ":memory:" or path or None (uses settings)
    ):
        self.collection_name = collection_name or settings.qdrant_collection
        self.embedding_service = embedding_service or EmbeddingService(settings.embedding_model)

        if client:
            self.client = client
        elif location == ":memory:":
            self.client = QdrantClient(location=":memory:")
        elif settings.qdrant_url:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
            )
        else:
            storage_path = Path(location) if location else settings.qdrant_path
            storage_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(storage_path))

        self.chunker = GxPChunker()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the Qdrant collection and payload indexes if they do not exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=settings.embedding_dim,
                    distance=models.Distance.COSINE,
                ),
            )
        # Create payload indexes for fast filtered searches if not local
        if settings.qdrant_url:
            for field_name in ["doc_id", "doc_type", "department", "version"]:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass

    def ingest_document(self, file_path_or_doc: Union[str, Path, ParsedGxPDocument]) -> int:
        """Parse, chunk, embed, and index a GxP document into Qdrant."""
        if isinstance(file_path_or_doc, ParsedGxPDocument):
            parsed_doc = file_path_or_doc
        else:
            parsed_doc = GxPDocumentParser.parse_file(file_path_or_doc)

        # Delete any existing points for this doc_id to support updates
        self.delete_document(parsed_doc.doc_id)

        chunks = self.chunker.chunk_document(parsed_doc)
        if not chunks:
            return 0

        # Generate embeddings
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedding_service.embed_texts(texts)

        # Build Qdrant points
        points = []
        for chunk, emb in zip(chunks, embeddings):
            # Create deterministic or random point UUID
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            point = models.PointStruct(
                id=point_id,
                vector=emb,
                payload=chunk.model_dump(),
            )
            points.append(point)

        # Upsert into Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )
        return len(chunks)

    def ingest_text(
        self,
        text: str,
        title: str,
        doc_type: str = "SOP",
        doc_id: Optional[str] = None,
        department: str = "Quality Assurance",
        version: str = "1.0",
    ) -> int:
        """Ingest raw text directly into the knowledge base."""
        parsed_doc = GxPDocumentParser.parse_text(
            text=text,
            title=title,
            doc_id=doc_id,
            department=department,
            version=version,
        )
        return self.ingest_document(parsed_doc)

    def ingest_directory(self, dir_path: Union[str, Path]) -> Dict[str, int]:
        """Ingest all supported document files in a directory."""
        path = Path(dir_path)
        if not path.is_dir():
            return {}

        results = {}
        for file in path.glob("**/*"):
            if file.is_file() and file.suffix.lower() in [".md", ".txt", ".pdf", ".docx", ".json"]:
                try:
                    chunks_count = self.ingest_document(file)
                    results[file.name] = chunks_count
                except Exception as e:
                    results[file.name] = -1
        return results

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.20,
        doc_types: Optional[List[str]] = None,
        department: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> List[GxPSearchResult]:
        """Execute semantic search with metadata filters using Universal Query API."""
        query_vector = self.embedding_service.embed_query(query)
        if not query_vector:
            return []

        # Build payload filters
        must_conditions = []
        if doc_types:
            must_conditions.append(
                models.FieldCondition(
                    key="doc_type",
                    match=models.MatchAny(any=doc_types),
                )
            )
        if department:
            must_conditions.append(
                models.FieldCondition(
                    key="department",
                    match=models.MatchValue(value=department),
                )
            )
        if doc_id:
            must_conditions.append(
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchValue(value=doc_id),
                )
            )

        query_filter = models.Filter(must=must_conditions) if must_conditions else None

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

        results: List[GxPSearchResult] = []
        for hit in response.points:
            payload = hit.payload or {}
            results.append(
                GxPSearchResult(
                    chunk_id=payload.get("chunk_id", ""),
                    doc_id=payload.get("doc_id", ""),
                    doc_title=payload.get("doc_title", ""),
                    doc_type=payload.get("doc_type", "SOP"),
                    department=payload.get("department", ""),
                    version=payload.get("version", "1.0"),
                    section_heading=payload.get("section_heading"),
                    text=payload.get("text", ""),
                    score=float(hit.score),
                    file_path=payload.get("file_path"),
                )
            )
        return results

    def list_documents(self) -> List[Dict[str, Any]]:
        """List summary of all unique documents currently indexed in Qdrant."""
        try:
            # Scroll through points to retrieve unique documents
            records, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            return []

        doc_map: Dict[str, Dict[str, Any]] = {}
        for record in records:
            payload = record.payload or {}
            doc_id = payload.get("doc_id")
            if not doc_id:
                continue
            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "doc_id": doc_id,
                    "title": payload.get("doc_title", doc_id),
                    "doc_type": payload.get("doc_type", "SOP"),
                    "department": payload.get("department", "QA"),
                    "version": payload.get("version", "1.0"),
                    "chunk_count": 0,
                    "file_path": payload.get("file_path"),
                }
            doc_map[doc_id]["chunk_count"] += 1

        return list(doc_map.values())

    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieve all indexed chunks for a given document."""
        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_id",
                        match=models.MatchValue(value=doc_id),
                    )
                ]
            ),
            limit=500,
            with_payload=True,
            with_vectors=False,
        )
        chunks = []
        for r in records:
            if r.payload:
                chunks.append(r.payload)
        # Sort by chunk_index
        chunks.sort(key=lambda x: x.get("chunk_index", 0))
        return chunks

    def delete_document(self, doc_id: str) -> bool:
        """Delete all points belonging to a specific document ID."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="doc_id",
                                match=models.MatchValue(value=doc_id),
                            )
                        ]
                    )
                ),
            )
            return True
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            info = self.client.get_collection(self.collection_name)
            docs = self.list_documents()
            return {
                "collection_name": self.collection_name,
                "total_points": info.points_count,
                "total_documents": len(docs),
                "status": str(info.status),
                "vector_size": settings.embedding_dim,
            }
        except Exception as e:
            return {"error": str(e)}
