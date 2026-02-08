# Full Transcript Storage Implementation

## Overview
Added complete transcript sentence storage with normalized speakers, raw JSON backup, and search indexes.

---

## Database Changes

### New Table: `transcript_sentences`

Stores every sentence from parliamentary videos with:
- ✅ Full text (not truncated like mentions.context)
- ✅ Normalized speaker ID (canonical)
- ✅ Original speaker name (as spoken)
- ✅ Timestamp in seconds only (no "5m30s" strings)
- ✅ Vector embedding for semantic search
- ✅ Full-text search vector for keyword search
- ✅ Precise hierarchical location (session → agenda → speech → sentence)

### Updated Table: `sessions`

Added `raw_transcript_json` column (JSONB) to store:
- Complete structured transcript from Gemini API
- Enables reprocessing without video re-analysis
- Provides backup of original data

---

## Pipeline Changes

### New Step 5.5: Create Transcript Sentences

Located between agenda items and knowledge graph extraction:

```
Step 5/6: Create agenda items
Step 5.5/6: Create transcript sentence records  ← NEW
Step 6/6: Extract knowledge graph
```

### Speaker Normalization

**Before:** Speaker looked up once per session, speech blocks used cached ID
**After:** Every speech block triggers `speaker_service.get_or_create_speaker()`

**Benefits:**
- Catches speaker name variations ("Hon. Wickham" vs "Barlow Wickham")
- Creates aliases when speakers appear differently
- More robust deduplication

### Ingestion Flow

1. Extract transcript from video
2. Create Session record with `raw_transcript_json`
3. Create Video record
4. Process speakers → normalized IDs for each speech block
5. Create AgendaItem records
6. Create TranscriptSentence records (full text + normalized speakers)
7. Extract entities and create Mention records

---

## Search Capabilities

Now you can query:

### 1. Full Sentence for Mention

```sql
SELECT
    m.*,
    ts.full_text,  -- ✅ Complete, not truncated
    ts.speaker_name_normalized,
    ts.speaker_name_original
FROM mentions m
JOIN transcript_sentences ts ON
    m.session_id = ts.session_id
    AND m.agenda_item_index = ts.agenda_item_index
    AND m.speech_block_index = ts.speech_block_index
    AND m.sentence_index = ts.sentence_index
WHERE m.mention_id = 'uuid';
```

### 2. All Sentences by Speaker

```sql
SELECT
    full_text,
    timestamp_seconds,
    s.session_date,
    s.sitting_number
FROM transcript_sentences ts
JOIN sessions s ON ts.session_id = s.session_id
WHERE speaker_id = 'hon_barlow_wickham_abc123'
ORDER BY s.session_date DESC, ts.timestamp_seconds ASC;
```

### 3. Reconstruct Full Transcript

```sql
SELECT
    agenda_item_index,
    speech_block_index,
    sentence_index,
    speaker_name_normalized,
    full_text,
    timestamp_seconds
FROM transcript_sentences
WHERE session_id = 's_67_2024_01_15'
ORDER BY
    agenda_item_index,
    speech_block_index,
    sentence_index;
```

### 4. Semantic Search Over Sentences

```sql
SELECT
    sentence_id,
    full_text,
    speaker_name_normalized,
    (embedding <=> '[vector...]')::float AS similarity
FROM transcript_sentences
WHERE embedding IS NOT NULL
ORDER BY similarity ASC
LIMIT 20;
```

### 5. Keyword Search Over Sentences

```sql
SELECT
    sentence_id,
    full_text,
    speaker_name_normalized,
    ts_rank(search_vector, plainto_tsquery('cybercrime'))
FROM transcript_sentences
WHERE search_vector @@ plainto_tsquery('cybercrime')
ORDER BY ts_rank DESC
LIMIT 20;
```

---

## Indexes

Created for fast queries:

1. **uq_transcript_sentence_location** (unique)
   - Fields: session_id, agenda_item_index, speech_block_index, sentence_index
   - Purpose: Prevent duplicate sentences, fast lookups

2. **ix_transcript_sentences_speaker_time**
   - Fields: speaker_id, timestamp_seconds
   - Purpose: Query all speeches by speaker in chronological order

3. **ix_transcript_sentences_video_time**
   - Fields: video_id, timestamp_seconds
   - Purpose: Query sentences by video with timestamps

4. **ix_transcript_sentences_embedding** (ivfflat)
   - Fields: embedding
   - Purpose: Fast vector similarity search
   - Config: ivfflat with lists=100

5. **ix_transcript_sentences_search** (gin)
   - Fields: search_vector
   - Purpose: Fast full-text keyword search

---

## Storage Estimates

**Assuming:**
- 100 sessions
- 10 agenda items per session
- 5 speeches per agenda
- 10 sentences per speech

**Total:** 50,000 transcript sentences

**Per row:** ~450 bytes
- sentence_id: 16 bytes
- location fields: ~80 bytes
- speakers: ~100 bytes
- full_text: ~150 bytes avg
- timestamp_seconds: 4 bytes
- embedding (768 floats): ~3000 bytes (optional, NULL until generated)
- search_vector: ~100 bytes (optional, NULL until generated)

**Total for 50K rows:** ~22 MB
**Raw JSON storage:** ~15 MB (compressed JSONB)

**Total overhead:** ~37 MB (negligible)

---

## Migration Path

### Phase 1: Initialize New Table

