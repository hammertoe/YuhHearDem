"""Migration coverage for speaker schema."""

from pathlib import Path


def test_speaker_canonical_id_migration_exists():
    """Ensure migration adds speaker canonical_id."""
    contents = Path("migrations/versions/002_add_speaker_canonical_id.py").read_text()

    assert "canonical_id" in contents
