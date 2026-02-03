#!/usr/bin/env python3
"""Scrape session papers from Barbados Parliament website"""

import argparse
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: requests and beautifulsoup4 not installed.")
    print("Install with: pip install requests beautifulsoup4")
    exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SessionPaperScraper:
    """Scrapes order papers from parliament website"""

    def __init__(self, base_url: str = "https://www.barbadosparliament.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )

    def scrape_session_papers(
        self,
        chamber: str = "house",
        max_papers: Optional[int] = None,
    ) -> list[dict]:
        """
        Scrape session papers from parliament website.

        Args:
            chamber: 'house' or 'senate'
            max_papers: Maximum number of papers to scrape (None = all)

        Returns:
            List of session paper metadata
        """
        logger.info(f"Scraping {chamber} session papers...")

        papers = []

        # Actual URLs for Barbados Parliament website
        if chamber == "house":
            url = f"{self.base_url}/order_papers/search/type/1"
        else:
            url = f"{self.base_url}/order_papers/search/type/2"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find table rows with order papers
            table = soup.find("table", class_="table-hover")
            if not table:
                logger.warning("No table found on page")
                return []

            rows = table.find_all("tr")[1:]  # Skip header row

            for i, row in enumerate(rows, 1):
                if max_papers and i > max_papers:
                    break

                # Extract data from table cells
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                # First cell: PDF link and title
                title_cell = cells[0]
                pdf_link = title_cell.find("a", href=True)
                if not pdf_link:
                    continue

                pdf_url = pdf_link.get("href")
                title = pdf_link.get_text(strip=True) or f"Session Paper {i}"

                # Second cell: posted date
                date_text = cells[1].get_text(strip=True)
                session_date = self._parse_date(date_text)

                logger.info(f"Found: {title} - {pdf_url}")

                papers.append(
                    {
                        "chamber": chamber,
                        "title": title,
                        "pdf_url": pdf_url,
                        "session_date": session_date,
                    }
                )

        except requests.RequestException as e:
            logger.error(f"Failed to scrape session papers: {e}")

        return papers

    def download_paper(self, pdf_url: str, output_path: Path) -> bool:
        """
        Download a single session paper PDF.

        Args:
            pdf_url: URL to PDF
            output_path: Where to save the PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading: {output_path.name}")

            response = self.session.get(pdf_url, timeout=60, stream=True)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded: {output_path}")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to download {pdf_url}: {e}")
            return False

    def download_all_papers(
        self,
        papers: list[dict],
        output_dir: Path,
    ) -> list[dict]:
        """
        Download all session papers.

        Args:
            papers: List of paper metadata
            output_dir: Output directory

        Returns:
            List of successful downloads with file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []

        for paper in papers:
            pdf_url = paper["pdf_url"]
            filename = self._sanitize_filename(paper["title"])
            output_path = output_dir / f"{filename}.pdf"

            if output_path.exists():
                logger.info(f"Skipping existing: {output_path.name}")
                results.append({**paper, "pdf_path": str(output_path)})
                continue

            if self.download_paper(pdf_url, output_path):
                results.append({**paper, "pdf_path": str(output_path)})

        return results

    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse date from text (YYYY-MM-DD)"""
        date_text = date_text.strip()

        # Try common date formats
        formats = [
            "%Y-%m-%d",  # 2026-01-20
            "%d %B %Y",  # 20 January 2026
            "%B %d, %Y",  # January 20, 2026
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_text, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem"""
        import re

        invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
        return re.sub(invalid_chars, "_", filename)


def main():
    parser = argparse.ArgumentParser(description="Scrape Barbados Parliament session papers")
    parser.add_argument(
        "--chamber",
        choices=["house", "senate"],
        default="house",
        help="Chamber to scrape (default: house)",
    )
    parser.add_argument(
        "--max",
        type=int,
        help="Maximum number of papers to scrape",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/papers"),
        help="Output directory (default: data/papers)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download PDFs (not just list them)",
    )

    args = parser.parse_args()

    scraper = SessionPaperScraper()
    papers = scraper.scrape_session_papers(args.chamber, args.max)

    print(f"\nFound {len(papers)} session papers:")
    for paper in papers:
        print(f"  - {paper['title']}")

    if args.download:
        downloaded = scraper.download_all_papers(papers, args.output)
        print(f"\nDownloaded {len(downloaded)} papers to {args.output}")


if __name__ == "__main__":
    main()
