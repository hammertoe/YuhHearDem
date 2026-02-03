#!/usr/bin/env python3
"""CLI tool for matching YouTube videos to order papers.

Automatically matches videos to order papers based on session date and chamber.
Only ambiguous cases (multiple papers, low confidence) are shown for review.

Usage:
    # Match all unprocessed videos
    python scripts/match_videos_to_papers.py

    # Show only ambiguous matches for manual review
    python scripts/match_videos_to_papers.py --review-only

    # Auto-accept with lower threshold
    python scripts/match_videos_to_papers.py --threshold 80

    # Dry run (show what would be matched without making changes)
    python scripts/match_videos_to_papers.py --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dependencies import get_db_session
from models.video import Video
from models.order_paper import OrderPaper
from services.video_paper_matcher import VideoPaperMatcher, TitlePatternMatcher, MatchResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VideoPaperMatchingCLI:
    """CLI for matching videos to order papers."""

    def __init__(self, threshold: int = 90, dry_run: bool = False):
        self.matcher = VideoPaperMatcher()
        self.threshold = threshold
        self.dry_run = dry_run
        self.stats = {
            "total_videos": 0,
            "already_matched": 0,
            "auto_matched": 0,
            "ambiguous": 0,
            "no_candidates": 0,
        }

    async def run(self, review_only: bool = False):
        """Run of matching process."""
        logger.info("=" * 80)
        logger.info("VIDEO-ORDER PAPER MATCHING")
        logger.info("=" * 80)
        logger.info(f"Mode: {'REVIEW ONLY' if review_only else 'AUTO-PROCESS'}")
        logger.info(f"Auto-accept threshold: {self.threshold}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 80)

        async for db in get_db_session():
            # Load all order papers
            order_papers_result = await db.execute(
                select(OrderPaper).order_by(OrderPaper.session_date.desc())
            )
            order_papers = order_papers_result.scalars().all()
            logger.info(f"Loaded {len(order_papers)} order papers from database")

            # Load videos that need matching
            if review_only:
                # Only show videos that couldn't be auto-matched
                videos_result = await db.execute(
                    select(Video)
                    .where(Video.order_paper_id.is_(None))
                    .order_by(Video.session_date.desc().nulls_last())
                )
            else:
                # All unmatched videos
                videos_result = await db.execute(
                    select(Video)
                    .where(Video.order_paper_id.is_(None))
                    .order_by(Video.session_date.desc().nulls_last())
                )

            videos = videos_result.scalars().all()
            self.stats["total_videos"] = len(videos)
            logger.info(f"Found {len(videos)} videos needing matching")

            if not videos:
                logger.info("No videos to process. All videos are matched!")
                return

            # Process each video
            ambiguous_cases = []

            for video in videos:
                result = await self._process_video(db, video, order_papers)

                if result.is_ambiguous:
                    ambiguous_cases.append(result)
                    self.stats["ambiguous"] += 1
                elif result.matched_paper_id:
                    self.stats["auto_matched"] += 1
                else:
                    self.stats["no_candidates"] += 1

            # Show summary
            await self._show_summary(db, ambiguous_cases)

    async def _process_video(self, db, video: Video, order_papers: list) -> MatchResult:
        """Process a single video and return match result."""
        # Check if video is already matched (via order_papers query)
        existing_match = await db.execute(select(OrderPaper).where(OrderPaper.video_id == video.id))
        if existing_match.scalar_one_or_none():
            self.stats["already_matched"] += 1
            return MatchResult(
                video=video,
                matched_paper_id=str(existing_match.scalar_one_or_none().id),
                confidence_score=100,
                is_ambiguous=False,
            )

        # Extract metadata from video title
        metadata = TitlePatternMatcher.parse_video_title(video.title)
        metadata.youtube_id = video.youtube_id
        metadata.description = video.description or ""

        # If video already has chamber in database, use it
        if video.chamber:
            metadata.extracted_chamber = video.chamber

        # If video already has session_date in database, use it
        if video.session_date:
            metadata.extracted_session_date = video.session_date

        # Run matching
        result = self.matcher.match_video(
            metadata, order_papers, auto_accept_threshold=self.threshold
        )

        # Handle result
        if not result.is_ambiguous and result.matched_paper_id:
            # Auto-accept high confidence match
            if not self.dry_run:
                # Update order paper to reference this video
                matched_paper = await db.execute(
                    select(OrderPaper).where(OrderPaper.id == result.matched_paper_id)
                )
                paper = matched_paper.scalar_one_or_none()
                if paper:
                    paper.video_id = video.id
                    await db.commit()
                    logger.info(
                        f"✓ AUTO-MATCHED: '{video.title[:50]}...' -> "
                        f"Order Paper {result.matched_paper_id} "
                        f"(confidence: {result.confidence_score})"
                    )
            else:
                logger.info(
                    f"[DRY RUN] Would match: '{video.title[:50]}...' -> "
                    f"Order Paper {result.matched_paper_id} "
                    f"(confidence: {result.confidence_score})"
                )
        elif result.is_ambiguous:
            # Log ambiguous case
            logger.warning(f"⚠ AMBIGUOUS: '{video.title[:50]}...' - {result.ambiguity_reason}")

        return result

    async def _show_summary(self, db, ambiguous_cases: list):
        """Show processing summary."""
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total videos processed: {self.stats['total_videos']}")
        logger.info(f"Already matched: {self.stats['already_matched']}")
        logger.info(f"Auto-matched (≥{self.threshold} confidence): {self.stats['auto_matched']}")
        logger.info(f"Ambiguous (needs review): {self.stats['ambiguous']}")
        logger.info(f"No candidates found: {self.stats['no_candidates']}")
        logger.info("=" * 80)

        if ambiguous_cases:
            logger.info(f"\n{len(ambiguous_cases)} AMBIGUOUS CASES NEED REVIEW:")
            logger.info("Run with --review-only to see details\n")

            # Show first few ambiguous cases
            for i, case in enumerate(ambiguous_cases[:5], 1):
                logger.info(f"{i}. '{case.video.title[:60]}...'")
                logger.info(f"   Reason: {case.ambiguity_reason}")
                if case.all_candidates:
                    logger.info(f"   Candidates: {len(case.all_candidates)}")
                logger.info("")

            if len(ambiguous_cases) > 5:
                logger.info(f"... and {len(ambiguous_cases) - 5} more")

    async def run_interactive_review(self):
        """Run interactive review mode for ambiguous cases."""
        logger.info("\n" + "=" * 80)
        logger.info("INTERACTIVE REVIEW MODE")
        logger.info("=" * 80)
        logger.info("Commands: [y]es confirm, [n]o skip, [s]how candidates, [q]uit")
        logger.info("=" * 80 + "\n")

        async with AsyncSessionLocal() as db:
            # Load order papers
            order_papers_result = await db.execute(select(OrderPaper))
            order_papers = order_papers_result.scalars().all()

            # Load unmatched videos
            videos_result = await db.execute(
                select(Video)
                .where(Video.order_paper_id.is_(None))
                .order_by(Video.session_date.desc().nulls_last())
            )
            videos = videos_result.scalars().all()

            reviewed = 0
            confirmed = 0

            for video in videos:
                # Extract and match
                metadata = TitlePatternMatcher.parse_video_title(video.title)
                metadata.youtube_id = video.youtube_id
                if video.chamber:
                    metadata.extracted_chamber = video.chamber
                if video.session_date:
                    metadata.extracted_session_date = video.session_date

                result = self.matcher.match_video(metadata, order_papers, self.threshold)

                # Skip if not ambiguous and no match
                if not result.is_ambiguous and not result.matched_paper_id:
                    continue

                # Show video details
                print(f"\n{'=' * 80}")
                print(f"VIDEO: {video.title}")
                print(f"ID: {video.youtube_id}")
                if video.session_date:
                    print(f"Date: {video.session_date}")
                if video.chamber:
                    print(f"Chamber: {video.chamber}")
                print(
                    f"\nExtracted: {metadata.extracted_session_date} | {metadata.extracted_chamber}"
                )

                if result.is_ambiguous:
                    print(f"\n⚠ AMBIGUOUS: {result.ambiguity_reason}")

                if result.all_candidates:
                    print(f"\nCANDIDATE ORDER PAPERS:")
                    for j, (score, paper) in enumerate(result.all_candidates[:3], 1):
                        paper_date = (
                            paper.session_date
                            if hasattr(paper, "session_date")
                            else paper.get("session_date")
                        )
                        paper_chamber = (
                            paper.chamber if hasattr(paper, "chamber") else paper.get("chamber")
                        )
                        paper_id = paper.id if hasattr(paper, "id") else paper.get("id")
                        print(
                            f"  {j}. [{score} pts] {paper_date} ({paper_chamber}) - ID: {paper_id}"
                        )

                # Get user input
                while True:
                    choice = input("\nConfirm match? [y/n/s/q]: ").lower().strip()

                    if choice == "q":
                        print(f"\nReviewed {reviewed} videos, confirmed {confirmed} matches")
                        return
                    elif choice == "y" and result.all_candidates:
                        # Confirm first candidate
                        best_paper = result.all_candidates[0][1]
                        paper_id = (
                            best_paper.id if hasattr(best_paper, "id") else best_paper.get("id")
                        )

                        if not self.dry_run:
                            video.order_paper_id = paper_id
                            await db.commit()
                            print(f"✓ CONFIRMED match to Order Paper {paper_id}")
                        else:
                            print(f"[DRY RUN] Would confirm match to Order Paper {paper_id}")
                        confirmed += 1
                        break
                    elif choice == "n":
                        print("Skipped")
                        break
                    elif choice == "s":
                        print(
                            f"\nCandidates shown above. Use 1-{len(result.all_candidates)} to select"
                        )
                        continue
                    elif choice.isdigit() and result.all_candidates:
                        idx = int(choice) - 1
                        if 0 <= idx < len(result.all_candidates):
                            selected_paper = result.all_candidates[idx][1]
                            paper_id = (
                                selected_paper.id
                                if hasattr(selected_paper, "id")
                                else selected_paper.get("id")
                            )

                            if not self.dry_run:
                                video.order_paper_id = paper_id
                                await db.commit()
                                print(f"✓ CONFIRMED match to Order Paper {paper_id}")
                            else:
                                print(f"[DRY RUN] Would confirm match to Order Paper {paper_id}")
                            confirmed += 1
                            break
                    else:
                        print("Invalid choice. Use: y (yes), n (no), s (show), q (quit), or number")

                reviewed += 1

            print(f"\n{'=' * 80}")
            print(f"Review complete! Reviewed {reviewed} videos, confirmed {confirmed} matches")


async def main():
    parser = argparse.ArgumentParser(description="Match YouTube videos to order papers")
    parser.add_argument(
        "--threshold",
        type=int,
        default=90,
        help="Confidence threshold for auto-accept (default: 90)",
    )
    parser.add_argument(
        "--review-only", action="store_true", help="Only show ambiguous matches for review"
    )
    parser.add_argument("--interactive", action="store_true", help="Run interactive review mode")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be matched without making changes"
    )

    args = parser.parse_args()

    cli = VideoPaperMatchingCLI(threshold=args.threshold, dry_run=args.dry_run)

    if args.interactive:
        await cli.run_interactive_review()
    else:
        await cli.run(review_only=args.review_only)


if __name__ == "__main__":
    asyncio.run(main())
