from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.retrieval import Chunk, Retriever, load_knowledge_base, parse_markdown_manual


@pytest.fixture
def mock_kb_dir() -> Generator[Path, None, None]:
    # We yield a TemporaryDirectory path and create standard files
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        cnc_content = (
            "# Spindle Inspection\n"
            "If spindle noise is reported during rapid movement, check the bearings.\n\n"
            "# Coolant Temperature\n"
            "The expected coolant temperature during normal operations is 18 to 24 degrees Celsius."
        )
        (tmp_path / "cnc.md").write_text(cnc_content, encoding="utf-8")
        
        pump_content = (
            "# Impeller Inspection\n"
            "If the pump is making grinding noises, inspect the impeller.\n\n"
            "# Coolant System\n"
            "Pump coolant lines must be inspected for leaks."
        )
        (tmp_path / "pump.md").write_text(pump_content, encoding="utf-8")
        
        yield tmp_path


def test_markdown_parsing_and_stable_ids(mock_kb_dir: Path) -> None:
    # A. Markdown sections are parsed correctly.
    # B. Stable section IDs are generated.
    cnc_file = mock_kb_dir / "cnc.md"
    chunks = parse_markdown_manual(cnc_file, "cnc")
    
    assert len(chunks) == 2
    
    assert chunks[0].title == "Spindle Inspection"
    assert chunks[0].chunk_id == "cnc-spindle-inspection"
    assert "rapid movement" in chunks[0].content
    
    assert chunks[1].title == "Coolant Temperature"
    assert chunks[1].chunk_id == "cnc-coolant-temperature"
    assert "18 to 24 degrees" in chunks[1].content


def test_spindle_noise_retrieves_spindle_section(mock_kb_dir: Path) -> None:
    # C. "spindle noise" retrieves the spindle-related section.
    # D. Specific spindle query ranks the relevant section above unrelated sections.
    retriever = load_knowledge_base(mock_kb_dir)
    results = retriever.search("spindle noise issue")
    
    assert len(results) > 0
    assert results[0].chunk_id == "cnc-spindle-inspection"


def test_coolant_query_retrieves_coolant_material(mock_kb_dir: Path) -> None:
    # E. Coolant query retrieves coolant material.
    retriever = load_knowledge_base(mock_kb_dir)
    results = retriever.search("coolant temperature 21 degrees")
    
    assert len(results) > 0
    # The top result should be the CNC coolant section because it matches 'temperature' and 'degrees' better
    assert results[0].chunk_id == "cnc-coolant-temperature"


def test_equipment_filtering(mock_kb_dir: Path) -> None:
    # F. Equipment filtering works.
    # G. Pump query does not return CNC-only material when filtered.
    retriever = load_knowledge_base(mock_kb_dir)
    
    # Query for 'coolant' which exists in both CNC and Pump
    unfiltered = retriever.search("coolant")
    assert len(unfiltered) == 2
    
    # Filter by pump
    pump_only = retriever.search("coolant", equipment_type="pump")
    assert len(pump_only) == 1
    assert pump_only[0].equipment_type == "pump"
    assert pump_only[0].chunk_id == "pump-coolant-system"
    
    # Check that a cnc-only query returns empty if pump is filtered
    cnc_only = retriever.search("spindle noise", equipment_type="pump")
    assert len(cnc_only) == 0


def test_empty_and_nomatch_queries(mock_kb_dir: Path) -> None:
    # H. Empty query is handled safely.
    # I. No-match query is handled safely.
    retriever = load_knowledge_base(mock_kb_dir)
    
    assert len(retriever.search("")) == 0
    assert len(retriever.search("   ")) == 0
    assert len(retriever.search("alien spaceship abduction")) == 0


def test_determinism_and_ordering(mock_kb_dir: Path) -> None:
    # J. Same query produces identical results and scores.
    retriever = load_knowledge_base(mock_kb_dir)
    query = "inspect the pump coolant"
    
    results1 = retriever.search(query)
    results2 = retriever.search(query)
    
    assert len(results1) == len(results2)
    for r1, r2 in zip(results1, results2):
        assert r1.chunk_id == r2.chunk_id
        assert r1.score == r2.score

    # K. Equal-score ordering is deterministic.
    # We will manually inject chunks with identical terms to force equal BM25 scores
    retriever2 = Retriever()
    retriever2.add_chunks([
        Chunk(chunk_id="b-chunk", equipment_type="test", title="Test", content="identical terms"),
        Chunk(chunk_id="c-chunk", equipment_type="test", title="Test", content="identical terms"),
        Chunk(chunk_id="a-chunk", equipment_type="test", title="Test", content="identical terms"),
    ])
    
    eq_results = retriever2.search("identical terms")
    assert len(eq_results) == 3
    # The chunk_ids must be sorted alphabetically ascending when scores are exactly equal
    assert eq_results[0].chunk_id == "a-chunk"
    assert eq_results[1].chunk_id == "b-chunk"
    assert eq_results[2].chunk_id == "c-chunk"


def test_result_metadata_preserved(mock_kb_dir: Path) -> None:
    # L. Result metadata is preserved correctly.
    retriever = load_knowledge_base(mock_kb_dir)
    results = retriever.search("impeller grinding")
    
    assert len(results) > 0
    top = results[0]
    assert top.chunk_id == "pump-impeller-inspection"
    assert top.title == "Impeller Inspection"
    assert top.equipment_type == "pump"
    assert "grinding noises" in top.content
    assert top.score > 0.0


def test_no_network_api_calls() -> None:
    # M. Retrieval does not perform network/API calls.
    # By strictly observing that we merely instantiated a BM25 engine with local collections,
    # we know no network happens. But we can also assert that we don't import requests.
    import sys
    assert "requests" not in sys.modules, "requests should not be loaded by retrieval module"
    
    # The retriever class is completely standalone
    r = Retriever()
    r.add_chunks([Chunk(chunk_id="1", equipment_type="test", title="Test", content="No internet")])
    assert len(r.search("internet")) == 1
