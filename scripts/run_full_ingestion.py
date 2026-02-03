#!/usr/bin/env python3
"""Full pipeline: scrape, parse, and ingest parliamentary data"""

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from google import genai

from app.config import get_settings
from scripts.download_youtube_videos import YouTubeDownloader
from scripts.ingest_order_paper import OrderPaperIngestor
from scripts.ingest_video import VideoIngestor
from scripts.scrape_session_papers import SessionPaperScraper
from services.gemini import GeminiClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FullIngestionPipeline:
    """Orchestrates full data ingestion pipeline"""

    def __init__(
        self,
        output_dir: Path,
        chamber: str = "house",
    ):
        self.output_dir = output_dir
        self.chamber = chamber

        self.papers_dir = output_dir / "papers"
        self.videos_dir = output_dir / "videos"
        self.mapping_file = output_dir / "video_mapping.json"

        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)

    async def run_full_pipeline(
        self,
        max_papers: int = None,
        max_videos: int = None,
        download_videos: bool = False,
    ):
        """
        Run the complete ingestion pipeline.

        Args:
            max_papers: Maximum number of order papers to scrape
            max_videos: Maximum number of videos to download
            download_videos: If True, download YouTube videos
        """
        logger.info("=" * 60)
        logger.info("Starting Full Ingestion Pipeline")
        logger.info("=" * 60)

        settings = get_settings()
        genai.configure(api_key=settings.google_api_key)

        from app.dependencies import get_db_session

        async with get_db_session() as db:
            client = GeminiClient()

            # Step 1: Scrape session papers
            logger.info("\n[Step 1] Scraping session papers...")
            scraper = SessionPaperScraper()
            papers = scraper.scrape_session_papers(self.chamber, max_papers)

            logger.info(f"Found {len(papers)} session papers")

            # Step 2: Download PDFs
            logger.info("\n[Step 2] Downloading PDFs...")
            downloaded = scraper.download_all_papers(papers, self.papers_dir)
            logger.info(f"Downloaded {len(downloaded)} PDFs")

            # Step 3: Ingest order papers to database
            logger.info("\n[Step 3] Ingesting order papers...")
            ingestor = OrderPaperIngestor(db, client)

            paper_results = []
            for paper in downloaded:
                result = await ingestor.ingest_pdf(
                    pdf_path=Path(paper["pdf_path"]),
                    chamber=self.chamber,
                )
                paper_results.append(result)

            success = sum(1 for r in paper_results if r["status"] == "success")
            logger.info(f"Ingested {success}/{len(downloaded)} order papers")

            # Step 4: Download YouTube videos (optional)
            video_results = []
            video_mapping = {}

            if download_videos:
                logger.info("\n[Step 4] Downloading YouTube videos...")

                urls_file = self.videos_dir / "urls.txt"

                # If no URLs file, prompt user
                if not urls_file.exists():
                    logger.warning(
                        "No URLs file found at: data/videos/urls.txt\n"
                        "Create this file with one YouTube URL per line\n"
                        "Example:\n"
                        "https://www.youtube.com/watch?v=ABC123\n"
                        "https://www.youtube.com/watch?v=DEF456"
                    )
                    return

                downloader = YouTubeDownloader(self.videos_dir)
                videos_metadata = downloader.download_from_list(urls_file)

                logger.info(f"Downloaded {len(videos_metadata)} videos")

                # Create video mapping
                for video in videos_metadata:
                    video_mapping[video["youtube_id"]] = video

                # Save mapping to file
                with open(self.mapping_file, "w") as f:
                    json.dump(video_mapping, f, indent=2)

            else:
                logger.info("\n[Step 4] Skipping video download")
                logger.info("To process videos, run:")
                logger.info(
                    "  python scripts/ingest_video.py --mapping data/videos/video_mapping.json"
                )

            # Step 5: Ingest videos to database (if downloaded)
            if download_videos and video_mapping:
                logger.info("\n[Step 5] Ingesting videos to database...")

                video_ingestor = VideoIngestor(db, client)

                # Create mapping file for ingest_video.py
                ingest_mapping = []
                for paper in downloaded:
                    paper_name = Path(paper["pdf_path"]).stem

                    # Try to find matching video
                    matching_video = None
                    for yt_id, video_meta in video_mapping.items():
                        if paper_name.lower() in video_meta["title"].lower():
                            matching_video = video_meta
                            break

                    if matching_video:
                        ingest_mapping.append(
                            {
                                "youtube_url": f"https://www.youtube.com/watch?v={yt_id}",
                                "chamber": self.chamber,
                                "session_date": paper.get("session_date")
                                or datetime.utcnow().isoformat(),
                                "order_paper_pdf": paper["pdf_path"],
                            }
                        )

                # Save ingest mapping
                ingest_mapping_file = self.output_dir / "video_ingest_mapping.json"
                with open(ingest_mapping_file, "w") as f:
                    json.dump(ingest_mapping, f, indent=2)

                logger.info(f"Saved mapping to: {ingest_mapping_file}")
                logger.info(
                    "Run: python scripts/ingest_video.py --mapping data/video_ingest_mapping.json"
                )

            logger.info("\n" + "=" * 60)
            logger.info("Pipeline Complete!")
            logger.info("=" * 60)

            return {
                "papers_scraped": len(papers),
                "papers_downloaded": len(downloaded),
                "papers_ingested": success,
                "videos_downloaded": len(video_mapping) if download_videos else 0,
            }


async def main():
    parser = argparse.ArgumentParser(description="Full parliamentary data ingestion pipeline")
    parser.add_argument(
        "--chamber",
        choices=["house", "senate"],
        default="house",
        help="Chamber to process (default: house)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        help="Maximum number of order papers to scrape",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        help="Maximum number of videos to download",
    )
    parser.add_argument(
        "--download-videos",
        action="store_true",
        help="Download YouTube videos (requires data/videos/urls.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data"),
        help="Output directory (default: data/)",
    )

    args = parser.parse_args()

    pipeline = FullIngestionPipeline(args.output, args.chamber)

    try:
        results = await pipeline.run_full_pipeline(
            max_papers=args.max_papers,
            max_videos=args.max_videos,
            download_videos=args.download_videos,
        )

        print("\nPipeline Results:")
        for key, value in results.items():
            print(f"  {key}: {value}")

    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
