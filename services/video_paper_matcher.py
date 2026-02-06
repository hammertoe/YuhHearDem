"""Video to Order Paper matching service.

Automatically associates YouTube videos with order papers based on:
- Session date (extracted from video title)
- Chamber (House vs Senate)
- Sitting number (when available)

Only flags ambiguous cases (multiple papers on same date, missing data) for manual review.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Extracted metadata from a YouTube video."""

    youtube_id: str
    title: str
    description: str
    upload_date: Optional[date] = None
    extracted_session_date: Optional[date] = None
    extracted_chamber: Optional[str] = None
    extracted_sitting: Optional[str] = None
    duration_seconds: Optional[int] = None


@dataclass
class MatchResult:
    """Result of matching a video to order papers."""

    video: VideoMetadata
    matched_paper_id: Optional[str] = None
    confidence_score: int = 0
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    all_candidates: list[tuple[int, object]] = field(default_factory=list)


class TitlePatternMatcher:
    """Extract session metadata from video titles using multiple patterns."""

    # Patterns for extracting date from titles (most common first)
    DATE_PATTERNS = [
        # "House of Assembly - 15th January 2024"
        # "Senate - 20th December 2025"
        r"(?:House of Assembly|Senate)\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})",
        # "126th Sitting - 13th January 2026"
        r"(\d+)(?:st|nd|rd|th)\s+Sitting\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})",
        # "House of Assembly - Tuesday, 13th January, 2026"
        r"(?:House of Assembly|Senate)\s*[-–]\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})",
        # "15 January 2024" or "15th January 2024"
        r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})",
    ]

    # Month name mappings
    MONTH_MAP = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    @classmethod
    def extract_session_date(cls, title: str) -> Optional[date]:
        """Extract session date from video title."""
        for pattern in cls.DATE_PATTERNS:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    # Pattern with sitting number: (sitting, day, month, year)
                    if len(groups) == 4 and groups[0].isdigit() and int(groups[0]) > 31:
                        day, month_str, year = groups[1], groups[2], groups[3]
                    else:
                        day, month_str, year = groups[0], groups[1], groups[2]

                    month = cls.MONTH_MAP.get(month_str.lower())
                    if month:
                        return date(int(year), month, int(day))
                except (ValueError, IndexError):
                    continue

        return None

    @classmethod
    def extract_chamber(cls, title: str) -> Optional[str]:
        """Extract chamber (house/senate) from title."""
        title_lower = title.lower()

        if "house of assembly" in title_lower or "house" in title_lower:
            return "house"
        elif "senate" in title_lower:
            return "senate"

        # Default to house if ambiguous but has sitting number pattern
        # (most common case)
        return None

    @classmethod
    def extract_sitting_number(cls, title: str) -> Optional[str]:
        """Extract sitting number from title (e.g., '126th')."""
        # Look for patterns like "126th Sitting" or "126th sitting"
        match = re.search(r"(\d+)(?:st|nd|rd|th)\s+Sitting", title, re.IGNORECASE)
        if match:
            return match.group(1)

        # Look for just a number before "sitting"
        match = re.search(r"(\d+)\s+Sitting", title, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    @classmethod
    def parse_video_title(cls, title: str) -> VideoMetadata:
        """Parse all metadata from a video title."""
        return VideoMetadata(
            youtube_id="",  # Will be filled in later
            title=title,
            description="",
            extracted_session_date=cls.extract_session_date(title),
            extracted_chamber=cls.extract_chamber(title),
            extracted_sitting=cls.extract_sitting_number(title),
        )


class VideoPaperMatcher:
    """Matches YouTube videos to order papers."""

    def __init__(self, db_session=None) -> None:
        """Initialize matcher with optional DB session."""
        self.db_session = db_session
        self.pattern_matcher = TitlePatternMatcher()

    def match_video(
        self, video: VideoMetadata, order_papers: list, auto_accept_threshold: int = 90
    ) -> MatchResult:
        """
        Match a video to the best order paper.

        Args:
            video: Video metadata with extracted fields
            order_papers: List of available order papers
            auto_accept_threshold: Minimum score to auto-accept (default 90)

        Returns:
            MatchResult with match details and ambiguity status
        """
        if not video.extracted_session_date:
            return MatchResult(
                video=video,
                is_ambiguous=True,
                ambiguity_reason="Could not extract session date from video title",
                confidence_score=0,
            )

        if not video.extracted_chamber:
            # Try to infer from order papers on that date
            chamber = self._infer_chamber(video, order_papers)
            if chamber:
                video.extracted_chamber = chamber
            else:
                return MatchResult(
                    video=video,
                    is_ambiguous=True,
                    ambiguity_reason="Could not determine chamber (House/Senate)",
                    confidence_score=0,
                )

        # Find candidates by date (±1 day) and chamber
        candidates = self._find_candidates(video, order_papers)

        if not candidates:
            return MatchResult(
                video=video,
                is_ambiguous=True,
                ambiguity_reason=f"No order papers found for {video.extracted_session_date} ({video.extracted_chamber})",
                confidence_score=0,
            )

        # Score each candidate
        scored_candidates = []
        for paper in candidates:
            score = self._calculate_match_score(video, paper)
            scored_candidates.append((score, paper))

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        best_score, best_paper = scored_candidates[0]

        # Check for ambiguity
        if len(scored_candidates) > 1:
            second_score, second_paper = scored_candidates[1]
            # Ambiguous if second best is close (within 20 points)
            if second_score >= best_score - 20 and second_score >= 50:
                return MatchResult(
                    video=video,
                    is_ambiguous=True,
                    ambiguity_reason=f"Multiple good matches (scores: {best_score} vs {second_score})",
                    confidence_score=best_score,
                    all_candidates=[(s, p) for s, p in scored_candidates[:3]],
                )

        # Check if best match meets threshold
        if best_score >= auto_accept_threshold:
            return MatchResult(
                video=video,
                matched_paper_id=best_paper.id
                if hasattr(best_paper, "id")
                else str(best_paper.get("id")),
                confidence_score=best_score,
                is_ambiguous=False,
                all_candidates=[(best_score, best_paper)],
            )
        elif best_score >= 70:
            # Good but not great - flag for review
            return MatchResult(
                video=video,
                matched_paper_id=best_paper.id
                if hasattr(best_paper, "id")
                else str(best_paper.get("id")),
                confidence_score=best_score,
                is_ambiguous=True,
                ambiguity_reason=f"Confidence score {best_score} below threshold {auto_accept_threshold}",
                all_candidates=[(best_score, best_paper)],
            )
        else:
            # Poor match
            return MatchResult(
                video=video,
                is_ambiguous=True,
                ambiguity_reason=f"Best match score too low: {best_score}",
                confidence_score=best_score,
                all_candidates=[(best_score, best_paper)],
            )

    def _find_candidates(self, video: VideoMetadata, order_papers: list) -> list:
        """Find order paper candidates by date and chamber."""
        if not video.extracted_session_date:
            return []

        candidates = []

        # Allow ±1 day for timezone/scheduling flexibility
        date_min = video.extracted_session_date - timedelta(days=1)
        date_max = video.extracted_session_date + timedelta(days=1)

        for paper in order_papers:
            # Get paper date
            paper_date = self._get_paper_value(paper, "session_date")

            if not paper_date:
                continue

            # Convert to date if datetime
            if isinstance(paper_date, datetime):
                paper_date = paper_date.date()

            # Check date range
            if date_min <= paper_date <= date_max:
                # Check chamber
                paper_chamber = self._get_paper_value(paper, "chamber")

                if (
                    paper_chamber
                    and video.extracted_chamber
                    and paper_chamber.lower() == video.extracted_chamber.lower()
                ):
                    candidates.append(paper)

        return candidates

    def _calculate_match_score(self, video: VideoMetadata, paper) -> int:
        """Calculate confidence score for a match."""
        if not video.extracted_session_date:
            return 0

        score = 0

        # Date match (exact = 50, ±1 day = 40)
        paper_date = self._get_paper_value(paper, "session_date")

        if isinstance(paper_date, datetime):
            paper_date = paper_date.date()

        if paper_date == video.extracted_session_date:
            score += 50
        elif paper_date and abs((paper_date - video.extracted_session_date).days) <= 1:
            score += 40

        # Chamber match = 30
        paper_chamber = self._get_paper_value(paper, "chamber")

        if (
            paper_chamber
            and video.extracted_chamber
            and paper_chamber.lower() == video.extracted_chamber.lower()
        ):
            score += 30

        # Sitting number match = 20
        if video.extracted_sitting:
            paper_sitting = self._get_paper_value(paper, "sitting_number")

            if paper_sitting:
                # Normalize: remove non-digits and compare
                paper_sitting_clean = re.sub(r"\D", "", str(paper_sitting))
                video_sitting_clean = re.sub(r"\D", "", str(video.extracted_sitting))
                if paper_sitting_clean == video_sitting_clean:
                    score += 20

        return score

    def _infer_chamber(self, video: VideoMetadata, order_papers: list) -> Optional[str]:
        """Infer chamber when not explicitly stated in title."""
        if not video.extracted_session_date:
            return None

        # Count papers by chamber on this date
        date_min = video.extracted_session_date - timedelta(days=1)
        date_max = video.extracted_session_date + timedelta(days=1)

        house_count = 0
        senate_count = 0

        for paper in order_papers:
            paper_date = self._get_paper_value(paper, "session_date")

            if isinstance(paper_date, datetime):
                paper_date = paper_date.date()

            if paper_date and date_min <= paper_date <= date_max:
                paper_chamber = self._get_paper_value(paper, "chamber")

                if paper_chamber:
                    if paper_chamber.lower() == "house":
                        house_count += 1
                    elif paper_chamber.lower() == "senate":
                        senate_count += 1

        # If only one chamber has papers on this date, use that
        if house_count > 0 and senate_count == 0:
            return "house"
        elif senate_count > 0 and house_count == 0:
            return "senate"

        return None

    def _get_paper_value(self, paper: object, key: str) -> Any:
        if isinstance(paper, dict):
            return paper.get(key)
        return getattr(paper, key, None)


def normalize_sitting_number(sitting: Optional[str]) -> Optional[str]:
    """Normalize sitting number by removing ordinals and non-digits."""
    if not sitting:
        return None
    return re.sub(r"\D", "", str(sitting))
