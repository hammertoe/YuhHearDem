"""Speaker matching with fuzzy deduplication"""

from typing import Optional, Tuple
from thefuzz import fuzz

from app.config import get_settings

settings = get_settings()


class SpeakerMatcher:
    """Matches speakers with fuzzy deduplication."""

    def __init__(self, threshold: int = None):
        """
        Initialize matcher.

        Args:
            threshold: Fuzzy match threshold 0-100 (default: from config)
        """
        self.threshold = threshold or settings.fuzzy_match_threshold

    def normalize_name(self, name: str) -> str:
        """
        Normalize speaker name for comparison.

        Removes titles, punctuation, and converts to lowercase.

        Args:
            name: Raw speaker name

        Returns:
            Normalized name
        """
        titles = [
            "hon.",
            "honourable",
            "dr.",
            "mr.",
            "mrs.",
            "ms.",
            "senator",
            "mp",
            "k.c.",
            "the honourable",
            "the hon.",
            "rev.",
            "sir.",
        ]

        normalized = name.lower().strip()

        for title in titles:
            if normalized.startswith(title):
                normalized = normalized[len(title) :].strip()

        normalized = normalized.strip(" ,.:-")
        return normalized

    def match_speaker(
        self,
        name: str,
        known_speakers: list[dict],
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Match a speaker name against known speakers.

        Args:
            name: Speaker name to match
            known_speakers: List of known speakers with 'canonical_id' and 'name' keys

        Returns:
            Tuple of (matched_canonical_id, match_type)
            match_type can be: 'exact', 'case_insensitive', 'fuzzy', None
        """
        if not known_speakers:
            return None, None

        normalized = self.normalize_name(name)

        # Exact match - highest priority (check raw strings)
        for speaker in known_speakers:
            if name == speaker["name"]:
                return speaker["canonical_id"], "exact"

        # Case-insensitive match - second priority (check raw strings)
        for speaker in known_speakers:
            if name.lower().strip() == speaker["name"].lower().strip():
                return speaker["canonical_id"], "case_insensitive"

        # Fuzzy match - last resort (compare normalized)
        best_match = None
        best_score = 0
        second_best_score = 0

        for speaker in known_speakers:
            score = fuzz.ratio(normalized, self.normalize_name(speaker["name"]))

            if score > best_score:
                second_best_score = best_score
                best_score = score
                best_match = speaker
            elif score > second_best_score:
                second_best_score = score

        # Check for ambiguity
        if best_match and best_score >= self.threshold:
            if second_best_score and (best_score - second_best_score) < 5:
                return None, "ambiguous"

            return best_match["canonical_id"], "fuzzy"

        return None, None
