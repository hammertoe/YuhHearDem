# Barbados Parliamentary Knowledge Graph - Architecture Analysis

## Executive Summary

This document provides a comprehensive architectural analysis of the Barbados Parliamentary Knowledge Graph system. This was an experimental rewrite of a previous system, featuring a multi-stage pipeline for processing parliamentary proceedings using modern NLP techniques, LLM-based entity extraction, and an agentic RAG (Retrieval-Augmented Generation) query system.

**Key Innovation**: The system processes parliamentary videos by using **Order Papers as context** - PDF documents that contain the session agenda and speaker list - to guide video transcription and speaker attribution with high accuracy.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Stage 1: Order Paper Processing (PDF → Gemini Vision)
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│ Order Paper │───▶│ Gemini Vision │───▶│  Speakers   │───▶│  Speaker    │
│   PDF       │    │  Extraction  │    │  + Agenda   │    │   Store     │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘

Stage 2: Video Transcription (YouTube → Gemini Video)
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│   YouTube   │───▶│ Gemini Video │───▶│ Transcript  │───▶│   Vector    │
│    Video    │    │ + Order Paper│    │   + Chunks  │    │   Store     │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  spaCy NER  │ (Optional pre-processing)
                   └─────────────┘

Stage 3: Entity & Relationship Extraction
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│ Transcript  │───▶│ spaCy + LLM │───▶│  Entities   │───▶│   Entity    │
│   (JSON)    │    │  Two-Pass    │    │+ Relations  │    │   Store     │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘

Stage 4: Agentic RAG Query System
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│  Natural    │───▶│ Parliamentary│───▶│ Knowledge   │───▶│  Answered   │
│  Language   │    │    Agent     │    │   Graph     │    │  + Citations│
│   Query     │    │ (Gemini FC)  │    │  (JSON)     │    │             │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
```

---

## Core Components Deep Dive

### 1. Order Paper Processing (`src/parsers/order_paper.py`)

**Purpose**: Parse parliamentary order paper PDFs to extract structured session context.

**Key Features**:
- Uses **Gemini Vision API** to analyze PDF pages
- Handles PDFs arranged for printing (not logical reading order)
- Extracts:
  - Session title, sitting number, date
  - **All speakers** with titles and roles
  - **Agenda items** with primary speakers
- Output: `OrderPaper` dataclass with speaker list and agenda

**Why This Matters**: The order paper provides crucial context for video transcription:
- Known speaker list helps identify who's speaking in the video
- Agenda structure guides transcript organization
- Enables speaker deduplication via fuzzy matching

**Code Pattern**:
```python
class OrderPaperParser:
    def parse(self, pdf_path: Path) -> OrderPaper:
        # Upload PDF to Gemini
        # Extract structured data with JSON schema
        # Return OrderPaper with speakers + agenda
```

---

### 2. Video Transcription (`src/parsers/video_transcript.py`)

**Purpose**: Transcribe parliamentary session videos with precise speaker attribution.

**Key Innovation**: Passes the **parsed Order Paper as context** to Gemini, enabling:
- Accurate speaker identification (comparing against known speaker list)
- Agenda-based transcript organization
- Sentence-level timestamp precision

**Architecture**:

```
VideoTranscriptionParser
├── transcribe() - Main entry point
│   ├── _build_transcription_prompt() - Includes Order Paper context
│   ├── _map_or_create_speaker_id() - Fuzzy matching for speaker IDs
│   └── Single-pass or Chunked processing
├── Chunking for long videos (>87 min at 0.25 FPS)
│   ├── Automatic token estimation
│   ├── Chunk persistence (resume capability)
│   └── Timestamp adjustment & validation
└── Speaker deduplication
    ├── Exact match → Canonical ID
    ├── Case-insensitive match
    └── Fuzzy matching (configurable threshold, default 85%)
