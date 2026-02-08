"""Video ingestion script using the unified pipeline.

This script ingests parliamentary videos with:
- Structured transcript extraction (constrained decoding)
- Speaker deduplication
- Chunked entity extraction (7 sentences, 2 overlap)
- Sentence-level provenance tracking

Usage:
    python scripts/ingest_video_unified.py --url "https://youtube.com/watch?v=..." --date 2024-01-15 --chamber senate

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    GOOGLE_API_KEY: Gemini API key
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from core.database import get_session_maker
from parsers.order_paper_parser import OrderPaperParser
from services.gemini import GeminiClient
from services.unified_ingestion import UnifiedIngestionPipeline

settings = get_settings()


def parse_date(date_str: str) -> datetime.date:
    """Parse date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


async def ingest_video(
    video_url: str,
    video_id: str,
    session_date: datetime.date,
    chamber: str,
    sitting_number: str | None,
    order_paper_path: str | None,
    fps: float,
    minutes: int | None,
    verbose: bool,
    no_thinking: bool,
) -> None:
    """Ingest a single video."""
    session_maker = get_session_maker()

    async with session_maker() as session:
        print("=" * 60)
        print("Ingestion Pipeline Configuration")
        print("=" * 60)
        print(f"  Video: {video_url}")
        print(f"  Date: {session_date}")
        print(f"  Chamber: {chamber}")
        if sitting_number:
            print(f"  Sitting: {sitting_number}")
        if minutes:
            print(f"  Time limit: {minutes} minutes")
        if no_thinking:
            print(f"  Thinking mode: DISABLED")
        print(f"  FPS: {fps}")
        if verbose:
            print(f"  Verbose mode: ENABLED")
        print()

        # Initialize Gemini client
        thinking_budget = None if no_thinking else -1  # -1 = model controls
        gemini_client = GeminiClient(
            api_key=settings.google_api_key,
            model="gemini-3-flash-preview",
            temperature=0.0,
            max_output_tokens=65536,
            thinking_budget=thinking_budget,
        )

        print(f"Using model: {gemini_client.model}")
        if verbose:
            print(f"Thinking budget: {thinking_budget if thinking_budget else 'Model default'}")
        print()

        # Load order paper speakers if provided
        order_paper_speakers = None
        if order_paper_path:
            print(f"Loading order paper: {order_paper_path}")
            parser = OrderPaperParser(gemini_client)
            from pathlib import Path

            order_paper = parser.parse(Path(order_paper_path))
            order_paper_speakers = [
                {"name": s.name, "title": s.title, "role": s.role} for s in order_paper.speakers
            ]
            print(f"  Found {len(order_paper_speakers)} speakers in order paper")
            print()

        # Initialize pipeline
        pipeline = UnifiedIngestionPipeline(
            session=session,
            gemini_client=gemini_client,
            verbose=verbose,
        )

        print("=" * 60)
        print("Starting Ingestion")
        print("=" * 60)
        print()

        try:
            # Calculate end time if minutes specified
            end_time = minutes * 60 if minutes else None
            if verbose and end_time:
                print(f"Processing first {minutes} minutes (0 to {end_time}s)")

            # Run ingestion
            result = await pipeline.ingest_video(
                video_url=video_url,
                video_id=video_id,
                session_date=session_date,
                chamber=chamber,
                sitting_number=sitting_number,
                order_paper_speakers=order_paper_speakers,
                fps=fps,
                end_time=end_time,
            )

            print("\nIngestion Complete!")
            print(f"  Session ID: {result.session_id}")
            print(f"  Video ID: {result.video_id}")
            print(f"\nSpeakers:")
            print(f"  Created: {result.speakers_created}")
            print(f"  Matched: {result.speakers_matched}")
            print(f"\nAgenda Items: {result.agenda_items_created}")
            print(f"\nKnowledge Graph:")
            print(f"  Entities: {result.entities_extracted}")
            print(f"  Relationships: {result.relationships_extracted}")
            print(f"  Mentions: {result.mentions_created}")

            if result.errors:
                print(f"\nErrors:")
                for error in result.errors:
                    print(f"  - {error}")

        except Exception as e:
            print(f"\nError during ingestion: {e}", file=sys.stderr)
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Ingest parliamentary video using unified pipeline"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="YouTube video URL",
    )
    parser.add_argument(
        "--video-id",
        help="YouTube video ID (extracted from URL if not provided)",
    )
    parser.add_argument(
        "--date",
        required=True,
        type=parse_date,
        help="Session date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--chamber",
        required=True,
        choices=["senate", "house"],
        help="Chamber (senate or house)",
    )
    parser.add_argument(
        "--sitting",
        help="Sitting number (e.g., '67')",
    )
    parser.add_argument(
        "--order-paper",
        help="Path to order paper PDF for speaker context",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=0.5,
        help="Frames per second for video analysis (default: 0.5)",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        help="Only ingest first X minutes of video (for quick testing)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress information",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="Disable LLM thinking mode for faster processing",
    )

    args = parser.parse_args()

    # Extract video ID from URL if not provided
    video_id = args.video_id
    if not video_id:
        # Extract from YouTube URL
        if "v=" in args.url:
            video_id = args.url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in args.url:
            video_id = args.url.split("youtu.be/")[1].split("?")[0]
        else:
            print("Error: Could not extract video ID from URL", file=sys.stderr)
            sys.exit(1)

    # Run ingestion
    asyncio.run(
        ingest_video(
            video_url=args.url,
            video_id=video_id,
            session_date=args.date,
            chamber=args.chamber,
            sitting_number=args.sitting,
            order_paper_path=args.order_paper,
            fps=args.fps,
        )
    )


if __name__ == "__main__":
    main()
