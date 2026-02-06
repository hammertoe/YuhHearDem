"""Integration test for video transcription timing accuracy.

This test verifies that the transcription service correctly identifies
timestamps for video segments. It uses a real YouTube video and Gemini API.

To run this test:
    pytest tests/test_services/test_video_transcription_timing.py -v

Expected timings will be printed for manual verification before finalizing test assertions.
"""

import os
from datetime import date
from pathlib import Path

import pytest
from pytest import fixture

from parsers.models import AgendaItem, OrderPaper, OrderPaperSpeaker
from parsers.video_transcript import VideoTranscriptionParser
from services.gemini import GeminiClient

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, skip


TEST_VIDEO_URL = "https://www.youtube.com/watch?v=P6cUJb9xqIs"


def _check_api_key():
    """Check if API key is available - helper for skip markers."""
    return bool(os.getenv("GOOGLE_API_KEY"))


@fixture
def gemini_client():
    """Create a real Gemini client with temperature=0 for deterministic results."""
    if not _check_api_key():
        pytest.skip("GOOGLE_API_KEY not set")
    return GeminiClient(temperature=0.0)


@fixture
def gemini_client_no_thinking():
    """Create a Gemini client with thinking disabled (thinking_budget=0)."""
    if not _check_api_key():
        pytest.skip("GOOGLE_API_KEY not set")
    return GeminiClient(temperature=0.0, thinking_budget=0)


@fixture
def gemini_client_with_thinking():
    """Create a Gemini client with model-controlled thinking (thinking_budget=-1)."""
    if not _check_api_key():
        pytest.skip("GOOGLE_API_KEY not set")
    return GeminiClient(temperature=0.0, thinking_budget=-1)


@fixture
def sample_order_paper():
    """Create a sample order paper for testing."""
    return OrderPaper(
        session_title="Barbados House of Assembly Session",
        session_date=date(2024, 1, 15),
        sitting_number="1",
        speakers=[
            OrderPaperSpeaker(name="Mr. Speaker", title="Hon.", role="Speaker"),
            OrderPaperSpeaker(name="John Smith", title="Hon.", role="Member"),
            OrderPaperSpeaker(name="Jane Doe", title="Hon.", role="Member"),
        ],
        agenda_items=[
            AgendaItem(
                topic_title="Welcome and Opening",
                primary_speaker="Mr. Speaker",
            ),
            AgendaItem(
                topic_title="Discussion on Legislation",
                primary_speaker="John Smith",
            ),
        ],
    )


