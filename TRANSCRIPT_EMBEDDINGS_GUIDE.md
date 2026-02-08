# Transcript Sentence Embeddings Guide

## Overview
Embeddings for transcript sentences are generated **after ingestion**, not during it. This keeps ingestion fast and allows batch processing.

---

## When to Generate Embeddings

### Recommended Timeline

**Phase 1: Initial Ingestion (No Embeddings)**
```bash
# Ingest videos quickly
python scripts/ingest_video_unified.py \
  --url "https://youtube.com/watch?v=..." \
  --date 2024-01-15 \
  --chamber house \
  --sitting 125 \
  --minutes 10 \
  --no-thinking
```
**Result:**
- ✅ Fast ingestion (no embedding API calls)
- ⚠️ Semantic search disabled (sentences have embedding=NULL)
- ⚠️ Keyword search disabled (sentences have search_vector=NULL)

**Phase 2: Generate Embeddings (Batch Processing)**
```bash
# Generate embeddings for all sentences
python scripts/generate_transcript_embeddings.py

# Or test with just 100 sentences first
python scripts/generate_transcript_embeddings.py --limit 100
```
**Result:**
- ✅ Semantic search enabled (sentences have embeddings)
- ✅ Keyword search enabled (sentences have search_vectors)
- ✅ Fast batch processing (100 sentences per API call)
- ⚠️ Takes time (depending on sentence count)

---

## Quick Start (Keyword Search Only)

If you only need **keyword search** (not semantic), use the fast mode:

```bash
# No API calls - generates search vectors locally
python scripts/generate_transcript_embeddings.py --fulltext-only
```

**Speed:** ~1000-5000 sentences/minute (no API overhead)

---

## Usage

### Full Embeddings (Semantic + Keyword Search)

```bash
# Process all sentences
python scripts/generate_transcript_embeddings.py

# Process first 1000 sentences (for testing)
python scripts/generate_transcript_embeddings.py --limit 1000

# Use custom batch size (default: 100)
python scripts/generate_transcript_embeddings.py --batch-size 500
```

**What it does:**
1. Fetches all `transcript_sentences` where `embedding IS NULL`
2. Generates vector embeddings via Gemini API (100 at a time)
3. Generates full-text search vectors (English dictionary)
4. Updates both columns in database
5. Reports progress and statistics

**Sample Output:**
```
Found 5234 transcript sentences without embeddings
Batch size: 100

Processing batch 1/53 (100 sentences)...
  Processed: 100  Errors: 0  Progress: 1.9%

Processing batch 2/53 (100 sentences)...
  Processed: 100  Errors: 0  Progress: 3.8%

...

============================================================
Embedding Generation Complete!
============================================================
Total sentences: 5234
Processed: 5234
Errors: 0
Batch count: 53
Success rate: 100.0%

Remaining sentences without embeddings: 0
```

### Keyword Search Only (Fast Mode)

```bash
# Generate only search vectors (no API calls)
python scripts/generate_transcript_embeddings.py --fulltext-only

# Test with 500 sentences first
python scripts/generate_transcript_embeddings.py --fulltext-only --limit 500
```

**What it does:**
1. Fetches all `transcript_sentences` where `search_vector IS NULL`
2. Generates full-text search vectors locally (no API calls)
3. Updates `search_vector` column
4. Reports progress

**Sample Output:**
```
Found 5234 sentences without full-text search vectors
Generating vectors (no API calls)...

Processing batch 1/53 (100 sentences)...
  Processed: 100  Progress: 1.9%

...

============================================================
Full-Text Vector Generation Complete!
============================================================
Total sentences: 5234
Processed: 5234
Batch count: 53

✓ Semantic search not available (run without --fulltext-only for faster)
```

---

## Search Capabilities After Embeddings

### Semantic Search (Over Full Text)

```sql
SELECT
    ts.sentence_id,
    ts.full_text,
    ts.speaker_name_normalized,
    ts.timestamp_seconds,
    s.session_date,
    (ts.embedding <=> '[query_embedding...]')::float AS similarity
FROM transcript_sentences ts
JOIN sessions s ON ts.session_id = s.session_id
WHERE ts.embedding IS NOT NULL
ORDER BY similarity ASC
LIMIT 20;
```

**Use case:** "Find sentences about **digital security**" (conceptual match)

### Keyword Search (Over Full Text)

```sql
SELECT
    ts.sentence_id,
    ts.full_text,
    ts.speaker_name_normalized,
    ts.timestamp_seconds,
    ts_rank(ts.search_vector, plainto_tsquery('cybercrime')) AS rank
FROM transcript_sentences ts
WHERE ts.search_vector IS NOT NULL
ORDER BY rank DESC
LIMIT 20;
```

**Use case:** "Find sentences containing **cybercrime**" (keyword match)

### Speaker Timeline (With Full Sentences)

```sql
SELECT
    ts.full_text,
    ts.timestamp_seconds,
    s.session_date,
    s.sitting_number
FROM transcript_sentences ts
JOIN sessions s ON ts.session_id = s.session_id
WHERE
    ts.speaker_id = 'hon_barlow_wickham_abc123'
    AND ts.speaker_id IS NOT NULL
ORDER BY s.session_date DESC, ts.timestamp_seconds ASC;
```

