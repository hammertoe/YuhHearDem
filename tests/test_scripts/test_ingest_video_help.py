"""Script entrypoint tests."""

import subprocess
import sys


def test_ingest_video_help_runs():
    """Ensure ingest_video CLI can render help text."""
    result = subprocess.run(
        [sys.executable, "scripts/ingest_video.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--fps" in result.stdout
    assert "--start-time" in result.stdout
    assert "--end-time" in result.stdout
    assert "--no-thinking" in result.stdout
