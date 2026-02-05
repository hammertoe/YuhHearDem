import asyncio
import importlib.util
import sys
from pathlib import Path

from rdflib import RDF

from models.entity import Entity
from sqlalchemy.exc import NoSuchTableError

from scripts.dump_knowledgebase_rdf import YHD, _RecordAdapter, _get_table_columns, build_graph


def test_build_graph_includes_entity_type():
    entity = Entity(
        entity_id="entity-1",
        entity_type="person",
        entity_subtype=None,
        name="Alice",
        canonical_name="Alice",
        aliases=[],
        description=None,
        importance_score=0.1,
        entity_confidence=None,
        source="test",
        source_ref=None,
        speaker_canonical_id=None,
        legislation_id=None,
        meta_data={},
        first_seen_date=None,
    )

    graph = build_graph(entities=[entity])

    subject = YHD["entity/entity-1"]
    assert (subject, RDF.type, YHD.Entity) in graph


def test_dump_script_imports_with_only_scripts_path(monkeypatch):
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    script_path = scripts_dir / "dump_knowledgebase_rdf.py"
    monkeypatch.setattr(sys, "path", [str(scripts_dir)])

    spec = importlib.util.spec_from_file_location("dump_knowledgebase_rdf", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)


def test_record_adapter_returns_none_for_missing_keys():
    adapter = _RecordAdapter({"legislation_id": "L1"})

    assert adapter.legislation_id == "L1"
    assert adapter.pdf_url is None


def test_get_table_columns_returns_empty_when_missing_table(monkeypatch):
    class FakeInspector:
        def get_columns(self, _table_name):
            raise NoSuchTableError("missing_table")

    def fake_inspect(_bind):
        return FakeInspector()

    class FakeSession:
        def __init__(self):
            self.bind = object()

        async def run_sync(self, func):
            return func(self)

    monkeypatch.setattr(
        "scripts.dump_knowledgebase_rdf.inspect",
        fake_inspect,
    )

    columns = asyncio.run(_get_table_columns(FakeSession(), "missing_table"))

    assert columns == set()