def _parse_timecode(time_str: str) -> int:
    """Parse time string to total milliseconds.

    Format: "XmYsZms" (e.g., "0m5s250ms")

    Returns:
        Total milliseconds from start of video
    """
    import re

    match = re.match(r"(\d+)m(\d+)s(\d+)ms", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
    minutes, seconds, ms = map(int, match.groups())
    return (minutes * 60 + seconds) * 1000 + ms


def _print_transcript_with_timestamps(
    transcript, segment_start: int = 0, segment_end: int | None = None
):
    """Print transcript with timestamps for manual verification.

    Args:
        transcript: SessionTranscript object
        segment_start: Start time of the video segment processed (in seconds)
        segment_end: End time of the video segment processed (in seconds)
    """
    print("\n" + "=" * 80)
    print("TRANSCRIPTION WITH TIMESTAMPS")
    print("=" * 80)
    print(f"Session: {transcript.session_title}")
    print(f"Date: {transcript.date}")
    print(f"Video Segment: {segment_start}s - {segment_end}s")
    print("=" * 80)

    for i, agenda_item in enumerate(transcript.agenda_items, 1):
        print(f"\n--- Agenda Item {i}: {agenda_item.topic_title} ---")

        for block in agenda_item.speech_blocks:
            speaker_name = block.speaker_name
            speaker_id = block.speaker_id or "N/A"
            print(f"\n  Speaker: {speaker_name} (ID: {speaker_id})")

            for sentence in block.sentences:
                time_ms = _parse_timecode(sentence.start_time)
                time_sec = time_ms / 1000
                time_display = sentence.start_time

                # Show time in multiple formats for easy verification
                print(f"    [{time_display}] ({time_sec:.3f}s) {sentence.text}")

    print("\n" + "=" * 80)
    print("END OF TRANSCRIPTION")
    print("=" * 80)


# Skip if no API key - evaluated at test collection time
pytestmark = pytest.mark.skipif(
    not _check_api_key(), reason="GOOGLE_API_KEY environment variable not set"
)


@pytest.mark.slow
class TestVideoTranscriptionTiming:
    """Integration tests for verifying transcription timestamp accuracy.

    These tests use real API calls to Gemini and should be run manually
    to verify timing accuracy before finalizing test assertions.

    Run with:
        GOOGLE_API_KEY=your_key pytest tests/test_services/test_video_transcription_timing.py -v
    """

    def test_transcribe_mid_video_segment_with_timing(
        self,
        gemini_client,
        sample_order_paper,
    ):
        """Transcribe a segment starting at 5 minutes to test mid-video timing.

        This verifies that timestamps are relative to video start, not segment start.
        If the video is processed starting at 300s (5 minutes), the timestamps
        should be around 300s+, not starting from 0s.
        """
        parser = VideoTranscriptionParser(
            gemini_client=gemini_client,
            chunk_size=60,
            fuzzy_threshold=85,
        )

        # Define test segment: 30 seconds starting at 5 minutes
        segment_start = 300  # 5 minutes
        segment_end = 330  # 5:30

        print(f"\nTranscribing video segment: {segment_start}s (5:00) to {segment_end}s (5:30)")
        print(f"Video URL: {TEST_VIDEO_URL}")

        speaker_id_mapping = {}
        transcript, _ = parser.transcribe(
            video_url=TEST_VIDEO_URL,
            order_paper=sample_order_paper,
            speaker_id_mapping=speaker_id_mapping,
            fps=0.25,
            start_time=segment_start,
            end_time=segment_end,
            auto_chunk=False,
            video_duration=30,
        )

        _print_transcript_with_timestamps(transcript, segment_start, segment_end)

        # Collect timestamps
        all_timestamps = []
        for agenda_item in transcript.agenda_items:
            for block in agenda_item.speech_blocks:
                for sentence in block.sentences:
                    time_ms = _parse_timecode(sentence.start_time)
                    all_timestamps.append((time_ms, sentence.start_time))

        assert all_timestamps, "Should have timestamps"

        # Check that timestamps are in the expected range (around 5:00-5:30)
        first_time_ms = all_timestamps[0][0]
        segment_start_ms = segment_start * 1000
        segment_end_ms = segment_end * 1000

        print("\nMid-video Timing Verification:")
        print(f"  Expected range: {segment_start}s - {segment_end}s")
        print(f"  First timestamp: {all_timestamps[0][1]} ({first_time_ms / 1000:.3f}s)")
        print(f"  Last timestamp: {all_timestamps[-1][1]} ({all_timestamps[-1][0] / 1000:.3f}s)")

        # The timestamps should be near 300s (5 minutes), not near 0s
        # Allow 10 second tolerance
        assert segment_start_ms - 10000 <= first_time_ms <= segment_end_ms + 10000, (
            f"First timestamp {all_timestamps[0][1]} should be in range "
            f"[{segment_start}s, {segment_end}s] but was {first_time_ms / 1000:.3f}s. "
            f"This indicates timestamps are relative to segment, not absolute from video start."
        )

        print("\n✓ Timestamps appear to be absolute (relative to video start)")

    def test_transcribe_5_minute_segment_check_drift(
        self,
        gemini_client,
        sample_order_paper,
    ):
        """Transcribe a 5-minute segment to check for timing drift.

        This test checks if timestamps drift over a shorter 5-minute segment.
        We transcribe 5 minutes (0s to 300s) and verify:
        1. Early timestamps are accurate (first 2 minutes)
        2. Mid timestamps are accurate (2-3.5 minutes)
        3. Late timestamps are accurate (3.5-5 minutes)

        With temperature=0, results should be deterministic.
        """
        parser = VideoTranscriptionParser(
            gemini_client=gemini_client,
            chunk_size=300,  # 5 minutes - process as one chunk
            fuzzy_threshold=85,
        )

        # Define test segment: 5 minutes from start
        segment_start = 0
        segment_end = 300  # 5 minutes

        print(f"\n{'=' * 80}")
        print("5-MINUTE DRIFT TEST")
        print(f"{'=' * 80}")
        print(f"Transcribing video segment: {segment_start}s to {segment_end}s (5 minutes)")
        print(f"Video URL: {TEST_VIDEO_URL}")
        print("This will take a few minutes due to the video length...")

        # Transcribe the segment
        speaker_id_mapping = {}
        transcript, new_speakers = parser.transcribe(
            video_url=TEST_VIDEO_URL,
            order_paper=sample_order_paper,
            speaker_id_mapping=speaker_id_mapping,
            fps=0.25,
            start_time=segment_start,
            end_time=segment_end,
            auto_chunk=False,
            video_duration=segment_end - segment_start,
        )

        # Print the transcript with timestamps
        _print_transcript_with_timestamps(transcript, segment_start, segment_end)

        # Collect all timestamps for drift analysis
        all_timestamps = []
        for agenda_item in transcript.agenda_items:
            for block in agenda_item.speech_blocks:
                for sentence in block.sentences:
                    time_ms = _parse_timecode(sentence.start_time)
                    all_timestamps.append((time_ms, sentence.start_time, sentence.text))

        assert all_timestamps, "Should have at least one sentence with timestamp"

        # Analyze timestamps across the 5-minute window
        print(f"\n{'=' * 80}")
        print("DRIFT ANALYSIS - Timestamp Distribution")
        print(f"{'=' * 80}")

        # Divide into early, mid, and late sections
        early_cutoff = 120000  # 2 minutes in ms
        mid_start = 120000  # 2 minutes
        mid_end = 210000  # 3.5 minutes
        late_start = 210000  # 3.5 minutes

        early_timestamps = [t for t in all_timestamps if t[0] < early_cutoff]
        mid_timestamps = [t for t in all_timestamps if mid_start <= t[0] <= mid_end]
        late_timestamps = [t for t in all_timestamps if t[0] > late_start]

        print("\nTimestamp Distribution:")
        print(f"  Early (0-2 min):     {len(early_timestamps)} sentences")
        print(f"  Mid (2-3.5 min):     {len(mid_timestamps)} sentences")
        print(f"  Late (3.5-5 min):    {len(late_timestamps)} sentences")
        print(f"  Total:               {len(all_timestamps)} sentences")

        if early_timestamps:
            print("\nEarly Section (0-2 min):")
            print(f"  First: {early_timestamps[0][1]} - {early_timestamps[0][2][:60]}...")
            print(f"  Last:  {early_timestamps[-1][1]} - {early_timestamps[-1][2][:60]}...")

        if mid_timestamps:
            print("\nMid Section (2-3.5 min):")
            print(f"  First: {mid_timestamps[0][1]} - {mid_timestamps[0][2][:60]}...")
            print(f"  Last:  {mid_timestamps[-1][1]} - {mid_timestamps[-1][2][:60]}...")

        if late_timestamps:
            print("\nLate Section (3.5-5 min) - CHECK FOR DRIFT HERE:")
            print(f"  First: {late_timestamps[0][1]} - {late_timestamps[0][2][:60]}...")
            print(f"  Last:  {late_timestamps[-1][1]} - {late_timestamps[-1][2][:60]}...")

        # Calculate average spacing to detect drift
        if len(all_timestamps) > 1:
            spacings = [
                all_timestamps[i][0] - all_timestamps[i - 1][0]
                for i in range(1, len(all_timestamps))
            ]
            avg_spacing = sum(spacings) / len(spacings)
            max_spacing = max(spacings)
            min_spacing = min(spacings)

            print("\nTiming Statistics:")
            print(f"  Average spacing: {avg_spacing / 1000:.3f}s")
            print(f"  Min spacing:     {min_spacing / 1000:.3f}s")
            print(f"  Max spacing:     {max_spacing / 1000:.3f}s")
            print(
                f"  Std deviation:   {(sum((s - avg_spacing) ** 2 for s in spacings) / len(spacings)) ** 0.5 / 1000:.3f}s"
            )

        # Drift detection - compare late timestamps to expected range
        print(f"\n{'=' * 80}")
        print("DRIFT DETECTION")
        print(f"{'=' * 80}")

        if late_timestamps:
            first_late_time = late_timestamps[0][0]
            last_late_time = late_timestamps[-1][0]

            # Expected: timestamps should be 210s+ (3.5 minutes+)
            expected_min_late = late_start  # 210000 ms

            print(f"Late timestamps should be between {late_start / 1000:.1f}s and {segment_end}s")
            print(
                f"Actual late timestamps: {first_late_time / 1000:.3f}s to {last_late_time / 1000:.3f}s"
            )

            # Check if late timestamps are in expected range
            if first_late_time < expected_min_late - 30000:  # More than 30s early
                print("\n⚠️  POTENTIAL DRIFT DETECTED!")
                print(f"   Expected first late timestamp around {expected_min_late / 1000:.1f}s")
                print(f"   Got: {first_late_time / 1000:.3f}s")
                print(f"   Difference: {(expected_min_late - first_late_time) / 1000:.1f}s")
            else:
                print("\n✓ Late timestamps appear to be in correct range (no obvious drift)")

        # Summary
        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total sentences transcribed: {len(all_timestamps)}")
        print(
            f"Time range covered: {all_timestamps[0][0] / 1000:.3f}s to {all_timestamps[-1][0] / 1000:.3f}s"
        )
        print(f"Expected range: {segment_start}s to {segment_end}s")

        # Basic assertions that should always pass
        assert len(all_timestamps) > 0, "Should have transcribed some content"

    def test_transcribe_10_minute_segment_check_drift(
        self,
        gemini_client,
        sample_order_paper,
    ):
        """Transcribe a 10-minute segment to check for timing drift.

        This test specifically checks if timestamps drift over longer segments.
        We transcribe 10 minutes (0s to 600s) and verify:
        1. Early timestamps are accurate (first few minutes)
        2. Mid timestamps are accurate (around 5 minutes)
        3. Late timestamps are accurate (last few minutes) - this is where drift shows

        With temperature=0, results should be deterministic.

        Drift Detection:
        - Compare actual timestamps against expected video time
        - Look for systematic offset that increases over time
        - Check if sentences near the end have incorrect timestamps

        After manual verification of the video, we can add assertions for:
        - Expected content at specific timestamps
        - Maximum acceptable drift (e.g., +/- 5 seconds over 10 minutes)
        """
        parser = VideoTranscriptionParser(
            gemini_client=gemini_client,
            chunk_size=600,  # 10 minutes - process as one chunk
            fuzzy_threshold=85,
        )

        # Define test segment: 10 minutes from start
        segment_start = 0
        segment_end = 600  # 10 minutes

        print(f"\n{'=' * 80}")
        print("10-MINUTE DRIFT TEST")
        print(f"{'=' * 80}")
        print(f"Transcribing video segment: {segment_start}s to {segment_end}s (10 minutes)")
        print(f"Video URL: {TEST_VIDEO_URL}")
        print("This will take several minutes due to the video length...")

        # Transcribe the segment
        speaker_id_mapping = {}
        transcript, new_speakers = parser.transcribe(
            video_url=TEST_VIDEO_URL,
            order_paper=sample_order_paper,
            speaker_id_mapping=speaker_id_mapping,
            fps=0.25,  # Low FPS for cost savings, but may affect timing accuracy
            start_time=segment_start,
            end_time=segment_end,
            auto_chunk=False,  # Don't chunk - we want to test single-pass accuracy
            video_duration=segment_end - segment_start,
        )

        # Print the transcript with timestamps
        _print_transcript_with_timestamps(transcript, segment_start, segment_end)

        # Collect all timestamps for drift analysis
        all_timestamps = []
        for agenda_item in transcript.agenda_items:
            for block in agenda_item.speech_blocks:
                for sentence in block.sentences:
                    time_ms = _parse_timecode(sentence.start_time)
                    all_timestamps.append((time_ms, sentence.start_time, sentence.text))

        assert all_timestamps, "Should have at least one sentence with timestamp"

        # Analyze timestamps across the 10-minute window
        print(f"\n{'=' * 80}")
        print("DRIFT ANALYSIS - Timestamp Distribution")
        print(f"{'=' * 80}")

        # Divide into early, mid, and late sections
        early_cutoff = 180000  # 3 minutes in ms
        mid_start = 240000  # 4 minutes
        mid_end = 360000  # 6 minutes
        late_start = 480000  # 8 minutes

        early_timestamps = [t for t in all_timestamps if t[0] < early_cutoff]
        mid_timestamps = [t for t in all_timestamps if mid_start <= t[0] <= mid_end]
        late_timestamps = [t for t in all_timestamps if t[0] > late_start]

        print("\nTimestamp Distribution:")
        print(f"  Early (0-3 min):    {len(early_timestamps)} sentences")
        print(f"  Mid (4-6 min):      {len(mid_timestamps)} sentences")
        print(f"  Late (8-10 min):    {len(late_timestamps)} sentences")
        print(f"  Total:              {len(all_timestamps)} sentences")

        if early_timestamps:
            print("\nEarly Section (0-3 min):")
            print(f"  First: {early_timestamps[0][1]} - {early_timestamps[0][2][:60]}...")
            print(f"  Last:  {early_timestamps[-1][1]} - {early_timestamps[-1][2][:60]}...")

        if mid_timestamps:
            print("\nMid Section (4-6 min):")
            print(f"  First: {mid_timestamps[0][1]} - {mid_timestamps[0][2][:60]}...")
            print(f"  Last:  {mid_timestamps[-1][1]} - {mid_timestamps[-1][2][:60]}...")

        if late_timestamps:
            print("\nLate Section (8-10 min) - CHECK FOR DRIFT HERE:")
            print(f"  First: {late_timestamps[0][1]} - {late_timestamps[0][2][:60]}...")
            print(f"  Last:  {late_timestamps[-1][1]} - {late_timestamps[-1][2][:60]}...")

        # Calculate average spacing to detect drift
        if len(all_timestamps) > 1:
            spacings = [
                all_timestamps[i][0] - all_timestamps[i - 1][0]
                for i in range(1, len(all_timestamps))
            ]
            avg_spacing = sum(spacings) / len(spacings)
            max_spacing = max(spacings)
            min_spacing = min(spacings)

            print("\nTiming Statistics:")
            print(f"  Average spacing: {avg_spacing / 1000:.3f}s")
            print(f"  Min spacing:     {min_spacing / 1000:.3f}s")
            print(f"  Max spacing:     {max_spacing / 1000:.3f}s")
            print(
                f"  Std deviation:   {(sum((s - avg_spacing) ** 2 for s in spacings) / len(spacings)) ** 0.5 / 1000:.3f}s"
            )

        # Drift detection - compare late timestamps to expected range
        print(f"\n{'=' * 80}")
        print("DRIFT DETECTION")
        print(f"{'=' * 80}")

        if late_timestamps:
            first_late_time = late_timestamps[0][0]
            last_late_time = late_timestamps[-1][0]

            # Expected: timestamps should be 480s+ (8 minutes+)
            expected_min_late = late_start  # 480000 ms

            print(f"Late timestamps should be between {late_start / 1000:.0f}s and {segment_end}s")
            print(
                f"Actual late timestamps: {first_late_time / 1000:.3f}s to {last_late_time / 1000:.3f}s"
            )

            # Check if late timestamps are in expected range
            # If they're significantly off (e.g., showing 200s when it should be 500s), that's drift
            if first_late_time < expected_min_late - 30000:  # More than 30s early
                print("\n⚠️  POTENTIAL DRIFT DETECTED!")
                print(f"   Expected first late timestamp around {expected_min_late / 1000:.0f}s")
                print(f"   Got: {first_late_time / 1000:.3f}s")
                print(f"   Difference: {(expected_min_late - first_late_time) / 1000:.1f}s")
            else:
                print("\n✓ Late timestamps appear to be in correct range (no obvious drift)")

        # Summary
        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total sentences transcribed: {len(all_timestamps)}")
        print(
            f"Time range covered: {all_timestamps[0][0] / 1000:.3f}s to {all_timestamps[-1][0] / 1000:.3f}s"
        )
        print(f"Expected range: {segment_start}s to {segment_end}s")

        # TODO: After manual verification, add specific drift assertions
        # Example:
        # assert not drift_detected, "Timing drift detected in late segment"
        #
        # Or quantify acceptable drift:
        # max_acceptable_drift_ms = 10000  # 10 seconds over 10 minutes
        # if late_timestamps:
        #     actual_drift = expected_min_late - first_late_time
        #     assert abs(actual_drift) < max_acceptable_drift_ms, \
        #         f"Drift of {actual_drift/1000:.1f}s exceeds acceptable threshold"

        # Basic assertions that should always pass
        assert len(all_timestamps) > 0, "Should have transcribed some content"

        # Check timestamps are in order
        for i in range(1, len(all_timestamps)):
            assert all_timestamps[i][0] >= all_timestamps[i - 1][0], (
                f"Timestamps out of order at index {i}"
            )

        # Check timestamps are within expected bounds
        for time_ms, time_str, _text in all_timestamps:
            assert segment_start * 1000 - 10000 <= time_ms <= segment_end * 1000 + 10000, (
                f"Timestamp {time_str} outside expected range"
            )

        print(f"\n{'=' * 80}")
        print("Test completed - review output above for drift issues")
        print(f"{'=' * 80}")