```bash
python scripts/init_database.py
```

This automatically creates:
- transcript_sentences table with all columns and indexes
- raw_transcript_json column on sessions table

### Phase 2: Reingest Data

**Option A: Start Fresh**
```bash
# Wipe and reingest one session (for testing)
python scripts/ingest_video_unified.py \
  --url "https://youtube.com/watch?v=..." \
  --date 2024-01-15 \
  --chamber senate \
  --sitting 67 \
  --minutes 10 \
  --verbose
```

**Option B: Backfill Existing** (if you have existing data)

1. Export raw transcripts from JSON files
2. Run ingestion with `--raw-transcript` flag (not yet implemented)
3. Or write a script to backfill from sessions.raw_transcript_json

### Phase 3: Generate Embeddings (Optional)

Embeddings are stored as NULL initially. To generate:

**Option A: On-demand in UI**
- When user searches, generate embedding for query + sentences
- Store generated embeddings back to database

**Option B: Batch generation script**
```python
# Create script: scripts/generate_transcript_embeddings.py
# Generates embeddings for all transcript_sentence.embedding IS NULL
# Batch size: 100-500 sentences
```

---

## Benefits

1. ✅ **Complete transcript preservation** - Can reconstruct entire session
2. ✅ **Normalized speakers** - Consistent references, catches variations
3. ✅ **Reprocessing capability** - Raw JSON stored for future pipeline updates
4. ✅ **Rich queries** - "What did X say?", "Search transcript", "Timeline view"
5. ✅ **No truncation** - UI gets complete sentences, not 200-char snippets
6. ✅ **Semantic search** - Vector embeddings enable concept-based search
7. ✅ **Keyword search** - Full-text vectors enable fast ranked results

---

## Next Steps (Not Implemented)

### High Priority
1. ✅ DONE - Create transcript_sentences table
2. ✅ DONE - Add to ingestion pipeline
3. ⏳ Generate embeddings for sentences (optional, on-demand)
4. ⏳ Create full-text search vectors (needs trigger)
5. ⏳ Write backfill script for existing data

### Medium Priority
1. ⏳ Add transcript_sentence.full_text to search_vector via trigger
2. ⏳ Create script to generate embeddings for all sentences
3. ⏳ Add API endpoint for transcript sentence search
4. ⏳ Add API endpoint for speaker timeline queries

---

## Testing

```bash
# Test with short video to verify everything works
python scripts/ingest_video_unified.py \
  --url "https://youtube.com/watch?v=..." \
  --date 2024-01-15 \
  --chamber senate \
  --sitting 67 \
  --minutes 5 \
  --verbose \
  --no-thinking

# Check database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM transcript_sentences;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM transcript_sentences WHERE embedding IS NOT NULL;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM transcript_sentences WHERE search_vector IS NOT NULL;"

# Reconstruct full transcript
psql $DATABASE_URL -c "SELECT speaker_name_normalized, full_text FROM transcript_sentences WHERE session_id = 's_67_2024_01_15' ORDER BY timestamp_seconds;"
```

---

## Implementation Details

### Files Changed

1. **models/transcript_sentence.py** (NEW)
   - TranscriptSentence model with all indexes

2. **models/session.py** (UPDATED)
   - Added raw_transcript_json column

3. **models/__init__.py** (UPDATED)
   - Exported TranscriptSentence

4. **services/unified_ingestion.py** (UPDATED)
   - Added EmbeddingService
   - Added _create_transcript_sentences method
   - Added _count_sentences helper
   - Updated _create_session to store JSON
   - Inserted Step 5.5 into pipeline
   - Normalize speakers for every speech block

### Key Design Decisions

1. **Speaker normalization frequency**: Every speech block (not once per session)
   - **Why**: Catches variations in speaker names
   - **Tradeoff**: Slightly slower ingestion

2. **Timestamp format**: Seconds only (int)
   - **Why**: Simpler, sortable, no parsing needed
   - **Tradeoff**: Less human-readable in database

3. **Embeddings initially NULL**: Generated on-demand or via batch script
   - **Why**: Faster initial ingestion
   - **Tradeoff**: First semantic search slower until embeddings generated

4. **Full-text search vector initially NULL**: Needs trigger or batch update
   - **Why**: Faster ingestion
   - **Tradeoff**: First keyword search falls back to ILIKE

---

## FAQ

**Q: Can I still search entities?**
A: Yes, entity search unchanged. Sentence search is ADDITIONAL capability.

**Q: Will this slow down ingestion?**
A: Minimal impact. Speaker normalization happens quickly (cached). No embeddings = fast.

**Q: How do I backfill existing data?**
A: Need to write script that:
1. Reads sessions.raw_transcript_json
2. Processes through _create_transcript_sentences logic
3. Inserts into transcript_sentences

**Q: When should I generate embeddings?**
A: Depends on use case:
- If searching transcripts frequently → generate embeddings ASAP
- If searching entities primarily → generate on-demand

**Q: Can I reprocess with better pipeline later?**
A: Yes! Raw JSON stored. Just write script that:
1. Reads sessions.raw_transcript_json
2. Runs through improved pipeline
3. Updates entities, relationships, mentions

---

## Verdict

✅ **Implementation complete.**

**Committed:** `a2daf5b`

**Ready for:**
- Testing with short video
- Full transcript queries
- Speaker timeline searches
- Semantic search (after embeddings generated)
- Keyword search (after search vectors generated)
