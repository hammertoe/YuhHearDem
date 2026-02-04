#!/usr/bin/env python3
"""Daily auto-processing pipeline for parliament videos.

This script runs daily to:
1. Scrape new order papers from parliament website
2. Check YouTube channel for new videos
3. Match videos to order papers automatically
4. Transcribe matched videos using Gemini (no download required)

Designed to run via cron daily at a scheduled time.

Usage:
    # Run full pipeline
    python scripts/daily_pipeline.py

    # Run specific steps only
    python scripts/daily_pipeline.py --step scrape
    python scripts/daily_pipeline.py --step match
    python scripts/daily_pipeline.py --step process

    # Dry run (don't make changes)
    python scripts/daily_pipeline.py --dry-run

    # With notifications
    python scripts/daily_pipeline.py --notify webhook_url
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import and_, select

from core.database import get_session_maker
from models.order_paper import OrderPaper
from models.video import Video
from parsers.models import OrderPaper as ParsedOrderPaper
from parsers.video_transcript import VideoTranscriptionParser
from services.gemini import GeminiClient
from services.video_paper_matcher import TitlePatternMatcher, VideoPaperMatcher

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/daily_pipeline.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DailyPipeline:
    """Daily processing pipeline for parliament videos."""

    def __init__(
        self,
        dry_run: bool = False,
        match_threshold: int = 75,
        max_videos: int = 50,
        max_papers: Optional[int] = None,
    ):
        self.dry_run = dry_run
        self.match_threshold = match_threshold
        self.max_videos = max_videos
        self.max_papers = max_papers
        self.matcher = VideoPaperMatcher()
        self.results = {
            "papers_scraped": 0,
            "papers_new": 0,
            "videos_found": 0,
            "videos_new": 0,
            "videos_matched_auto": 0,
            "videos_matched_ambiguous": 0,
            "videos_processed": 0,
            "errors": [],
        }

    async def run(self, steps: Optional[list] = None):
        """Run the full pipeline or specific steps."""
        steps = steps or ["scrape", "monitor", "match", "process"]

        logger.info("=" * 80)
        logger.info("DAILY PARLIAMENT PIPELINE")
        logger.info("=" * 80)
        logger.info(f"Steps: {', '.join(steps)}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"Match threshold: {self.match_threshold}")
        logger.info(f"Started: {datetime.now().isoformat()}")
        logger.info("=" * 80)

        try:
            if "scrape" in steps:
                await self.scrape_order_papers()

            if "monitor" in steps:
                await self.monitor_youtube()

            if "match" in steps:
                await self.match_videos_to_papers()

            if "process" in steps:
                await self.process_matched_videos()

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self.results["errors"].append(str(e))

        finally:
            self._print_summary()

    async def scrape_order_papers(self):
        """Step 1: Scrape new order papers from parliament website."""
        logger.info("\n[STEP 1] Scraping order papers...")

        try:
            from scripts.scrape_session_papers import SessionPaperScraper

            scraper = SessionPaperScraper()

            # Scrape House papers
            house_papers = scraper.scrape_session_papers(
                chamber="house", max_papers=self.max_papers
            )
            logger.info(f"Found {len(house_papers)} House papers")

            # Scrape Senate papers
            senate_papers = scraper.scrape_session_papers(
                chamber="senate", max_papers=self.max_papers
            )
            logger.info(f"Found {len(senate_papers)} Senate papers")

            self.results["papers_scraped"] = len(house_papers) + len(senate_papers)

            if not self.dry_run:
                # Ingest into database
                from scripts.ingest_order_paper import OrderPaperIngestor

                gemini_client = GeminiClient()
                ingestor = OrderPaperIngestor(gemini_client=gemini_client)
                session_maker = get_session_maker()

                for paper_data in house_papers + senate_papers:
                    try:
                        # Download and ingest
                        pdf_path = Path("data/papers") / f"{paper_data['title']}.pdf"
                        if scraper.download_paper(paper_data["pdf_url"], pdf_path):
                            result = await ingestor.ingest_pdf(session_maker, pdf_path)
                            if result["status"] == "success":
                                self.results["papers_new"] += 1

                    except Exception as e:
                        logger.warning(f"Failed to ingest {paper_data['title']}: {e}")
            else:
                logger.info("[DRY RUN] Would ingest new papers")

        except Exception as e:
            logger.error(f"Error scraping papers: {e}")
            self.results["errors"].append(f"Scrape error: {e}")

    async def monitor_youtube(self):
        """Step 2: Monitor YouTube for new videos."""
        logger.info("\n[STEP 2] Monitoring YouTube...")

        try:
            # Use yt-dlp to list recent videos from channel
            import yt_dlp

            channel_url = "https://www.youtube.com/@barbadosparliamentchannel/streams"

            ydl_opts = {
                "quiet": True,
                "extract_flat": True,
                "playlistend": self.max_videos,  # Check last N videos
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist = ydl.extract_info(channel_url, download=False)

                if not playlist or "entries" not in playlist:
                    logger.warning("No videos found on channel")
                    return

                videos = playlist["entries"]
                self.results["videos_found"] = len(videos)
                logger.info(f"Found {len(videos)} videos on channel")

                if not self.dry_run:
                    async with get_session_maker()() as db:
                        for video_info in videos:
                            try:
                                youtube_id = video_info.get("id")
                                if not youtube_id:
                                    continue

                                # Check if already in database
                                existing = await db.execute(
                                    select(Video).where(Video.youtube_id == youtube_id)
                                )
                                if existing.scalar_one_or_none():
                                    continue

                                # Extract metadata
                                title = video_info.get("title", "")
                                metadata = TitlePatternMatcher.parse_video_title(title)

                                session_date = metadata.extracted_session_date
                                if isinstance(session_date, datetime):
                                    normalized_session_date = session_date
                                elif session_date:
                                    normalized_session_date = datetime.combine(
                                        session_date,
                                        datetime.min.time(),
                                    )
                                else:
                                    normalized_session_date = datetime.now(timezone.utc).replace(
                                        tzinfo=None
                                    )

                                # Create video record
                                video = Video(
                                    youtube_id=youtube_id,
                                    youtube_url=f"https://youtube.com/watch?v={youtube_id}",
                                    title=title,
                                    session_date=normalized_session_date,
                                    chamber=metadata.extracted_chamber,
                                    duration_seconds=video_info.get("duration"),
                                    transcript=None,
                                    created_at=datetime.now(),
                                )

                                db.add(video)
                                self.results["videos_new"] += 1
                                logger.info(f"Added new video: {title[:50]}...")

                            except Exception as e:
                                logger.warning(f"Failed to add video {youtube_id}: {e}")

                        await db.commit()
                else:
                    logger.info("[DRY RUN] Would add new videos")

        except Exception as e:
            logger.error(f"Error monitoring YouTube: {e}")
            self.results["errors"].append(f"YouTube error: {e}")

    async def match_videos_to_papers(self):
        """Step 3: Match videos to order papers."""
        logger.info("\n[STEP 3] Matching videos to order papers...")

        try:
            async with get_session_maker()() as db:
                # Load all order papers
                papers_result = await db.execute(select(OrderPaper))
                order_papers = papers_result.scalars().all()

                # Load unmatched videos (videos without order_paper_id)
                videos_result = await db.execute(
                    select(Video).where(Video.order_paper_id.is_(None))
                )
                videos = videos_result.scalars().all()

                logger.info(f"Matching {len(videos)} videos against {len(order_papers)} papers")

                for video in videos:
                    try:
                        # Extract metadata
                        metadata = TitlePatternMatcher.parse_video_title(video.title)
                        metadata.youtube_id = video.youtube_id

                        # Skip videos without valid metadata (chamber and session_date)
                        if not metadata.extracted_chamber or not metadata.extracted_session_date:
                            logger.debug(
                                f"Skipping video without valid metadata: {video.title[:50]}"
                            )
                            continue

                        # Run matching
                        result = self.matcher.match_video(
                            metadata, order_papers, auto_accept_threshold=self.match_threshold
                        )

                        if not result.is_ambiguous and result.matched_paper_id:
                            # Auto-accept - update Video to link to this order paper
                            if not self.dry_run:
                                video.order_paper_id = result.matched_paper_id
                                self.results["videos_matched_auto"] += 1
                                logger.info(
                                    f"✓ Auto-matched: '{video.title[:40]}...' "
                                    f"(score: {result.confidence_score})"
                                )
                            else:
                                self.results["videos_matched_auto"] += 1
                                logger.info(
                                    f"[DRY RUN] Would match: '{video.title[:40]}...' "
                                    f"(score: {result.confidence_score})"
                                )
                        elif result.is_ambiguous:
                            self.results["videos_matched_ambiguous"] += 1
                            logger.warning(
                                f"⚠ Ambiguous: '{video.title[:40]}...' - {result.ambiguity_reason}"
                            )

                    except Exception as e:
                        logger.warning(f"Failed to match video {video.id}: {e}")

                if not self.dry_run:
                    await db.commit()

        except Exception as e:
            logger.error(f"Error matching videos: {e}")
            self.results["errors"].append(f"Matching error: {e}")

    async def process_matched_videos(self):
        """Step 4: Transcribe matched videos using Gemini."""
        logger.info("\n[STEP 4] Transcribing matched videos...")

        try:
            async with get_session_maker()() as db:
                # Load videos that are matched but not yet transcribed
                # Join with OrderPaper to get linked order paper data
                videos_result = await db.execute(
                    select(Video, OrderPaper)
                    .join(OrderPaper, Video.order_paper_id == OrderPaper.id)
                    .where(
                        and_(
                            Video.transcript.is_(None),  # Not yet transcribed
                        )
                    )
                )
                video_paper_pairs = videos_result.all()

                logger.info(f"Processing {len(video_paper_pairs)} matched videos")

                # Initialize transcription service
                gemini_client = GeminiClient(temperature=0.0)
                parser = VideoTranscriptionParser(
                    gemini_client=gemini_client, chunk_size=600, fuzzy_threshold=85
                )

                for video, order_paper_record in video_paper_pairs:
                    try:
                        logger.info(f"Processing: {video.title[:50]}...")

                        if self.dry_run:
                            logger.info("[DRY RUN] Would transcribe")
                            self.results["videos_processed"] += 1
                            continue

                        # Get order paper as parsed object
                        order_paper = ParsedOrderPaper(
                            session_title=order_paper_record.session_title or video.title,
                            session_date=order_paper_record.session_date,
                            sitting_number=order_paper_record.sitting_number,
                            speakers=order_paper_record.speakers or [],
                            agenda_items=order_paper_record.agenda_items or [],
                        )

                        # Transcribe with order paper context using YouTube URL directly
                        transcript, _ = parser.transcribe(
                            video_url=video.youtube_url,
                            order_paper=order_paper,
                            speaker_id_mapping={},
                            fps=0.25,
                            start_time=0,
                            end_time=None,
                            auto_chunk=True,
                        )

                        # Save transcript to video record
                        video.transcript = transcript.to_dict()
                        video.transcript_processed_at = datetime.now()

                        self.results["videos_processed"] += 1
                        logger.info(f"✓ Transcribed: {len(transcript.agenda_items)} agenda items")

                    except Exception as e:
                        logger.error(f"Failed to process video {video.id}: {e}")
                        self.results["errors"].append(f"Processing error for {video.id}: {e}")

                await db.commit()

        except Exception as e:
            logger.error(f"Error processing videos: {e}")
            self.results["errors"].append(f"Processing error: {e}")

    def _print_summary(self):
        """Print pipeline summary."""
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Order papers scraped: {self.results['papers_scraped']}")
        logger.info(f"New papers added: {self.results['papers_new']}")
        logger.info(f"Videos found on YouTube: {self.results['videos_found']}")
        logger.info(f"New videos added: {self.results['videos_new']}")
        logger.info(f"Videos auto-matched: {self.results['videos_matched_auto']}")
        logger.info(f"Videos ambiguous: {self.results['videos_matched_ambiguous']}")
        logger.info(f"Videos processed: {self.results['videos_processed']}")
        logger.info(f"Errors: {len(self.results['errors'])}")
        logger.info("=" * 80)
        logger.info(f"Finished: {datetime.now().isoformat()}")
        logger.info("=" * 80)


async def main():
    parser = argparse.ArgumentParser(description="Daily pipeline for parliament video processing")
    parser.add_argument(
        "--step",
        choices=["scrape", "monitor", "match", "process", "all"],
        default="all",
        help="Run specific step only (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=75,
        help="Confidence threshold for auto-matching (default: 75)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=50,
        help="Maximum number of videos to fetch from YouTube (default: 50)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Maximum number of order papers to scrape (default: all)",
    )

    args = parser.parse_args()

    # Map step to pipeline steps
    if args.step == "all":
        steps = ["scrape", "monitor", "match", "process"]
    else:
        steps = [args.step]

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    pipeline = DailyPipeline(
        dry_run=args.dry_run,
        match_threshold=args.threshold,
        max_videos=args.max_videos,
        max_papers=args.max_papers,
    )

    await pipeline.run(steps=steps)


if __name__ == "__main__":
    asyncio.run(main())