```

**Speaker Matching Algorithm**:
1. **Exact match** (O(1)) - Quick lookup
2. **Case-insensitive match** (O(n)) - Handles capitalization differences
3. **Fuzzy matching** with **ambiguity detection**:
   - Uses `thefuzz.ratio()` on normalized names
   - Detects when top 2 scores are within 5 points (ambiguous)
   - Creates new ID for ambiguous matches to prevent misattribution

**Name Normalization** (critical for fuzzy matching):
- Removes titles (Hon., Mr., Dr., K.C., M.P., etc.)
- Handles compound titles ("the honourable" before "honourable")
- Strips punctuation
- Lowercases for comparison

**Chunking Strategy**:
- Token estimation: 383 tokens/frame (measured from actual API usage)
- Safe limit: 500,000 tokens (~87 min at 0.25 FPS)
- Default chunk size: 60 minutes
- Chunk persistence: Saves to `data/processed/chunks/` for resume capability
- Timestamp adjustment: Detects relative vs absolute timestamps from Gemini

**Output**: `SessionTranscript` with:
- Session metadata (title, date, chamber, video URLs)
- Agenda items with speech blocks
- Each sentence has: text, speaker_name, speaker_id, timestamp

---

### 3. spaCy NLP Preprocessor (`src/services/spacy_preprocessor.py`)

**Purpose**: Fast, local entity extraction using spaCy transformer models.

**Model**: `en_core_web_trf` (transformer-based, accurate but slower than small models)

**Features**:
- **EntityRuler integration**: Pre-loads known speakers and entities from JSON files
  - Adds patterns from `data/speakers.json` and `data/entities.json`
  - Ensures canonical IDs are preserved for known entities
- Maps spaCy NER labels to custom EntityType enum:
  - `PERSON` → `EntityType.PERSON`
  - `ORG` → `EntityType.ORGANIZATION`
  - `GPE/LOC` → `EntityType.PLACE`
  - `LAW` → `EntityType.LAW`
  - `EVENT` → `EntityType.EVENT`
  - `NORP/FAC/PRODUCT/WORK_OF_ART/LANGUAGE` → `EntityType.CONCEPT`

**Entity ID Generation**:
- Slugifies entity name (lowercase, hyphenated)
- Removes special characters
- Adds 8-char UUID suffix for uniqueness
- Example: `"CARICOM"` → `"caricom-a7b3c2d1"`

**Use Cases**:
1. **Pre-processing for LLM extraction**: Provides candidate entities as "seed" context
2. **Standalone extraction**: Fast entity detection without API calls
3. **Entity mention tracking**: Records where each entity appears in transcript

---

### 4. Entity & Relationship Extraction (`src/services/entity_extractor.py`)

**Purpose**: Extract semantic entities and their relationships from transcripts using LLM.

**Two-Pass Extraction Strategy** (default method):

**Pass 1: Entity Extraction**
- Sends full transcript to Gemini
- Extracts ALL entities with:
  - Unique entity_id
  - Type (person, organization, place, law, concept, event)
  - Name, canonical_name, aliases
  - Description and importance score
- Optional: Uses spaCy entities as "seed" context

**Pass 2: Relationship Extraction**
- Sends same transcript + complete entity list from Pass 1
- Extracts relationships between entities:
  - Types: mentions, supports, opposes, relates_to, references
  - Sentiment: positive, negative, neutral
  - Evidence: Direct quote from transcript
  - Confidence score

**Why Two-Pass?**
- Eliminates entity fragmentation across chunks
- LLM has full context for relationship inference
- More consistent entity IDs
- Cross-agenda relationships detected

**Alternative Methods**:
- **Chunked mode**: Processes by agenda item (legacy, for very large transcripts >3.5MB)
- **Single mode**: One-shot extraction (legacy, smaller transcripts)

**Output Schema**:
```json
{
  "entities": [{
    "entity_id": "caricom-org-001",
    "entity_type": "organization",
    "name": "CARICOM",
    "canonical_name": "Caribbean Community",
    "aliases": ["Caribbean Community"],
    "description": "Regional organization discussed in free movement context",
    "importance": 0.95
  }],
  "relationships": [{
    "source_id": "senator-mallalieu-001",
    "target_id": "caricom-org-001",
    "relation_type": "supports",
    "sentiment": "positive",
    "evidence": "I rise as a regionalist...",
    "confidence": 0.92
  }]
}
```

**Mention Detection**: After LLM extraction, the system scans the transcript to find:
- Where each entity was mentioned
- Timestamp of each mention
- Context (sentence text)
- Links to bills if mentioned in bill-related agenda items

---

### 5. Storage Layer

#### Entity Store (`src/storage/entity_store.py`)
- **Purpose**: Persistent storage for entities and relationships
- **Format**: JSON files (`data/entities.json`, `data/relationships.json`)
- **Features**:
  - Fuzzy matching for entity deduplication (configurable threshold, default 85%)
  - Entity resolution cache (avoids re-processing same entities)
  - LLM-based entity resolution for ambiguous matches
  - Index by ID, name, and type

#### Vector Store (`src/storage/vector_store.py`)
- **Purpose**: Semantic search over transcript sentences
- **Technology**: ChromaDB with cosine similarity
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- **Features**:
  - Stores every sentence with metadata (speaker, timestamp, session, chamber)
  - Links sentences to entity mentions and relationship evidence
  - Gender inference from speaker database for pronoun resolution
  - Filtered search by chamber, date range

#### Legislation Store (`src/storage/legislation_store.py`)
- **Purpose**: Store bill/resolution metadata from parliament website
- **Links**: Connects law entities to full bill details (stages, PDFs, sponsors)

#### Speaker Store (`src/storage/store.py`)
- **Purpose**: Canonical speaker database with deduplication
- **Fuzzy Matching**: Prevents duplicate speaker entries using `thefuzz`

---

### 6. Agentic RAG System (`src/api/parliamentary_agent.py`)

**Purpose**: Natural language query interface using Gemini function calling.

**Architecture**:
- **System**: Gemini 2.5 Flash with tool use (function calling)
- **Max Iterations**: 10 (configurable)
- **Tools Available**:
  1. `find_entity()` - Hybrid fuzzy + vector search for entities
  2. `get_relationships()` - Get entity connections
  3. `get_mentions()` - Get specific citations with timestamps
  4. `get_entity_details()` - Full entity metadata
  5. `search_by_date()` - Find sessions in date range
  6. `search_by_speaker()` - Find all speeches by speaker
  7. `search_semantic()` - Vector search for topic queries
  8. `get_legislation_details()` - Full bill metadata
  9. `get_session_details()` - Session metadata

**Query Flow**:
1. User asks natural language question
2. Agent decides which tools to call
3. Agent iteratively builds context (multi-hop reasoning)
4. Agent generates final answer with citations
5. Each citation includes: speaker, timestamp, video URL, quote

**Example Multi-Hop Query**:
```
User: "What did Senator Trim say about the Cybercrime Bill?"

