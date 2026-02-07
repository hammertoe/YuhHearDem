#!/usr/bin/env python3
"""Ingest order paper PDFs into database"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from core.database import get_session_maker
from models.order_paper import OrderPaper
from parsers.order_paper_parser import OrderPaperParser
from services.gemini import GeminiClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def ingest_order_paper(pdf_path: Path, chamber: str = "house") -> OrderPaper:
    """
    Parse an order paper PDF and save it to the database.

    Args:
        pdf_path: Path to the PDF file
        chamber: Chamber type (house or senate)

    Returns:
        Saved OrderPaper object
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Initialize Gemini client
    settings = get_settings()
    gemini_client = GeminiClient(
        api_key=settings.google_api_key,
        model=settings.gemini_model,
        temperature=0.0,
    )

    # Parse the PDF
    logger.info(f"Parsing order paper: {pdf_path}")
    parser = OrderPaperParser(gemini_client)
    parsed_paper = parser.parse(pdf_path)

    # Generate order_paper_id
    date_str = parsed_paper.session_date.strftime("%Y_%m_%d")
    chamber_code = "h" if chamber == "house" else "s"
    order_paper_id = f"op_{chamber_code}_{date_str}"

    # Save to database
    import asyncio
    from sqlalchemy import select

    async def save_paper():
        session_maker = get_session_maker()
        async with session_maker() as session:
            async with session.begin():
                # Check if already exists
                result = await session.execute(
                    select(OrderPaper).where(OrderPaper.order_paper_id == order_paper_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    logger.info(f"Order paper already exists: {order_paper_id}")
                    return existing

                # Create new order paper
                order_paper = OrderPaper(
                    order_paper_id=order_paper_id,
                    session_title=parsed_paper.session_title,
                    session_date=parsed_paper.session_date,
                    sitting_number=parsed_paper.sitting_number,
                    chamber=chamber,
                    source_url=str(pdf_path),
                    source_type="pdf",
                    speakers=[
                        {"name": s.name, "title": s.title, "role": s.role}
                        for s in parsed_paper.speakers
                    ],
                    agenda_items=[
                        {
                            "topic_title": item.topic_title,
                            "primary_speaker": item.primary_speaker,
                            "description": item.description,
                        }
                        for item in parsed_paper.agenda_items
                    ],
                )

                session.add(order_paper)
                await session.commit()
                logger.info(f"Saved order paper: {order_paper_id}")
                logger.info(f"  - {len(parsed_paper.speakers)} speakers")
                logger.info(f"  - {len(parsed_paper.agenda_items)} agenda items")
                return order_paper

    return asyncio.run(save_paper())


def main():
    parser = argparse.ArgumentParser(description="Ingest order paper PDFs")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--chamber",
        choices=["house", "senate"],
        default="house",
        help="Chamber type (default: house)",
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    try:
        order_paper = ingest_order_paper(pdf_path, args.chamber)
        print(f"\n✓ Successfully ingested order paper: {order_paper.order_paper_id}")
        print(f"  Session: {order_paper.session_title}")
        print(f"  Date: {order_paper.session_date}")
        print(f"  Speakers: {len(order_paper.speakers)}")
        print(f"  Agenda Items: {len(order_paper.agenda_items)}")
    except Exception as e:
        logger.error(f"Failed to ingest order paper: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
