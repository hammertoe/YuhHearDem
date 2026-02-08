"""Speaker service for canonical speaker management and deduplication."""

import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

from core.config import get_settings
from models.speaker import Speaker
from parsers.models import OrderPaperSpeaker

settings = get_settings()


class SpeakerService:
    """Service for managing canonical speakers with deduplication."""

    def __init__(self, session: AsyncSession, threshold: int | None = None) -> None:
        """
        Initialize speaker service.

        Args:
            session: Database session
            threshold: Fuzzy match threshold 0-100 (default: from config)
        """
        self.session = session
        self.threshold = threshold if threshold is not None else settings.fuzzy_match_threshold
        self._all_speakers: list[Speaker] | None = None

    async def get_or_create_speaker(
        self,
        name: str,
        title: str | None = None,
        role: str | None = None,
        party: str | None = None,
        chamber: str | None = None,
        session_id: str | None = None,
    ) -> Speaker:
        """
        Get existing speaker or create new one with deduplication.

        Uses three-stage matching:
        1. Exact match on normalized name
        2. Fuzzy name matching with role disambiguation
        3. Surname + role matching for edge cases

        Args:
            name: Speaker name
            title: Title (e.g., "Hon.", "Dr.")
            role: Role/position (e.g., "Minister of Finance")
            party: Political party
            chamber: Chamber ("senate" or "house")
            session_id: Current session ID to track appearances

        Returns:
            Existing or new Speaker with canonical ID
        """
        # Try to find matching speaker
        existing = await self._find_matching_speaker(name, role)

        if existing:
            # Update with any new info and track session
            await self._update_speaker(existing, title, role, party, chamber, session_id)
            return existing

        # Create new speaker
        return await self._create_speaker(name, title, role, party, chamber, session_id)

    async def process_order_paper_speakers(
        self,
        speakers: list[OrderPaperSpeaker],
        chamber: str,
        session_id: str,
    ) -> list[Speaker]:
        """
        Process all speakers from an order paper.

        Args:
            speakers: List of speakers from order paper
            chamber: Chamber ("senate" or "house")
            session_id: Current session ID

        Returns:
            List of canonical Speaker objects
        """
        canonical_speakers = []

        for speaker in speakers:
            canonical = await self.get_or_create_speaker(
                name=speaker.name,
                title=speaker.title,
                role=speaker.role,
                chamber=chamber,
                session_id=session_id,
            )
            canonical_speakers.append(canonical)

        return canonical_speakers

    async def _find_matching_speaker(
        self,
        name: str,
        role: str | None = None,
    ) -> Optional[Speaker]:
        """
        Find matching speaker using multi-stage matching.

        Stage 1: Exact match on normalized name
        Stage 2: Fuzzy match with role disambiguation
        Stage 3: Surname + role matching
        """
        all_speakers = await self._get_all_speakers()
        normalized_name = self._normalize_name(name)

        # Stage 1: Exact normalized match
        for speaker in all_speakers:
            if self._normalize_name(speaker.name) == normalized_name:
                return speaker

        # Stage 2: Fuzzy matching with role disambiguation
        best_match: Speaker | None = None
        best_score = 0
        second_best_score = 0

        for speaker in all_speakers:
            speaker_normalized = self._normalize_name(speaker.name)
            score = fuzz.ratio(normalized_name, speaker_normalized)

            # Check role disambiguation if both have roles
            if role and speaker.role:
                role_similarity = fuzz.ratio(role.lower(), speaker.role.lower())
                # If roles are very different, probably different people
                if role_similarity < 50:
                    continue

            if score > best_score:
                second_best_score = best_score
                best_score = score
                best_match = speaker
            elif score > second_best_score:
                second_best_score = score

        # Check if best match is good enough and unambiguous
        if best_match and best_score >= self.threshold:
            # Avoid ambiguous matches (top 2 within 5 points)
            if second_best_score > 0 and (best_score - second_best_score) < 5:
                # Ambiguous - use role for final disambiguation
                if role and best_match.role:
                    role_sim_best = fuzz.ratio(role.lower(), best_match.role.lower())
                    # Could get second best here for comparison
                    return best_match if role_sim_best >= 70 else None
                return None  # Too ambiguous without role
            return best_match

        # Stage 3: Surname + role matching
        if role:
            for speaker in all_speakers:
                if self._surname_matches(name, speaker.name):
                    if speaker.role and fuzz.ratio(role.lower(), speaker.role.lower()) >= 70:
                        return speaker

        return None

    async def _create_speaker(
        self,
        name: str,
        title: str | None = None,
        role: str | None = None,
        party: str | None = None,
        chamber: str | None = None,
        session_id: str | None = None,
    ) -> Speaker:
        """Create new canonical speaker."""
        canonical_id = self._generate_canonical_id(name)

        session_ids = [session_id] if session_id else []

        speaker = Speaker(
            canonical_id=canonical_id,
            name=name,
            title=title,
            role=role,
            party=party,
            chamber=chamber,
            session_ids=session_ids,
            aliases=[],
        )

        self.session.add(speaker)
        await self.session.flush()
        return speaker

    async def _update_speaker(
        self,
        speaker: Speaker,
        title: str | None = None,
        role: str | None = None,
        party: str | None = None,
        chamber: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Update speaker with new information."""
        # Track session appearance
        if session_id and session_id not in speaker.session_ids:
            speaker.session_ids.append(session_id)

        # Update fields if new info is more complete
        if title and not speaker.title:
            speaker.title = title
        if role and not speaker.role:
            speaker.role = role
        if party and not speaker.party:
            speaker.party = party
        if chamber and not speaker.chamber:
            speaker.chamber = chamber

        speaker.updated_at = datetime.now()

    def _generate_canonical_id(self, name: str) -> str:
        """Generate unique canonical ID from name."""
        normalized = self._normalize_name(name)
        slug = normalized.replace(" ", "-")
        unique_suffix = str(uuid.uuid4())[:8]
        return f"{slug}-{unique_suffix}"

    def _normalize_name(self, name: str) -> str:
        """
        Normalize speaker name for comparison.

        Removes titles, punctuation, and converts to lowercase.
        """
        titles = [
            "hon.",
            "honourable",
            "the honourable",
            "the hon.",
            "dr.",
            "dr",
            "mr.",
            "mr",
            "mrs.",
            "mrs",
            "ms.",
            "ms",
            "miss",
            "sir",
            "dame",
            "prof.",
            "professor",
            "senator",
            "sen.",
            "mp",
            "k.c.",
            "kc",
            "rev.",
            "rev",
        ]

        normalized = name.lower().strip()

        # Remove titles
        for title in titles:
            if normalized.startswith(title + " "):
                normalized = normalized[len(title) :].strip()
            if normalized.startswith(title):
                normalized = normalized[len(title) :].strip()

        # Remove extra whitespace and punctuation
        normalized = re.sub(r"[^\w\s-]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _surname_matches(self, name1: str, name2: str) -> bool:
        """Check if two names have the same surname."""
        surname1 = name1.split()[-1].lower() if name1 else ""
        surname2 = name2.split()[-1].lower() if name2 else ""
        return surname1 == surname2

    async def _get_all_speakers(self) -> list[Speaker]:
        """Get all speakers from database (cached)."""
        if self._all_speakers is None:
            result = await self.session.execute(select(Speaker))
            self._all_speakers = list(result.scalars().all())
        return self._all_speakers

    async def refresh_cache(self) -> None:
        """Refresh speaker cache (call after bulk operations)."""
        self._all_speakers = None