Agent:
1. find_entity("Trim", entity_type="person") → Gets senator-trim-001
2. search_semantic("Cybercrime Bill") → Finds law entity
3. get_relationships(senator-trim-001) → Finds relationships
4. get_mentions(law-cybercrime-001) → Gets direct quotes
5. Answer with citations
```

---

## Data Models

### Core Entities

```python
# Order Paper (from PDF)
OrderPaper
├── session_title: str
├── session_date: date
├── sitting_number: str
├── chamber: str ("senate" | "house")
├── speakers: list[OrderPaperSpeaker]
└── agenda_items: list[AgendaItem]

# Transcript (from Video)
SessionTranscript
├── session_title: str
├── date: date
├── chamber: str
├── agenda_items: list[TranscriptAgendaItem]
├── video_url: str
├── video_title: str
└── video_upload_date: str

TranscriptAgendaItem
├── topic_title: str
├── speech_blocks: list[SpeechBlock]
├── bill_id: str (optional, linked to legislation)
└── bill_match_confidence: float

SpeechBlock
├── speaker_name: str (as heard in video)
├── speaker_id: str (canonical ID)
└── sentences: list[Sentence]

Sentence
├── start_time: str ("XmYsZms" format)
└── text: str

# Knowledge Graph
Entity
├── entity_id: str
├── entity_type: EntityType
├── name: str
├── canonical_name: str
├── aliases: list[str]
├── mentions: list[Mention]
└── legislation_id: str (for law entities)

Mention
├── session_id: str
├── agenda_item_index: int
├── sentence_index: int
├── timestamp: str
├── context: str
└── bill_id: str (optional)

