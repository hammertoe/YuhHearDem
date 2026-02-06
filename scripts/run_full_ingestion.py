#!/usr/bin/env python3
"""Full pipeline: scrape, parse, and ingest parliamentary data"""

import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from scripts.ingest_order_paper import OrderPaperIngestor
from scripts.scrape_session_papers import SessionPaperScraper
from services.gemini import GeminiClient

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
        self.papers_dir.mkdir(parents=True, exist_ok=True)

    async def run_full_pipeline(
        self,
        max_papers: int | None = None,
    ):
        """
        Run the complete ingestion pipeline.

        Args:
            max_papers: Maximum number of order papers to scrape
        """
        logger.info("=" * 60)
        logger.info("Starting Full Ingestion Pipeline")
        logger.info("=" * 60)

        from core.database import get_session_maker

        session_maker = get_session_maker()

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
        ingestor = OrderPaperIngestor(gemini_client=client)

        paper_results = []
        for paper in downloaded:
            result = await ingestor.ingest_pdf(
                db_session_maker=session_maker,
                pdf_path=Path(paper["pdf_path"]),
                chamber=self.chamber,
            )
            paper_results.append(result)

        success = sum(1 for r in paper_results if r["status"] == "success")
        logger.info(f"Ingested {success}/{len(downloaded)} order papers")

        logger.info("\n" + "=" * 60)
        logger.info("Pipeline Complete!")
        logger.info("=" * 60)
        logger.info("\nTo process videos, use the daily pipeline:")
        logger.info("  python scripts/daily_pipeline.py")

        return {
            "papers_scraped": len(papers),
            "papers_downloaded": len(downloaded),
            "papers_ingested": success,
        }


async def main() -> None:
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
