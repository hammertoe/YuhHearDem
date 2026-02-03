"""Video transcription parser using Gemini with order paper context."""

import hashlib
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from src.models.order_paper import OrderPaper
from src.models.session import Sentence, SessionTranscript, SpeechBlock, TranscriptAgendaItem
from src.models.speaker import Speaker
from src.services.gemini import GeminiClient
from thefuzz import fuzz


class VideoTranscriptionParser:
    """Parses parliamentary session videos with speaker attribution."""

    # Token estimation constants
    TOKENS_PER_FRAME = 383  # Measured from actual API usage (was 258 - underestimated by 48%)
    MAX_TOKENS = 1_048_576  # Gemini 2.5 Flash max context window
    SAFE_TOKEN_LIMIT = 500_000  # Conservative limit for auto-chunking (~87 min at 0.25 FPS)
    DEFAULT_CHUNK_SIZE = 3600  # 60 minutes (1 hour) in seconds

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 5  # seconds

    def __init__(
        self,
        gemini_client: GeminiClient,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        fuzzy_threshold: int = 85,
    ):
        """
        Initialize parser with Gemini client.

        Args:
            gemini_client: Initialized Gemini client instance
            chunk_size: Chunk size in seconds for long videos (default: 3600 = 60 minutes)
            fuzzy_threshold: Minimum similarity score (0-100) for fuzzy name matching (default: 85)
        """
        self.client = gemini_client
        self.chunk_size = chunk_size
        self.fuzzy_threshold = fuzzy_threshold

    def transcribe(
        self,
        video_url: str,
        order_paper: OrderPaper,
        speaker_id_mapping: dict[str, str],
        fps: float = 0.25,
        start_time: int | None = None,
        end_time: int | None = None,
        auto_chunk: bool = True,
        video_duration: int | None = None,
        cleanup_chunks: bool = True,
        video_metadata: dict | None = None,
    ) -> tuple[SessionTranscript, list[Speaker]]:
        """
        Transcribe a parliamentary session video.

        Args:
            video_url: YouTube URL of the session recording
            order_paper: Parsed order paper with agenda and speakers
            speaker_id_mapping: Maps extracted speaker names to canonical IDs
            fps: Frames per second to sample (default: 0.25, lower = fewer tokens)
            start_time: Optional start time in seconds
            end_time: Optional end time in seconds
            auto_chunk: Automatically chunk long videos (default: True)
            video_duration: Video duration in seconds (for chunking calculation)
            cleanup_chunks: Delete chunk files after successful merge (default: True)
            video_metadata: Optional video metadata (title, url, upload_date)

        Returns:
            Tuple of (SessionTranscript, list of newly created Speaker objects)
        """
        prompt = self._build_transcription_prompt(order_paper, speaker_id_mapping)
        schema = self._load_output_schema()
        new_speakers = []  # Track newly created speakers

        # Determine actual duration to process
        if start_time is not None and end_time is not None:
            duration = end_time - start_time
        elif video_duration:
            duration = video_duration
        else:
            # Unknown duration - try single pass
            duration = None

        # Check if chunking is needed
        needs_chunking = False
        if duration and auto_chunk:
            estimated_tokens = self._estimate_tokens(duration, fps)
            needs_chunking = estimated_tokens > self.SAFE_TOKEN_LIMIT

        if needs_chunking:
            print("   Video exceeds token limit - processing in chunks...")
            return self._transcribe_chunked(
                video_url=video_url,
                order_paper=order_paper,
                speaker_id_mapping=speaker_id_mapping,
                fps=fps,
                start_time=start_time or 0,
                end_time=end_time or duration,
                prompt=prompt,
                schema=schema,
                cleanup_chunks=cleanup_chunks,
                video_metadata=video_metadata,
            )
        else:
            # Single-pass processing
            response = self.client.analyze_video_with_transcript(
                video_url=video_url,
                prompt=prompt,
                response_schema=schema,
                fps=fps,
                start_time=start_time,
                end_time=end_time,
            )
            transcript = self._parse_response(response, speaker_id_mapping, new_speakers)
            # Add video metadata
            if video_metadata:
                transcript.video_url = video_metadata.get("url")
                transcript.video_title = video_metadata.get("title")
                transcript.video_upload_date = video_metadata.get("upload_date")
            return (transcript, new_speakers)

    def _build_transcription_prompt(
        self,
        order_paper: OrderPaper,
        speaker_id_mapping: dict[str, str],
    ) -> str:
        """
        Build prompt for Gemini with full context.

        Args:
            order_paper: Parsed order paper
            speaker_id_mapping: Speaker name → canonical ID mapping

        Returns:
            Detailed transcription prompt
        """
        # Build speaker reference with clear ID/name separation
        speaker_list = []
        for speaker in order_paper.speakers:
            canonical_id = speaker_id_mapping.get(speaker.name, speaker.name)
            speaker_info = (
                f"  ---\n  ID: {canonical_id}\n  Name: {speaker.title or ''} {speaker.name}"
            )
            if speaker.role:
                speaker_info += f"\n  Role: {speaker.role}"
            speaker_list.append(speaker_info)

        # Build agenda reference
        agenda_list = []
        for i, item in enumerate(order_paper.agenda_items, 1):
            agenda_list.append(f"  {i}. {item.topic_title}")
            if item.primary_speaker:
                agenda_list.append(f"     Primary Speaker: {item.primary_speaker}")

        return f"""Transcribe this Barbados parliamentary session video with precise speaker attribution and timing.

SESSION CONTEXT:
- Title: {order_paper.session_title}
- Date: {order_paper.session_date}
- Sitting: {order_paper.sitting_number or "N/A"}

SPEAKERS (for reference - to help you identify who is speaking):
{chr(10).join(speaker_list)}

AGENDA (expected order of business):
{chr(10).join(agenda_list)}

TRANSCRIPTION INSTRUCTIONS:

1. **Structure by Agenda Items:**
   - Organize the transcript according to the agenda items above
   - Each agenda item should contain all speeches related to that topic
   - If the video doesn't follow the agenda exactly, use your best judgment

2. **Speaker Attribution:**
   - For "speaker_name": provide the name EXACTLY as you hear it announced or spoken
   - Include all titles and honorifics (e.g., "Mr. Ralph Thorne, K.C., M.P." or "Hon. L. R. Cummins")
   - Leave "speaker_id" blank - the system will populate this automatically
   - Use the speaker reference list above to help identify who is speaking
   - If you cannot identify the speaker, use "UNIDENTIFIED SPEAKER"

3. **Speech Blocks:**
   - Group consecutive sentences from the same speaker into speech blocks
   - When the speaker changes, start a new speech block

4. **Sentence-Level Timing:**
   - Provide the start time for EACH sentence in format "XmYsZms" (e.g., "0m5s250ms")
   - Be as precise as possible with timecodes
   - Times should be relative to the start of the video

5. **Transcription Quality:**
   - Transcribe exactly what is said, including:
     * Parliamentary procedure language ("I move that...", "The question is...", etc.)
     * Questions and responses
     * Interruptions and points of order
   - Preserve the formal tone and language
   - Do not summarize - transcribe verbatim

6. **Handling Uncertainty:**
   - If you cannot clearly identify a speaker, use "UNIDENTIFIED_SPEAKER"
   - If you cannot hear a word clearly, use "[inaudible]"

Return the complete transcript in the specified JSON structure."""

    def _load_output_schema(self) -> dict:
        """
        Load the output schema from output-schema.json.

        Returns:
            JSON schema dictionary
        """
        schema_path = Path("output-schema.json")
        with open(schema_path) as f:
            return json.load(f)

    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name by removing titles and extra punctuation.

        Args:
            name: Name to normalize

        Returns:
            Normalized name
        """
        titles = [
            # Compound titles (must be processed before their components)
            "the honourable",
            "the hon.",
            "his honour",
            "her honour",
            "his excellency",
            "her excellency",
            # Single titles
            "honourable",
            "hon.",
            "mr.",
            "mrs.",
            "ms.",
            "dr.",
            "k.c.",
            "m.p.",
            "senator",
            "s.c.",
            "q.c.",
            "minister",
            "rev.",
            "prof.",
            "sir",
            "dame",
            "lord",
            "lady",
        ]
        normalized = name.lower()
        # Sort by length descending to ensure longer titles are removed first
        # This prevents "the honourable" from becoming "the " after removing "honourable"
        for title in sorted(titles, key=len, reverse=True):
            normalized = normalized.replace(title, "")
        return normalized.strip().replace(",", "").replace(".", "")

    def _generate_canonical_id(self, name: str) -> str:
        """
        Generate a canonical ID for a speaker.

        Uses normalized name plus a unique suffix.

        Args:
            name: Speaker's name

        Returns:
            Canonical ID (e.g., "john-smith-abc12345")
        """
        normalized = self._normalize_name(name)
        # Replace spaces with hyphens
        slug = normalized.replace(" ", "-")
        # Remove any remaining special characters except hyphens
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        # Remove consecutive hyphens
        slug = re.sub(r"-+", "-", slug).strip("-")
        # Add short unique suffix (8 chars from UUID)
        unique_suffix = str(uuid.uuid4())[:8]
        return f"{slug}-{unique_suffix}"

    def _map_or_create_speaker_id(
        self, speaker_name: str, speaker_id_mapping: dict[str, str]
    ) -> tuple[str | None, bool, Speaker | None]:
        """
        Map a speaker name to canonical ID using fuzzy matching, or create a new ID.

        Uses a three-stage matching approach:
        1. Exact string match
        2. Case-insensitive match
        3. Fuzzy matching on normalized names (configurable threshold, default 85%)

        If no match found, generates a new canonical ID and adds it to the mapping.

        Args:
            speaker_name: Speaker name as heard in video
            speaker_id_mapping: Dict mapping names to canonical IDs
                               WARNING: This dict will be MUTATED by adding new speakers
                               to ensure consistency within a single transcription run.

        Returns:
            Tuple of (speaker_id, is_new, speaker_object)
            - speaker_id: Canonical speaker ID or None if UNIDENTIFIED SPEAKER
            - is_new: True if a new ID was generated
            - speaker_object: Speaker object if new, None otherwise
        """
        # Don't generate IDs for unidentified speakers
        if speaker_name.upper() == "UNIDENTIFIED SPEAKER":
            return (None, False, None)

        # Try exact match first (O(1))
        if speaker_name in speaker_id_mapping:
            return (speaker_id_mapping[speaker_name], False, None)

        # Try case-insensitive exact match (O(n) - could be optimized)
        for name, speaker_id in speaker_id_mapping.items():
            if name.lower() == speaker_name.lower():
                return (speaker_id, False, None)

        # Try fuzzy matching with ambiguity detection
        normalized_speaker = self._normalize_name(speaker_name)

        # Collect all matches that meet the threshold
        close_matches = []
        for name, speaker_id in speaker_id_mapping.items():
            normalized_candidate = self._normalize_name(name)
            score = fuzz.ratio(normalized_speaker, normalized_candidate)
            if score >= self.fuzzy_threshold:
                close_matches.append((score, speaker_id, name))

        # Sort by score descending
        close_matches.sort(key=lambda x: x[0], reverse=True)

        # Check for ambiguity: if top two scores are very close (within 5 points)
        if len(close_matches) > 1 and (close_matches[0][0] - close_matches[1][0]) < 5:
            print(f"      ⚠️  Ambiguous match for '{speaker_name}':")
            print(f"         - {close_matches[0][2]} (score: {close_matches[0][0]})")
            print(f"         - {close_matches[1][2]} (score: {close_matches[1][0]})")
            print("         Creating new ID to avoid misattribution.")
            # Fall through to create new ID
        elif close_matches:
            # Clear match found
            return (close_matches[0][1], False, None)

        # No match found - generate new ID
        new_id = self._generate_canonical_id(speaker_name)
        new_speaker = Speaker(
            id=new_id,
            name=speaker_name,
            title=None,
            role=None,
            party=None,
        )

        # IMPORTANT: Add to mapping immediately so subsequent encounters find it.
        # This is a deliberate side effect for in-run deduplication.
        speaker_id_mapping[speaker_name] = new_id

        print(f"      ✨ Created new speaker ID: {new_id} for '{speaker_name}'")
        return (new_id, True, new_speaker)

    def _parse_response(
        self,
        response: dict,
        speaker_id_mapping: dict[str, str] | None = None,
        new_speakers_list: list[Speaker] | None = None,
    ) -> SessionTranscript:
        """
        Parse Gemini response into SessionTranscript object.

        Args:
            response: JSON response from Gemini matching output-schema.json
            speaker_id_mapping: Optional mapping for speaker name → canonical ID
            new_speakers_list: Optional list to collect newly created speakers

        Returns:
            SessionTranscript object with speaker IDs populated where possible
        """
        agenda_items = []
        unmapped_speakers = set()

        for item_data in response.get("agenda_items", []):
            speech_blocks = []

            for block_data in item_data.get("speech_blocks", []):
                sentences = []

                for sent_data in block_data.get("sentences", []):
                    sentences.append(
                        Sentence(
                            start_time=sent_data["start_time"],
                            text=sent_data["text"],
                        )
                    )

                # Handle both old format (speaker) and new format (speaker_name/speaker_id)
                speaker_name = block_data.get("speaker_name") or block_data.get(
                    "speaker", "UNKNOWN"
                )
                speaker_id = block_data.get("speaker_id")

                # Map speaker name to ID if mapping provided (even if empty) and ID not already set
                if speaker_id_mapping is not None and not speaker_id:
                    speaker_id, is_new, new_speaker = self._map_or_create_speaker_id(
                        speaker_name, speaker_id_mapping
                    )
                    # Track new speakers if list provided
                    if is_new and new_speaker and new_speakers_list is not None:
                        # Avoid duplicates
                        if not any(s.id == new_speaker.id for s in new_speakers_list):
                            new_speakers_list.append(new_speaker)
                    if not speaker_id:
                        unmapped_speakers.add(speaker_name)

                speech_blocks.append(
                    SpeechBlock(
                        speaker_name=speaker_name,
                        speaker_id=speaker_id,
                        sentences=sentences,
                    )
                )

            agenda_items.append(
                TranscriptAgendaItem(
                    topic_title=item_data["topic_title"],
                    speech_blocks=speech_blocks,
                )
            )

        # Parse date string to date object
        date_str = response["date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Log unmapped speakers (only UNIDENTIFIED SPEAKER at this point)
        if unmapped_speakers:
            print(f"      ℹ️  {len(unmapped_speakers)} speaker(s) left without IDs:")
            for speaker in sorted(unmapped_speakers):
                print(f"         - {speaker}")

        return SessionTranscript(
            session_title=response["session_title"],
            date=date_obj,
            agenda_items=agenda_items,
        )

    def _extract_video_id(self, video_url: str) -> str:
        """
        Extract video ID from YouTube URL or generate hash from URL.

        Args:
            video_url: YouTube URL

        Returns:
            Video identifier for chunk file naming
        """
        # Try to extract YouTube video ID
        match = re.search(r"[?&]v=([^&]+)", video_url)
        if match:
            return match.group(1)

        # Fallback: hash the URL
        return hashlib.md5(video_url.encode()).hexdigest()[:12]

    def _get_chunk_file_path(self, video_url: str, chunk_num: int) -> Path:
        """
        Get file path for saving/loading a chunk.

        Args:
            video_url: YouTube URL
            chunk_num: Chunk number (1-indexed)

        Returns:
            Path to chunk file
        """
        video_id = self._extract_video_id(video_url)
        chunks_dir = Path("data/processed/chunks")
        chunks_dir.mkdir(parents=True, exist_ok=True)
        return chunks_dir / f"transcript_{video_id}_chunk_{chunk_num}.json"

    def _save_chunk(self, transcript: SessionTranscript, video_url: str, chunk_num: int) -> None:
        """
        Save a chunk transcript to disk.

        Args:
            transcript: Chunk transcript to save
            video_url: YouTube URL
            chunk_num: Chunk number
        """
        chunk_file = self._get_chunk_file_path(video_url, chunk_num)
        with open(chunk_file, "w") as f:
            json.dump(transcript.to_dict(), f, indent=2)
        print(f"      ✓ Saved chunk {chunk_num} to {chunk_file}")

    def _load_chunk(self, video_url: str, chunk_num: int) -> SessionTranscript | None:
        """
        Load a chunk transcript from disk if it exists.

        Args:
            video_url: YouTube URL
            chunk_num: Chunk number

        Returns:
            Loaded transcript or None if file doesn't exist
        """
        chunk_file = self._get_chunk_file_path(video_url, chunk_num)
        if not chunk_file.exists():
            return None

        with open(chunk_file) as f:
            data = json.load(f)

        return SessionTranscript.from_dict(data)

    def _estimate_tokens(self, duration_seconds: int, fps: float) -> int:
        """
        Estimate token count for video duration.

        Args:
            duration_seconds: Video duration in seconds
            fps: Frames per second

        Returns:
            Estimated token count
        """
        frames = duration_seconds * fps
        return int(frames * self.TOKENS_PER_FRAME)

    def _calculate_chunks(self, start_time: int, end_time: int) -> list[tuple[int, int]]:
        """
        Calculate chunk boundaries for video processing.

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            List of (start, end) tuples for each chunk
        """
        chunks = []
        current_start = start_time

        while current_start < end_time:
            current_end = min(current_start + self.chunk_size, end_time)
            chunks.append((current_start, current_end))
            current_start = current_end

        return chunks

    def _cleanup_chunks(self, video_url: str, num_chunks: int) -> None:
        """
        Delete chunk files after successful merge.

        Args:
            video_url: YouTube URL
            num_chunks: Number of chunks to delete
        """
        for i in range(1, num_chunks + 1):
            chunk_file = self._get_chunk_file_path(video_url, i)
            if chunk_file.exists():
                chunk_file.unlink()
        print(f"   🗑️  Cleaned up {num_chunks} chunk files")

    def _transcribe_chunked(
        self,
        video_url: str,
        order_paper: OrderPaper,
        speaker_id_mapping: dict[str, str],
        fps: float,
        start_time: int,
        end_time: int,
        prompt: str,
        schema: dict,
        cleanup_chunks: bool = True,
        video_metadata: dict | None = None,
    ) -> tuple[SessionTranscript, list[Speaker]]:
        """
        Transcribe video in chunks and merge results.

        Args:
            video_url: YouTube URL
            order_paper: Order paper context
            speaker_id_mapping: Speaker ID mappings
            fps: Frames per second
            start_time: Overall start time
            end_time: Overall end time
            prompt: Transcription prompt
            schema: Output schema
            cleanup_chunks: Delete chunk files after successful merge (default: True)
            video_metadata: Optional video metadata (title, url, upload_date)

        Returns:
            Tuple of (Merged SessionTranscript, list of newly created Speaker objects)
        """
        chunks = self._calculate_chunks(start_time, end_time)
        print(f"   Processing {len(chunks)} chunks of {self.chunk_size}s each...")

        # Check for existing chunks
        existing_chunks = sum(
            1 for i in range(1, len(chunks) + 1) if self._get_chunk_file_path(video_url, i).exists()
        )
        if existing_chunks > 0:
            print(
                f"   Found {existing_chunks} existing chunk(s) - resuming from where we left off..."
            )

        chunk_transcripts = []
        new_speakers = []  # Track newly created speakers across all chunks

        for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
            # Try to load existing chunk
            existing_chunk = self._load_chunk(video_url, i)
            if existing_chunk:
                print(f"   ✓ Chunk {i}/{len(chunks)} already processed - loading from disk...")
                chunk_transcripts.append(existing_chunk)
                # Note: We can't track new speakers from pre-existing chunks
                # They would need to be re-processed to generate new speaker IDs
                continue

            print(f"   Processing chunk {i}/{len(chunks)} ({chunk_start}s - {chunk_end}s)...")

            # Retry logic with exponential backoff
            transcript = None
            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    response = self.client.analyze_video_with_transcript(
                        video_url=video_url,
                        prompt=prompt,
                        response_schema=schema,
                        fps=fps,
                        start_time=chunk_start,
                        end_time=chunk_end,
                    )

                    transcript = self._parse_response(response, speaker_id_mapping, new_speakers)

                    # Adjust timestamps to account for chunk offset and validate
                    if chunk_start > 0:
                        transcript = self._adjust_timestamps(
                            transcript, chunk_start, chunk_start, chunk_end
                        )

                    # Save chunk to disk
                    self._save_chunk(transcript, video_url, i)
                    break  # Success!

                except Exception as e:
                    if attempt < self.MAX_RETRIES:
                        delay = self.RETRY_DELAY_BASE * (2 ** (attempt - 1))  # Exponential backoff
                        print(f"      ⚠️  Error: {e}")
                        print(
                            f"      Retrying in {delay}s (attempt {attempt + 1}/{self.MAX_RETRIES})..."
                        )
                        time.sleep(delay)
                    else:
                        print(f"      ❌ Failed after {self.MAX_RETRIES} attempts")
                        raise e

            chunk_transcripts.append(transcript)

        # Merge all chunks
        merged_transcript = self._merge_transcripts(chunk_transcripts)

        # Add video metadata
        if video_metadata:
            merged_transcript.video_url = video_metadata.get("url")
            merged_transcript.video_title = video_metadata.get("title")
            merged_transcript.video_upload_date = video_metadata.get("upload_date")

        # Cleanup chunk files if requested
        if cleanup_chunks:
            self._cleanup_chunks(video_url, len(chunks))

        return (merged_transcript, new_speakers)

    def _parse_timecode(self, time_str: str) -> int:
        """
        Parse time string to total seconds.

        Args:
            time_str: Time in format "XmYsZms"

        Returns:
            Total seconds (rounded)
        """
        match = re.match(r"(\d+)m(\d+)s(\d+)ms", time_str)
        if not match:
            return 0
        minutes, seconds, ms = map(int, match.groups())
        return minutes * 60 + seconds

    def _detect_timestamp_mode(
        self, transcript: SessionTranscript, chunk_start_seconds: int
    ) -> str:
        """
        Detect if Gemini returned absolute or relative timestamps.

        Args:
            transcript: Transcript to analyze
            chunk_start_seconds: Expected chunk start time

        Returns:
            "relative" if timestamps start near 0, "absolute" if near chunk_start
        """
        # Find first timestamp
        for item in transcript.agenda_items:
            for block in item.speech_blocks:
                if block.sentences:
                    first_timestamp_seconds = self._parse_timecode(block.sentences[0].start_time)

                    # If first timestamp is close to 0, it's relative
                    if first_timestamp_seconds < 300:  # Within 5 minutes of start
                        return "relative"

                    # If first timestamp is close to chunk_start, it's absolute
                    if abs(first_timestamp_seconds - chunk_start_seconds) < 300:
                        return "absolute"

                    # Default to relative if unclear
                    return "relative"

        # No timestamps found, default to relative
        return "relative"

    def _validate_and_filter_timestamps(
        self,
        transcript: SessionTranscript,
        expected_start: int,
        expected_end: int,
        tolerance: int = 600,  # 10 minutes tolerance
    ) -> SessionTranscript:
        """
        Validate timestamps are within expected range and filter outliers.

        Args:
            transcript: Transcript to validate
            expected_start: Expected start time in seconds
            expected_end: Expected end time in seconds
            tolerance: How many seconds outside range to tolerate

        Returns:
            Filtered transcript
        """
        filtered_items = []
        filtered_count = 0

        for item in transcript.agenda_items:
            filtered_blocks = []

            for block in item.speech_blocks:
                filtered_sentences = []

                for sentence in block.sentences:
                    timestamp_seconds = self._parse_timecode(sentence.start_time)

                    # Check if timestamp is within expected range (with tolerance)
                    if (
                        (expected_start - tolerance)
                        <= timestamp_seconds
                        <= (expected_end + tolerance)
                    ):
                        filtered_sentences.append(sentence)
                    else:
                        filtered_count += 1

                # Only keep block if it has sentences
                if filtered_sentences:
                    filtered_blocks.append(
                        SpeechBlock(
                            speaker_name=block.speaker_name,
                            speaker_id=block.speaker_id,
                            sentences=filtered_sentences,
                        )
                    )

            # Only keep item if it has blocks
            if filtered_blocks:
                filtered_items.append(
                    TranscriptAgendaItem(
                        topic_title=item.topic_title,
                        speech_blocks=filtered_blocks,
                    )
                )

        if filtered_count > 0:
            print(
                f"      ⚠️  Filtered {filtered_count} sentence(s) with timestamps outside expected range"
            )

        return SessionTranscript(
            session_title=transcript.session_title,
            date=transcript.date,
            agenda_items=filtered_items,
        )

    def _adjust_timestamps(
        self, transcript: SessionTranscript, offset_seconds: int, chunk_start: int, chunk_end: int
    ) -> SessionTranscript:
        """
        Adjust all timestamps in transcript by adding offset if needed.

        Detects if Gemini returned relative or absolute timestamps and adjusts accordingly.

        Args:
            transcript: Transcript to adjust
            offset_seconds: Seconds to add to all timestamps (chunk start time)
            chunk_start: Chunk start time in seconds
            chunk_end: Chunk end time in seconds

        Returns:
            Transcript with adjusted and validated timestamps
        """
        # Detect timestamp mode
        timestamp_mode = self._detect_timestamp_mode(transcript, chunk_start)
        print(f"      Timestamp mode detected: {timestamp_mode}")

        # Parse time format: "0m5s250ms" -> total milliseconds
        def parse_time(time_str: str) -> int:
            """Parse time string to milliseconds."""
            match = re.match(r"(\d+)m(\d+)s(\d+)ms", time_str)
            if not match:
                return 0
            minutes, seconds, ms = map(int, match.groups())
            return (minutes * 60 + seconds) * 1000 + ms

        # Format milliseconds back to time string
        def format_time(total_ms: int) -> str:
            """Format milliseconds to time string."""
            minutes = total_ms // 60000
            remaining_ms = total_ms % 60000
            seconds = remaining_ms // 1000
            ms = remaining_ms % 1000
            return f"{minutes}m{seconds}s{ms}ms"

        # Only adjust if timestamps are relative
        if timestamp_mode == "relative":
            print(f"      Adding {offset_seconds}s offset to timestamps...")
            offset_ms = offset_seconds * 1000

            # Adjust all sentences
            adjusted_items = []
            for item in transcript.agenda_items:
                adjusted_blocks = []
                for block in item.speech_blocks:
                    adjusted_sentences = []
                    for sentence in block.sentences:
                        original_ms = parse_time(sentence.start_time)
                        new_ms = original_ms + offset_ms
                        adjusted_sentences.append(
                            Sentence(
                                start_time=format_time(new_ms),
                                text=sentence.text,
                            )
                        )
                    adjusted_blocks.append(
                        SpeechBlock(
                            speaker_name=block.speaker_name,
                            speaker_id=block.speaker_id,
                            sentences=adjusted_sentences,
                        )
                    )
                adjusted_items.append(
                    TranscriptAgendaItem(
                        topic_title=item.topic_title,
                        speech_blocks=adjusted_blocks,
                    )
                )

            transcript = SessionTranscript(
                session_title=transcript.session_title,
                date=transcript.date,
                agenda_items=adjusted_items,
            )
        else:
            print("      Timestamps are already absolute - no adjustment needed")

        # Filter out-of-range timestamps
        transcript = self._validate_and_filter_timestamps(transcript, chunk_start, chunk_end)

        return transcript

    def _merge_transcripts(self, transcripts: list[SessionTranscript]) -> SessionTranscript:
        """
        Merge multiple chunk transcripts into one.

        Args:
            transcripts: List of transcripts to merge

        Returns:
            Merged transcript
        """
        if not transcripts:
            raise ValueError("No transcripts to merge")

        if len(transcripts) == 1:
            return transcripts[0]

        # Use first transcript as base
        base = transcripts[0]
        merged_items = list(base.agenda_items)

        # Merge subsequent transcripts
        for transcript in transcripts[1:]:
            for new_item in transcript.agenda_items:
                # Find matching agenda item by title
                matching_item = None
                for existing_item in merged_items:
                    if existing_item.topic_title == new_item.topic_title:
                        matching_item = existing_item
                        break

                if matching_item:
                    # Merge speech blocks, handling speaker continuity
                    last_block = (
                        matching_item.speech_blocks[-1] if matching_item.speech_blocks else None
                    )
                    first_new_block = new_item.speech_blocks[0] if new_item.speech_blocks else None

                    # Check if same speaker across chunk boundary
                    # Prefer speaker_id if available, fallback to speaker_name
                    same_speaker = False
                    if last_block and first_new_block:
                        if last_block.speaker_id and first_new_block.speaker_id:
                            same_speaker = last_block.speaker_id == first_new_block.speaker_id
                        else:
                            same_speaker = last_block.speaker_name == first_new_block.speaker_name

                    if same_speaker:
                        # Same speaker across chunk boundary - merge blocks
                        last_block.sentences.extend(first_new_block.sentences)
                        matching_item.speech_blocks.extend(new_item.speech_blocks[1:])
                    else:
                        # Different speakers - just append
                        matching_item.speech_blocks.extend(new_item.speech_blocks)
                else:
                    # New agenda item - add it
                    merged_items.append(new_item)

        return SessionTranscript(
            session_title=base.session_title,
            date=base.date,
            agenda_items=merged_items,
        )