Relationship
├── source_id: str
├── target_id: str
├── relation_type: RelationType
├── sentiment: Sentiment
├── evidence: str
├── session_id: str
└── timestamp: str
```

---

## Processing Scripts

### Main Entry Points

1. **`transcribe_video.py`** - Video transcription workflow
   ```bash
   python transcribe_video.py --url YOUTUBE_URL --order-paper PDF_PATH --full
   ```

2. **`extract_entities.py`** - Entity extraction from transcripts
   ```bash
   python extract_entities.py --transcript FILE.json --spacy
   ```

3. **`process_order_paper.py`** - Single order paper processing
   ```bash
   python process_order_paper.py PDF_PATH
   ```

4. **`index_knowledge_graph.py`** - Build vector store from transcripts
   ```bash
   python index_knowledge_graph.py
   ```

5. **`link_legislation.py`** - Link entities to legislation database
   ```bash
   python link_legislation.py
   ```

### Utility Scripts

- **`infer_speaker_gender.py`** - Infer speaker gender from names/context
- **`infer_speaker_pronouns.py`** - Infer pronouns for speakers
- **`scrape_all_legislation.py`** - Scrape bills from parliament website
- **`parse_all_order_papers.py`** - Batch process order papers
- **`process_legislation.py`** - Process legislation metadata

---

## Key Technical Decisions

### 1. Why Gemini?
- **Vision**: Native PDF understanding without OCR preprocessing
- **Video**: Direct YouTube URL processing with frame sampling
- **Structured Output**: JSON schema enforcement for reliable parsing
- **Context Window**: 1M tokens handles most parliamentary sessions

### 2. Why spaCy + LLM Hybrid?
- **spaCy**: Fast, local, deterministic entity detection
- **LLM**: Captures context, relationships, nuanced understanding
- **Combination**: spaCy provides candidates, LLM validates and enriches

### 3. Why Fuzzy Matching?
- Parliamentary names have variations:
  - "Hon. L. R. Cummins" vs "Cummins" vs "Mr. Cummins"
  - Title differences across sessions
  - Spelling variations
- **Solution**: Normalized fuzzy matching with configurable thresholds

### 4. Why Order Paper as Context?
- Without context: Gemini must guess speakers from video
- With context: Known speaker list guides attribution
- Result: Higher accuracy, consistent IDs, better transcript structure

### 5. Why Two-Pass Entity Extraction?
- Single-pass across chunks: Entity fragmentation
- Two-pass on full transcript: Consistent entities, cross-context relationships
- Trade-off: Requires transcript to fit in context window (most do)

---

## Data Flow Example

**Input**: Senate session on October 22, 2025 (Free Movement Bill)

```
Step 1: Order Paper Processing
PDF: order_paper_2025-10-22.pdf
↓
Gemini Vision extracts:
- Session: "The Honourable The Senate, First Session of 2022-2027"
- Date: 2025-10-22
- Speakers: ["Hon. L. R. Cummins", "Dr. J. X. Walcott", ...] (20+ speakers)
- Agenda: ["Caribbean Community (Free Movement) Bill", ...] (13 items)
↓
Stored: data/processed/order_paper_2025-10-22.json
        data/speakers.json (updated with new speakers, deduplicated)

Step 2: Video Transcription
Video: https://youtube.com/watch?v=...
↓
Uses Order Paper as context in prompt
↓
Gemini Video extracts:
- 4+ hours of transcribed speech
- Sentence-level timestamps
- Speaker attribution via fuzzy matching
↓
Stored: data/processed/transcript_senate-2025-10-22.json

Step 3: Entity Extraction
Transcript → spaCy (optional) → Gemini Two-Pass
↓
Pass 1: Extract entities (CARICOM, Free Movement Bill, Barbados, etc.)
Pass 2: Extract relationships (Senator X supports Bill Y)
↓
Stored: data/entities.json (fuzzy deduplication)
        data/relationships.json

Step 4: Vector Indexing
Transcript sentences → Embeddings → ChromaDB
↓
Each sentence linked to:
- Speaker ID
- Entity mentions
- Relationship evidence
- Timestamp & video URL

