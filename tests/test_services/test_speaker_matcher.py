"""Video transcription tests"""

from services.speaker_matcher import SpeakerMatcher


class TestSpeakerMatcher:
    """Test speaker matching logic."""

    def test_normalize_name_removes_titles(self):
        """Test that titles are removed from names."""
        matcher = SpeakerMatcher()

        assert matcher.normalize_name("Hon. John Smith") == "john smith"
        assert matcher.normalize_name("Dr. Jane Doe") == "jane doe"
        assert matcher.normalize_name("Senator Bob Wilson") == "bob wilson"
        assert matcher.normalize_name("The Hon. Mary Johnson") == "mary johnson"

    def test_exact_match(self):
        """Test exact speaker matching."""
        matcher = SpeakerMatcher(threshold=85)

        known_speakers = [
            {"canonical_id": "speaker-1", "name": "Hon. John Smith"},
            {"canonical_id": "speaker-2", "name": "Dr. Jane Doe"},
        ]

        speaker_id, match_type = matcher.match_speaker("Hon. John Smith", known_speakers)
        assert speaker_id == "speaker-1"
        assert match_type == "exact"

    def test_case_insensitive_match(self):
        """Test case-insensitive matching."""
        matcher = SpeakerMatcher(threshold=85)

        known_speakers = [
            {"canonical_id": "speaker-1", "name": "Hon. John Smith"},
        ]

        speaker_id, match_type = matcher.match_speaker("hon. john smith", known_speakers)
        assert speaker_id == "speaker-1"
        assert match_type == "case_insensitive"

    def test_fuzzy_match(self):
        """Test fuzzy speaker matching."""
        matcher = SpeakerMatcher(threshold=70)

        known_speakers = [
            {"canonical_id": "speaker-1", "name": "Hon. John Smith"},
        ]

        speaker_id, match_type = matcher.match_speaker("Jon Smythe", known_speakers)
        assert speaker_id == "speaker-1"
        assert match_type == "fuzzy"

    def test_no_match(self):
        """Test when no match is found."""
        matcher = SpeakerMatcher(threshold=85)

        known_speakers = [
            {"canonical_id": "speaker-1", "name": "Hon. John Smith"},
        ]

        speaker_id, match_type = matcher.match_speaker("Unknown Person", known_speakers)
        assert speaker_id is None
        assert match_type is None

    def test_ambiguous_match(self):
        """Test ambiguous matching detection."""
        matcher = SpeakerMatcher(threshold=70)

        known_speakers = [
            {"canonical_id": "speaker-1", "name": "Hon. John Smith"},
            {"canonical_id": "speaker-2", "name": "Hon. John Smythe"},
        ]

        speaker_id, match_type = matcher.match_speaker("John Smtih", known_speakers)
        assert speaker_id is None
        assert match_type == "ambiguous"