**Use case:** "What did **Hon. Barlow Wickham** say across all sessions?"

---

## Performance

### Full Embeddings (API Calls)

**Estimates:**
- Batch size: 100 sentences
- API time per batch: ~2-5 seconds
- Processing rate: ~20-50 sentences/second

**Example for 5,000 sentences:**
- Total time: ~100-250 seconds (2-4 minutes)
- API calls: ~50 batches

### Keyword Search Only (No API Calls)

**Estimates:**
- Batch size: 100 sentences
- Processing rate: ~1000-5000 sentences/second

**Example for 5,000 sentences:**
- Total time: ~1-5 seconds
- API calls: 0

---

## Cost Optimization

### Recommended Strategy

**1. Start with keyword search only**
```bash
# Fast first pass (no API costs)
python scripts/generate_transcript_embeddings.py --fulltext-only
```
- ✅ Immediate keyword search capability
- ✅ Zero API costs
- ✅ Very fast (seconds for thousands of sentences)

**2. Generate semantic embeddings on-demand**
```bash
# Generate embeddings only for popular sessions or recent data
python scripts/generate_transcript_embeddings.py --limit 1000
```
- ✅ Semantic search for key content
- ✅ Controlled API costs
- ✅ Gradual rollout

**3. Full embeddings when needed**
```bash
# Generate all embeddings for complete semantic search
python scripts/generate_transcript_embeddings.py
```
- ✅ Complete semantic search
- ✅ One-time cost
- ✅ Future-proof

---

## Monitoring

### Check Embedding Status

```bash
# How many sentences have embeddings?
psql $DATABASE_URL -c "SELECT
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
    COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding
FROM transcript_sentences;"

# How many have search vectors?
psql $DATABASE_URL -c "SELECT
    COUNT(*) FILTER (WHERE search_vector IS NOT NULL) as with_search_vector,
    COUNT(*) FILTER (WHERE search_vector IS NULL) as without_search_vector
FROM transcript_sentences;"

# Breakdown by session
psql $DATABASE_URL -c "SELECT
    s.session_id,
    s.session_date,
    COUNT(*) FILTER (WHERE ts.embedding IS NOT NULL) as embedded,
    COUNT(*) FILTER (WHERE ts.embedding IS NULL) as not_embedded
FROM sessions s
JOIN transcript_sentences ts ON s.session_id = ts.session_id
GROUP BY s.session_id, s.session_date
ORDER BY s.session_date DESC;"
```

### Verify Search Works

```bash
# Test semantic search
psql $DATABASE_URL -c "
SELECT full_text, speaker_name_normalized
FROM transcript_sentences
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.1, 0.2, ...]'::float
LIMIT 5;"

# Test keyword search
psql $DATABASE_URL -c "
SELECT full_text, speaker_name_normalized
FROM transcript_sentences
WHERE search_vector @@ plainto_tsquery('cybercrime')
LIMIT 5;"
```

---

## Troubleshooting

### "No transcript sentences found without embeddings"

**Cause:** All sentences already have embeddings
**Fix:**
```bash
# Check if you've already generated embeddings
psql $DATABASE_URL -c "SELECT COUNT(*) FROM transcript_sentences WHERE embedding IS NOT NULL;"
```

### "Error processing batch"

**Cause:** API rate limit or database connection issue
**Fix:**
1. Reduce batch size: `--batch-size 50`
2. Check GOOGLE_API_KEY is set
3. Run script again (continues where it left off)

### "Embeddings are NULL after script completes"

**Cause:** Rollback occurred on error
**Fix:**
1. Check script output for errors
2. Verify transaction committed successfully
3. Run script again

---

## API Model Used

**Embedding Model:** `text-embedding-004`
- Dimensions: 768
- Fast, high-quality embeddings
- Same model used for entity embeddings

**Full-Text Model:** Built-in PostgreSQL `to_tsvector('english', ...)`
- No API calls
- Fast local generation
- Good for keyword search

---

## Integration with UI

### Initial State (Ingestion Complete)

```json
{
  "search_capabilities": {
    "semantic": false,
    "keyword": false
  },
  "message": "Run embeddings script to enable search"
}
```

### After Keyword Search Only

```json
{
  "search_capabilities": {
    "semantic": false,
    "keyword": true
  },
  "available_searches": ["keyword"]
}
```

### After Full Embeddings

```json
{
  "search_capabilities": {
    "semantic": true,
    "keyword": true
  },
  "available_searches": ["semantic", "keyword"]
}
```

---

## Summary

| Feature | Ingestion | Keyword Only | Full Embeddings |
|---------|------------|---------------|-----------------|
| **Ingestion speed** | Fast ⚡ | Fast ⚡ | Fast ⚡ |
| **API calls** | Minimal | 0 | Many (50+ batches) |
| **Time to enable** | Immediate | ~1-5 seconds | ~2-4 minutes |
| **Semantic search** | ❌ No | ❌ No | ✅ Yes |
| **Keyword search** | ❌ No | ✅ Yes | ✅ Yes |
| **Cost** | Minimal | $0 | $Low |

**Recommended:** Start with keyword search only, generate semantic embeddings as needed.