Step 5: Query
User: "Who supported the Free Movement Bill?"
↓
ParliamentaryAgent:
1. search_semantic("Free Movement Bill") → Find bill entity
2. get_relationships(bill-id, direction="incoming") → Find supporters
3. get_mentions() → Get direct quotes
4. Answer: "Senator Cummins supported it, saying: '...' (timestamp)"
```

---

## Configuration & Environment

**Environment Variables** (`.env` file):
```bash
GOOGLE_API_KEY=your_gemini_api_key_here
```

**Key Configuration**:
- **Fuzzy Threshold**: 85% (configurable in parsers/stores)
- **Chunk Size**: 60 minutes (configurable in VideoTranscriptionParser)
- **FPS**: 0.25 (lower = fewer tokens, higher = more detail)
- **Max Tokens**: 500,000 safe limit for chunking decisions

**Data Directory Structure**:
```
data/
├── order_papers/          # Input PDFs
├── processed/             # Output JSONs
│   ├── chunks/           # Video chunk cache
│   ├── order_paper_*.json
│   └── transcript_*.json
├── speakers.json         # Canonical speaker database
├── entities.json         # Knowledge graph entities
├── relationships.json    # Knowledge graph relationships
├── legislation.json      # Bills and resolutions
└── vector_db/            # ChromaDB persistence
```

---

## Known Issues & Experimental Nature

1. **Type Safety**: Some LSP errors exist in gemini.py and parliamentary_agent.py (type mismatches with None)
2. **Gender Inference**: Heuristic-based, may need manual verification
3. **Entity Resolution**: LLM-based resolution is expensive and cached, but cache invalidation strategy unclear
4. **Video Chunking**: Edge cases with timestamp detection (relative vs absolute)
5. **Bill Linking**: Fuzzy matching bill titles to agenda items, may have false positives
6. **Thinking Budget**: Experimental Gemini feature for reasoning (used in AB tests)

---

## What Worked Well

1. **Order Paper Context**: Dramatically improved transcription accuracy
2. **Fuzzy Speaker Matching**: Successfully handled name variations
3. **Two-Pass Extraction**: Higher quality entities and relationships
4. **Chunk Persistence**: Resume capability for long video processing
5. **Agentic RAG**: Natural language queries with citations work well
6. **spaCy + LLM Hybrid**: Good balance of speed and accuracy

---

## Recommendations for New Implementation

### Keep:
- Order Paper as context approach
- Two-pass entity extraction
- Fuzzy speaker matching with normalization
- Vector store for semantic search
- Agentic RAG with function calling
- JSON-based storage (simple, debuggable)

### Improve:
- Add proper database (PostgreSQL + pgvector) instead of JSON files
- Implement async processing for batch operations
- Add comprehensive logging and monitoring
- Build web UI for manual verification of ambiguous matches
- Add speaker voice recognition as secondary signal
- Implement incremental updates (don't re-process unchanged data)
- Add tests (current test coverage is minimal)

### Consider:
- Whisper v3 for initial transcription (faster/cheaper than Gemini)
- Use Gemini only for entity extraction and speaker attribution
- Implement streaming processing for live sessions
- Add multi-language support (if needed)
- Build analytics dashboard for knowledge graph metrics

---

## Dependencies

**Core**:
- `google-genai` - Gemini API client
- `spacy` + `en_core_web_trf` - NLP preprocessing
- `chromadb` + `sentence-transformers` - Vector search
- `thefuzz` - Fuzzy string matching
- `fastapi` + `uvicorn` - Web API
- `pydantic` - Data validation

**Utilities**:
- `yt-dlp` - YouTube metadata extraction
- `beautifulsoup4` + `lxml` - Web scraping
- `python-dotenv` - Environment management

---

## Conclusion

This system represents a sophisticated approach to parliamentary transcript processing. The **key architectural insight** is using structured documents (Order Papers) as context for unstructured data (video), enabling high-accuracy speaker attribution and semantic organization.

The **two-pass entity extraction** and **hybrid spaCy + LLM approach** provide a good balance of efficiency and accuracy. The **agentic RAG system** demonstrates how LLMs can effectively query structured knowledge graphs when given appropriate tools.

For a production rewrite, focus on:
1. **Data integrity** - Proper database with transactions
2. **Observability** - Logging, metrics, error tracking
3. **Scalability** - Async processing, caching strategies
4. **Usability** - Web interface, verification workflows
5. **Testing** - Comprehensive test coverage

The experimental nature of this codebase means many edge cases were discovered but not fully resolved. The architecture is sound, but implementation details need hardening for production use.
