"""GxP-aware semantic and hierarchical chunker."""

import re
from typing import List, Optional
from pydantic import BaseModel, Field

from gxp_rag.rag.parser import ParsedGxPDocument


class GxPChunk(BaseModel):
    """A semantic chunk of a GxP document ready for vector indexing."""
    chunk_id: str = Field(..., description="Unique chunk ID (e.g., SOP-MFG-001#chunk-0)")
    doc_id: str = Field(..., description="Parent document ID")
    doc_title: str = Field(..., description="Parent document title")
    doc_type: str = Field(..., description="Parent document type")
    department: str = Field(..., description="Department")
    version: str = Field(..., description="Document version")
    section_heading: Optional[str] = Field(None, description="Section heading this chunk belongs to")
    text: str = Field(..., description="Text content of the chunk")
    chunk_index: int = Field(..., description="Index of the chunk in the document")
    total_chunks: int = Field(default=1, description="Total chunks in parent document")
    file_path: Optional[str] = None


class GxPChunker:
    """Intelligent chunker that respects GxP document section headers."""

    def __init__(self, target_chunk_size: int = 600, chunk_overlap: int = 100):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: ParsedGxPDocument) -> List[GxPChunk]:
        """Split a parsed GxP document into semantic chunks."""
        raw_text = doc.raw_text
        if not raw_text.strip():
            return []

        # Split text by Markdown headers or standard GxP numbering: e.g. "### 1.0", "## 2.0", "1.0 Purpose", etc.
        section_pattern = r"(?m)^(?:#{1,4}\s*|\b(?:\d+\.\d+|\d+\.0)\s+)([A-Za-z0-9 &/\-—:,]+)$"
        
        # Find sections
        matches = list(re.finditer(section_pattern, raw_text))
        
        sections = []
        if not matches:
            # Fallback to paragraph splitting if no standard GxP headings found
            sections.append(("General Content", raw_text))
        else:
            # Preamble before first section
            if matches[0].start() > 0:
                preamble = raw_text[:matches[0].start()].strip()
                if preamble:
                    sections.append(("Header / Document Control", preamble))
            
            for i, match in enumerate(matches):
                heading = match.group(0).strip().lstrip("#").strip()
                start_pos = match.start()
                end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
                section_body = raw_text[start_pos:end_pos].strip()
                sections.append((heading, section_body))

        raw_chunks = []
        for heading, sec_text in sections:
            # If section text is within reasonable size, keep as single chunk
            if len(sec_text) <= self.target_chunk_size + 150:
                raw_chunks.append((heading, sec_text))
            else:
                # Sub-divide by paragraphs or sentences with overlap
                paras = [p.strip() for p in sec_text.split("\n\n") if p.strip()]
                current_chunk_parts = []
                current_len = 0

                for p in paras:
                    if current_len + len(p) > self.target_chunk_size and current_chunk_parts:
                        chunk_text = "\n\n".join(current_chunk_parts)
                        raw_chunks.append((heading, chunk_text))
                        # Keep last part for overlap
                        current_chunk_parts = [current_chunk_parts[-1], p] if len(current_chunk_parts[-1]) < self.chunk_overlap else [p]
                        current_len = sum(len(x) for x in current_chunk_parts)
                    else:
                        current_chunk_parts.append(p)
                        current_len += len(p)
                        
                if current_chunk_parts:
                    chunk_text = "\n\n".join(current_chunk_parts)
                    raw_chunks.append((heading, chunk_text))

        total_chunks = len(raw_chunks)
        chunks: List[GxPChunk] = []

        for idx, (heading, text) in enumerate(raw_chunks):
            # Prepend contextual header to text for stronger embedding representation
            contextualized_text = f"Document: {doc.doc_id} - {doc.title} (Type: {doc.doc_type.value}, Dept: {doc.department})\nSection: {heading}\n\n{text}"
            
            chunk = GxPChunk(
                chunk_id=f"{doc.doc_id}#chunk-{idx}",
                doc_id=doc.doc_id,
                doc_title=doc.title,
                doc_type=doc.doc_type.value,
                department=doc.department,
                version=doc.version,
                section_heading=heading,
                text=contextualized_text,
                chunk_index=idx,
                total_chunks=total_chunks,
                file_path=doc.file_path,
            )
            chunks.append(chunk)

        return chunks
