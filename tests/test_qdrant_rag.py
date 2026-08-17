"""Tests for Qdrant Vector Store, Parsing, Chunking, and Retrieval."""

import pytest
from pathlib import Path
from gxp_rag.rag.chunker import GxPChunker
from gxp_rag.rag.parser import GxPDocumentParser
from gxp_rag.rag.qdrant_store import QdrantStore
from gxp_rag.schemas.document import DocumentType


def test_parser_and_chunker():
    text = """# SOP-QC-050: pH Meter Calibration and Daily Verification
## Document Control
- **Document ID**: SOP-QC-050
- **Department**: Quality Control

### 1.0 Purpose
This SOP outlines the daily two-point calibration and maintenance of laboratory pH meters.

### 2.0 Scope
Applies to all Metrohm and Mettler Toledo pH meters in the QC testing laboratory.

### 3.0 Procedure
#### 3.1 Two-Point Buffer Calibration
Inspect electrodes and rinse with deionized water. Calibrate using pH 4.01 and pH 7.00 certified reference buffers. Slope must be 95.0% - 105.0%.
"""
    parsed = GxPDocumentParser.parse_text(text, filename="sop_ph_meter.md")
    assert parsed.doc_id == "SOP-QC-050"
    assert parsed.doc_type == DocumentType.SOP
    assert "pH Meter Calibration" in parsed.title

    chunker = GxPChunker(target_chunk_size=400, chunk_overlap=50)
    chunks = chunker.chunk_document(parsed)
    assert len(chunks) >= 1
    assert any("Two-Point Buffer Calibration" in c.text or "Procedure" in (c.section_heading or "") for c in chunks)


def test_qdrant_in_memory_ingest_and_search():
    store = QdrantStore(location=":memory:", collection_name="test_gxp_kb")

    # Ingest 2 sample documents
    doc1 = """# SOP-MFG-014: Cleanroom Sanitization
### 1.0 Purpose
Cleaning and disinfection of Grade A cleanrooms using sporicidal agents and 70% IPA. Minimum contact time is 10 minutes for sporicides.
"""
    doc2 = """# SOP-QC-028: HPLC System Suitability
### 1.0 Purpose
Operating Agilent 1260 HPLC and verifying system suitability with peak area %RSD <= 1.5% and retention time %RSD <= 1.0%.
"""
    c1 = store.ingest_text(doc1, title="Cleanroom Sanitization", doc_id="SOP-MFG-014", doc_type="SOP")
    c2 = store.ingest_text(doc2, title="HPLC Operation", doc_id="SOP-QC-028", doc_type="SOP")

    assert c1 > 0
    assert c2 > 0

    # Search for cleanroom disinfection
    res_cleanroom = store.search("sporicidal disinfectant contact time", limit=3)
    assert len(res_cleanroom) > 0
    assert res_cleanroom[0].doc_id == "SOP-MFG-014"

    # Search for chromatography
    res_hplc = store.search("HPLC system suitability peak area RSD", limit=3)
    assert len(res_hplc) > 0
    assert res_hplc[0].doc_id == "SOP-QC-028"

    # List documents
    docs = store.list_documents()
    assert len(docs) == 2
    doc_ids = [d["doc_id"] for d in docs]
    assert "SOP-MFG-014" in doc_ids
    assert "SOP-QC-028" in doc_ids

    # Delete document
    deleted = store.delete_document("SOP-QC-028")
    assert deleted is True
    res_after = store.search("HPLC system suitability", limit=3)
    assert not any(r.doc_id == "SOP-QC-028" for r in res_after)
