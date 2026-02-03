#!/usr/bin/env python3
"""Download YouTube videos for parliamentary sessions"""

import argparse
import json
import logging
import re
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp not installed. Install with: pip install yt-dlp")
    exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class YouTubeDownloader:
    """Downloads YouTube videos with metadata"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_video(
        self,
        url: str,
        quality: str = "best",
        extract_audio: bool = False,
        timeout: int = 300,
    ) -> dict:
        """
        Download a YouTube video.

        Args:
            url: YouTube URL
            quality: Video quality (best/worst/bestaudio/worstaudio)
            extract_audio: If True, extract audio only
            timeout: Download timeout in seconds

        Returns:
            Dictionary with video metadata and file paths
        """
        ydl_opts = {
            "format": "bestaudio/best" if extract_audio else f"{quality}[ext=mp4]/best",
            "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
            "quiet": False,
            "no_warnings": False,
            "extract_flat": False,
            "writesubtitles": False,
            "writeinfojson": True,
        }

        if extract_audio:
            ydl_opts.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                    "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
                }
            )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Downloading: {url}")

                info = ydl.extract_info(
                    url,
                    download=True,
                )

                video_id = info.get("id")
                title = info.get("title")
                duration = info.get("duration")

                file_path = None
                if "requested_downloads" in info:
                    file_path = info["requested_downloads"][0].get("filepath")

                json_path = self.output_dir / f"{video_id}.info.json"

                logger.info(f"Downloaded: {title} ({video_id})")

                return {
                    "youtube_id": video_id,
                    "youtube_url": url,
                    "title": title,
                    "duration_seconds": duration,
                    "file_path": str(file_path) if file_path else None,
                    "json_path": str(json_path),
                    "upload_date": info.get("upload_date"),
                    "description": info.get("description"),
                    "channel": info.get("channel"),
                }

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Download error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def extract_youtube_id(self, url: str) -> str | None:
        """Extract YouTube ID from URL"""
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def download_from_list(
        self,
        urls_file: Path,
        extract_audio: bool = False,
    ) -> list[dict]:
        """
        Download videos from a list of URLs (one per line).

        Args:
            urls_file: Path to file with URLs
            extract_audio: If True, extract audio only

        Returns:
            List of video metadata dictionaries
        """
        if not urls_file.exists():
            logger.error(f"URLs file not found: {urls_file}")
            return []

        with open(urls_file) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        logger.info(f"Found {len(urls)} URLs to download")

        results = []
        for i, url in enumerate(urls, 1):
            logger.info(f"Processing {i}/{len(urls)}")
            try:
                result = self.download_video(url, extract_audio=extract_audio)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")
                continue

        return results


def main():
    parser = argparse.ArgumentParser(description="Download YouTube videos")
    parser.add_argument("url", nargs="?", help="YouTube URL to download")
    parser.add_argument(
        "--list",
        type=Path,
        help="File with list of YouTube URLs (one per line)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/videos"),
        help="Output directory (default: data/videos)",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Extract audio only (no video)",
    )

    args = parser.parse_args()

    downloader = YouTubeDownloader(args.output)

    if args.list:
        downloader.download_from_list(args.list, extract_audio=args.audio_only)
    elif args.url:
        result = downloader.download_video(args.url, extract_audio=args.audio_only)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
