#!/usr/bin/env python3
"""Simple example: Download a YouTube video and extract info"""

import argparse
import json
import logging
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp not installed. Install with: pip install yt-dlp")
    exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Download YouTube video")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--output", type=Path, default=Path("data/videos"), help="Output directory")

    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "best",
        "outtmpl": str(args.output / "%(title)s.%(ext)s"),
        "writeinfojson": True,
        "quiet": False,
    }

    logger.info(f"Downloading: {args.url}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(args.url, download=True)

        metadata = {
            "youtube_id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "upload_date": info.get("upload_date"),
            "url": args.url,
        }

        logger.info("Download complete!")
        print("\nVideo Info:")
        print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
