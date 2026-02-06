# Plan: Clean-Slate Ingestor Schema + Pipeline

## Assumptions
- This repo is not in production; existing data and schema can be dropped.
- No Alembic migrations; schema is managed directly from SQLAlchemy models.
- The GraphRAG/search stack lives in another package and is removed here.
- YouTube videos must never be downloaded; ingest uses URLs only.

## Goals
- Implement the schema from `docs/INGESTOR_DESIGN.md` plus an `agenda_items` table.
- Generate stable, compact IDs during ingestion (no runtime heuristics).
- Persist explicit relationship evidence linking to exact transcript segments.
- Keep ingestion fast, robust, and aligned with the new prompt JSON format.

## Target Schema (summary)
- `sessions`: `session_id` (text PK), `date`, `title`, `sitting_number`, `chamber`, `created_at`.
- `videos`: `video_id` (text PK, YouTube ID), `session_id` FK, `platform`, `url`, `duration_seconds`, `created_at`.
- `speakers`: `speaker_id` (text PK), `name`, `title`, `role`, `chamber`, `aliases` (jsonb), `created_at`.
- `agenda_items` (new):
  - `agenda_item_id` (text PK, e.g., `{session_id}_a{index}`)
  - `session_id` FK
  - `agenda_index` (int)
  - `title` (text)
  - `description` (text, optional)
  - `primary_speaker` (text, optional)
  - `created_at`
- `transcript_segments`: `segment_id` (text PK), `session_id` FK, `video_id` FK, `speaker_id` FK, `start_time_seconds`, `end_time_seconds`, `text`, `agenda_item_id` FK (optional), `speech_block_index`, `segment_index`, `embedding` (vector/json), `embedding_model`, `created_at`.
- `entities`: `entity_id` (text PK), `name`, `canonical_name`, `entity_type`, `entity_subtype`, `description`, `aliases` (jsonb), `created_at`.
- `relationships`: `relationship_id` (UUID), `source_entity_id` FK, `target_entity_id` FK, `relation`, `description`, `confidence`, `created_at`.
- `relationship_evidence`: `evidence_id` (UUID), `relationship_id` FK, `segment_id` FK, `video_id` FK, `start_time_seconds`, `created_at`.
- Indexes: `relationship_evidence(relationship_id)`, `relationship_evidence(segment_id)`, `relationship_evidence(video_id, start_time_seconds)`, plus FKs and PKs.

## Work Plan (TDD, tidy-first)

### Completed
1. **Structural cleanup (no behavior changes)**
   - [X] Removed Alembic dependency and deleted all `migrations/` files.
   - [X] Removed GraphRAG/search services: `services/hybrid_graphrag.py`, `services/simplified_agent.py`, `services/query_entity_extractor.py`, `services/community_summarizer.py`, `storage/knowledge_graph_store.py`
   - [X] Removed GraphRAG scripts: `scripts/compute_communities.py`, `scripts/compute_graph_metrics.py`, `scripts/show_knowledge_graph.py`, `scripts/dump_knowledgebase_rdf.py`
   - [X] Removed GraphRAG and obsolete tests
   - [X] Removed obsolete models: `models/message.py`, `models/mention.py`, `models/community.py`, `models/legislation.py`, `models/order_paper.py`
   - [X] Removed `storage/` and `services/community_detection.py`, `services/parliamentary_agent_tools.py`, `scripts/dedupe_entities.py`
   - [X] Updated docs to remove migration references

2. **Define new models (tests first)**
   - [X] Added tests for stable ID formats (`session_id`, `segment_id`, `agenda_item_id`, `speaker_id`).
   - [X] Added tests for `relationship_evidence` linking to exact `segment_id`s.
   - [X] Added tests for `agenda_items` linking to `sessions` and `transcript_segments`.
   - [X] Implemented SQLAlchemy models: `Session`, `AgendaItem`, `Video`, `Speaker`, `TranscriptSegment`, `Entity`, `Relationship`, `RelationshipEvidence`.
   - [X] All new model tests passing

3. **Database reset flow**
   - [X] Added `scripts/reset_db.py` with `drop_all()` + `create_all()` using `Base.metadata`.

4. **Order paper ingestion updates** (pending)
   - Treat order papers as metadata seeders: upsert `sessions`, `speakers`, `agenda_items`.
   - Map agenda items by index and stable `agenda_item_id`.

5. **Video ingestion updates** (pending)
   - Upsert `sessions` + `videos` with `video_id = youtube_id`.
   - Write `transcript_segments` using `segment_id = {youtube_id}_{start_time_seconds:05d}`.
   - Attach `agenda_item_id` when agenda index is known.
   - Store embeddings and `embedding_model` metadata.

6. **Knowledge-graph extraction updates** (pending)
   - Extract entities and write `entities` with stable `entity_id`.
   - Extract relationships and write `relationships` with UUID `relationship_id`.
   - Persist one or more `relationship_evidence` rows per relationship, using segment map from ingestion.

7. **Docs + verification** (completed)
   - [X] Updated README/QUICKSTART/scripts docs to reflect new schema
   - [X] Updated scripts/README.md with new schema and ID formats
   - [X] All new model tests passing

## Notes / Decisions
- `agenda_items` is additive to the design; keep it minimal and order-paper-aligned.
- Prefer UUIDs for `relationship_id`/`evidence_id` for uniqueness, as allowed by the design.
- Avoid heuristic matching after ingestion; evidence is written only at ingest time.
