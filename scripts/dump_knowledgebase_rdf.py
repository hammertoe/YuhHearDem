"""Dump the knowledge base to RDF Turtle (TTL)."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, cast
from urllib.parse import quote
import sys

from dotenv import load_dotenv
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD
from sqlalchemy import select, inspect, Table, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import NoSuchTableError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.database import get_session_maker
from models import (
    Entity,
    Legislation,
    Mention,
    OrderPaper,
    Relationship,
    Speaker,
    TranscriptSegment,
    Video,
)

DEFAULT_BASE_URI = "https://yuhheardem.org/"
YHD = Namespace(DEFAULT_BASE_URI)
RDF_JSON = URIRef(str(RDF) + "JSON")


class _RecordAdapter:
    def __init__(self, mapping: dict):
        self._mapping = mapping

    def __getattr__(self, name: str):
        return self._mapping.get(name)


def build_graph(
    *,
    base_uri: str = DEFAULT_BASE_URI,
    videos: Iterable[Video] | None = None,
    speakers: Iterable[Speaker] | None = None,
    entities: Iterable[Entity] | None = None,
    relationships: Iterable[Relationship] | None = None,
    mentions: Iterable[Mention] | None = None,
    order_papers: Iterable[OrderPaper] | None = None,
    transcript_segments: Iterable[TranscriptSegment] | None = None,
    legislation: Iterable[Legislation] | None = None,
) -> Graph:
    """Build an RDF graph from model records."""
    graph = Graph()
    namespace = Namespace(base_uri)
    graph.bind("yhd", namespace)
    graph.bind("rdf", RDF)
    graph.bind("xsd", XSD)

    for video in videos or []:
        _add_video(graph, namespace, video)
    for speaker in speakers or []:
        _add_speaker(graph, namespace, speaker)
    for entity in entities or []:
        _add_entity(graph, namespace, entity)
    for relationship in relationships or []:
        _add_relationship(graph, namespace, relationship)
    for mention in mentions or []:
        _add_mention(graph, namespace, mention)
    for order_paper in order_papers or []:
        _add_order_paper(graph, namespace, order_paper)
    for segment in transcript_segments or []:
        _add_transcript_segment(graph, namespace, segment)
    for law in legislation or []:
        _add_legislation(graph, namespace, law)

    return graph


def _add_literal(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    value: object | None,
    *,
    datatype: URIRef | None = None,
) -> None:
    if value is None:
        return
    if isinstance(value, datetime):
        graph.add((subject, predicate, Literal(value.isoformat(), datatype=XSD.dateTime)))
        return
    if isinstance(value, date):
        graph.add((subject, predicate, Literal(value.isoformat(), datatype=XSD.date)))
        return
    if isinstance(value, (list, dict)):
        json_value = json.dumps(value, ensure_ascii=True)
        graph.add((subject, predicate, Literal(json_value, datatype=RDF_JSON)))
        return
    graph.add((subject, predicate, Literal(value, datatype=datatype)))


def _resource(namespace: Namespace, path: str) -> URIRef:
    safe_path = quote(path, safe="/:")
    return namespace[safe_path]


def _add_video(graph: Graph, namespace: Namespace, video: Video) -> None:
    """Add a video resource."""
    subject = _resource(namespace, f"video/{video.id}")
    graph.add((subject, RDF.type, namespace.Video))
    _add_literal(graph, subject, namespace.youtubeId, video.youtube_id)
    _add_literal(graph, subject, namespace.youtubeUrl, video.youtube_url)
    _add_literal(graph, subject, namespace.title, video.title)
    _add_literal(graph, subject, namespace.chamber, video.chamber)
    _add_literal(graph, subject, namespace.sessionDate, video.session_date)
    _add_literal(graph, subject, namespace.sittingNumber, video.sitting_number)
    _add_literal(graph, subject, namespace.durationSeconds, video.duration_seconds)
    _add_literal(graph, subject, namespace.transcript, video.transcript)
    _add_literal(graph, subject, namespace.transcriptProcessedAt, video.transcript_processed_at)
    _add_literal(graph, subject, namespace.createdAt, video.created_at)
    _add_literal(graph, subject, namespace.updatedAt, video.updated_at)
    if video.order_paper_id:
        order_paper = _resource(namespace, f"order-paper/{video.order_paper_id}")
        graph.add((subject, namespace.orderPaper, order_paper))


def _add_speaker(graph: Graph, namespace: Namespace, speaker: Speaker) -> None:
    """Add a speaker resource."""
    subject = _resource(namespace, f"speaker/{speaker.canonical_id}")
    graph.add((subject, RDF.type, namespace.Speaker))
    _add_literal(graph, subject, namespace.canonicalId, speaker.canonical_id)
    _add_literal(graph, subject, namespace.name, speaker.name)
    _add_literal(graph, subject, namespace.title, speaker.title)
    _add_literal(graph, subject, namespace.role, speaker.role)
    _add_literal(graph, subject, namespace.chamber, speaker.chamber)
    _add_literal(graph, subject, namespace.aliases, speaker.aliases)
    _add_literal(graph, subject, namespace.pronoun, speaker.pronoun)
    _add_literal(graph, subject, namespace.gender, speaker.gender)
    _add_literal(graph, subject, namespace.firstSeenDate, speaker.first_seen_date)
    _add_literal(graph, subject, namespace.metaData, speaker.meta_data)
    _add_literal(graph, subject, namespace.createdAt, speaker.created_at)
    _add_literal(graph, subject, namespace.updatedAt, speaker.updated_at)


def _add_entity(graph: Graph, namespace: Namespace, entity: Entity) -> None:
    """Add an entity resource."""
    subject = _resource(namespace, f"entity/{entity.entity_id}")
    graph.add((subject, RDF.type, namespace.Entity))
    _add_literal(graph, subject, namespace.entityId, entity.entity_id)
    _add_literal(graph, subject, namespace.entityType, entity.entity_type)
    _add_literal(graph, subject, namespace.entitySubtype, entity.entity_subtype)
    _add_literal(graph, subject, namespace.name, entity.name)
    _add_literal(graph, subject, namespace.canonicalName, entity.canonical_name)
    _add_literal(graph, subject, namespace.aliases, entity.aliases)
    _add_literal(graph, subject, namespace.description, entity.description)
    _add_literal(graph, subject, namespace.importanceScore, entity.importance_score)
    _add_literal(graph, subject, namespace.entityConfidence, entity.entity_confidence)
    _add_literal(graph, subject, namespace.source, entity.source)
    _add_literal(graph, subject, namespace.sourceRef, entity.source_ref)
    _add_literal(graph, subject, namespace.speakerCanonicalId, entity.speaker_canonical_id)
    _add_literal(graph, subject, namespace.metaData, entity.meta_data)
    _add_literal(graph, subject, namespace.firstSeenDate, entity.first_seen_date)
    _add_literal(graph, subject, namespace.createdAt, entity.created_at)
    _add_literal(graph, subject, namespace.updatedAt, entity.updated_at)
    if entity.legislation_id:
        law = _resource(namespace, f"legislation/{entity.legislation_id}")
        graph.add((subject, namespace.legislation, law))


def _add_relationship(graph: Graph, namespace: Namespace, relationship: Relationship) -> None:
    """Add a relationship resource."""
    subject = _resource(namespace, f"relationship/{relationship.id}")
    graph.add((subject, RDF.type, namespace.Relationship))
    source = _resource(namespace, f"entity/{relationship.source_id}")
    target = _resource(namespace, f"entity/{relationship.target_id}")
    graph.add((subject, namespace.sourceEntity, source))
    graph.add((subject, namespace.targetEntity, target))
    _add_literal(graph, subject, namespace.relationType, relationship.relation_type)
    _add_literal(graph, subject, namespace.sentiment, relationship.sentiment)
    _add_literal(graph, subject, namespace.evidence, relationship.evidence)
    _add_literal(graph, subject, namespace.confidence, relationship.confidence)
    _add_literal(graph, subject, namespace.source, relationship.source)
    _add_literal(graph, subject, namespace.sourceRef, relationship.source_ref)
    _add_literal(graph, subject, namespace.timestampSeconds, relationship.timestamp_seconds)
    _add_literal(graph, subject, namespace.createdAt, relationship.created_at)
    if relationship.video_id:
        video = _resource(namespace, f"video/{relationship.video_id}")
        graph.add((subject, namespace.video, video))


def _add_mention(graph: Graph, namespace: Namespace, mention: Mention) -> None:
    """Add a mention resource."""
    subject = _resource(namespace, f"mention/{mention.id}")
    graph.add((subject, RDF.type, namespace.Mention))
    entity = _resource(namespace, f"entity/{mention.entity_id}")
    video = _resource(namespace, f"video/{mention.video_id}")
    graph.add((subject, namespace.entity, entity))
    graph.add((subject, namespace.video, video))
    _add_literal(graph, subject, namespace.agendaItemIndex, mention.agenda_item_index)
    _add_literal(graph, subject, namespace.speechBlockIndex, mention.speech_block_index)
    _add_literal(graph, subject, namespace.sentenceIndex, mention.sentence_index)
    _add_literal(graph, subject, namespace.timestampSeconds, mention.timestamp_seconds)
    _add_literal(graph, subject, namespace.context, mention.context)
    _add_literal(graph, subject, namespace.billId, mention.bill_id)
    _add_literal(graph, subject, namespace.speakerId, mention.speaker_id)
    _add_literal(graph, subject, namespace.speakerCanonicalId, mention.speaker_canonical_id)
    _add_literal(graph, subject, namespace.agendaTitle, mention.agenda_title)
    _add_literal(graph, subject, namespace.segmentId, mention.segment_id)
    _add_literal(graph, subject, namespace.createdAt, mention.created_at)


def _add_order_paper(graph: Graph, namespace: Namespace, order_paper: OrderPaper) -> None:
    """Add an order paper resource."""
    subject = _resource(namespace, f"order-paper/{order_paper.id}")
    graph.add((subject, RDF.type, namespace.OrderPaper))
    _add_literal(graph, subject, namespace.pdfPath, order_paper.pdf_path)
    _add_literal(graph, subject, namespace.pdfHash, order_paper.pdf_hash)
    _add_literal(graph, subject, namespace.sessionTitle, order_paper.session_title)
    _add_literal(graph, subject, namespace.sessionDate, order_paper.session_date)
    _add_literal(graph, subject, namespace.sittingNumber, order_paper.sitting_number)
    _add_literal(graph, subject, namespace.chamber, order_paper.chamber)
    _add_literal(graph, subject, namespace.speakers, order_paper.speakers)
    _add_literal(graph, subject, namespace.agendaItems, order_paper.agenda_items)
    _add_literal(graph, subject, namespace.parsedAt, order_paper.parsed_at)


def _add_transcript_segment(
    graph: Graph,
    namespace: Namespace,
    segment: TranscriptSegment,
) -> None:
    """Add a transcript segment resource."""
    subject = _resource(namespace, f"transcript-segment/{segment.id}")
    graph.add((subject, RDF.type, namespace.TranscriptSegment))
    video = _resource(namespace, f"video/{segment.video_id}")
    graph.add((subject, namespace.video, video))
    _add_literal(graph, subject, namespace.segmentId, segment.segment_id)
    _add_literal(graph, subject, namespace.agendaItemIndex, segment.agenda_item_index)
    _add_literal(graph, subject, namespace.speechBlockIndex, segment.speech_block_index)
    _add_literal(graph, subject, namespace.segmentIndex, segment.segment_index)
    _add_literal(graph, subject, namespace.startTimeSeconds, segment.start_time_seconds)
    _add_literal(graph, subject, namespace.endTimeSeconds, segment.end_time_seconds)
    _add_literal(graph, subject, namespace.text, segment.text)
    _add_literal(graph, subject, namespace.embeddingModel, segment.embedding_model)
    _add_literal(graph, subject, namespace.embeddingVersion, segment.embedding_version)
    _add_literal(graph, subject, namespace.embedding, segment.embedding)
    _add_literal(graph, subject, namespace.metaData, segment.meta_data)
    _add_literal(graph, subject, namespace.createdAt, segment.created_at)
    if segment.speaker_id:
        speaker = _resource(namespace, f"speaker/{segment.speaker_id}")
        graph.add((subject, namespace.speaker, speaker))


def _add_legislation(graph: Graph, namespace: Namespace, law: Legislation) -> None:
    """Add a legislation resource."""
    subject = _resource(namespace, f"legislation/{law.legislation_id}")
    graph.add((subject, RDF.type, namespace.Legislation))
    _add_literal(graph, subject, namespace.legislationId, law.legislation_id)
    _add_literal(graph, subject, namespace.title, law.title)
    _add_literal(graph, subject, namespace.type, law.type)
    _add_literal(graph, subject, namespace.status, law.status)
    _add_literal(graph, subject, namespace.sponsors, law.sponsors)
    _add_literal(graph, subject, namespace.chamber, law.chamber)
    _add_literal(graph, subject, namespace.parliamentId, law.parliament_id)
    _add_literal(graph, subject, namespace.pdfUrl, law.pdf_url)
    _add_literal(graph, subject, namespace.description, law.description)
    _add_literal(graph, subject, namespace.stages, law.stages)
    _add_literal(graph, subject, namespace.scrapedAt, law.scraped_at)
    _add_literal(graph, subject, namespace.updatedAt, law.updated_at)


async def dump_to_ttl(
    *,
    output_path: Path,
    base_uri: str,
) -> None:
    """Dump the knowledge base to a Turtle file."""
    session_maker = cast(async_sessionmaker[AsyncSession], get_session_maker())
    if session_maker is None:
        raise RuntimeError("Database session maker is not initialized")
    graph = build_graph(base_uri=base_uri)

    async with session_maker() as session:
        for model, handler, table_name in (
            (Video, _add_video, "videos"),
            (Speaker, _add_speaker, "speakers"),
            (Entity, _add_entity, "entities"),
            (Relationship, _add_relationship, "relationships"),
            (Mention, _add_mention, "mentions"),
            (OrderPaper, _add_order_paper, "order_papers"),
            (TranscriptSegment, _add_transcript_segment, "transcript_segments"),
            (Legislation, _add_legislation, "legislation"),
        ):
            await _dump_model(session, graph, Namespace(base_uri), model, handler, table_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(output_path), format="turtle")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump knowledge base to RDF Turtle")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("processed/knowledgebase.ttl"),
        help="Output TTL path (default: processed/knowledgebase.ttl)",
    )
    parser.add_argument(
        "--base-uri",
        default=DEFAULT_BASE_URI,
        help=f"Base URI for RDF resources (default: {DEFAULT_BASE_URI})",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this run",
    )
    return parser.parse_args()


async def _dump_model(
    session,
    graph: Graph,
    namespace: Namespace,
    model,
    handler,
    table_name: str,
) -> None:
    db_columns = await _get_table_columns(session, table_name)
    if not db_columns:
        return

    model_columns = set(model.__table__.columns.keys())
    if model_columns.issubset(db_columns):
        result = await session.stream(select(model))
        async for record in result.scalars():
            handler(graph, namespace, record)
        return

    table = await _get_reflected_table(session, table_name)
    result = await session.stream(select(table))
    async for row in result:
        handler(graph, namespace, _RecordAdapter(dict(row._mapping)))


async def _get_table_columns(session, table_name: str) -> set[str]:
    def _inspect(sync_session):
        inspector = inspect(sync_session.bind)
        try:
            return {column["name"] for column in inspector.get_columns(table_name)}
        except NoSuchTableError:
            return set()

    return await session.run_sync(_inspect)


async def _get_reflected_table(session, table_name: str) -> Table:
    def _reflect(sync_session):
        metadata = MetaData()
        return Table(table_name, metadata, autoload_with=sync_session.bind)

    return await session.run_sync(_reflect)


async def main() -> None:
    """CLI entry point."""
    load_dotenv()
    args = _parse_args()
    if args.database_url:
        import os

        os.environ["DATABASE_URL"] = args.database_url

    await dump_to_ttl(output_path=args.output, base_uri=args.base_uri)


if __name__ == "__main__":
    asyncio.run(main())
