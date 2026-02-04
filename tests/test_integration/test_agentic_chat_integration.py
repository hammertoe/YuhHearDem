import os
from datetime import datetime
from pathlib import Path

import pytest

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

from models.video import Video
from services.gemini import GeminiClient
from services.parliamentary_agent import ParliamentaryAgent
from storage.knowledge_graph_store import KnowledgeGraphStore


@pytest.mark.integration
@pytest.mark.expensive
@pytest.mark.anyio
async def test_agent_returns_useful_last_session_answer(db_session):
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")

    transcript = {
        "session_title": "House of Assembly",
        "date": "2026-02-03",
        "agenda_items": [
            {
                "topic_title": "Water Management Reform",
                "speech_blocks": [
                    {
                        "speaker_name": "Hon. Jane Doe",
                        "sentences": [
                            {
                                "start_time": "0m12s0ms",
                                "text": "Project Pelican Delta will modernize our water infrastructure.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    video = Video(
        youtube_id="test123",
        youtube_url="https://youtube.com/watch?v=test123",
        title="House of Assembly - 3rd February 2026",
        chamber="house",
        session_date=datetime(2026, 2, 3, 10, 0, 0),
        sitting_number="150",
        duration_seconds=3600,
        transcript=transcript,
    )

    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)

    agent = ParliamentaryAgent(
        gemini_client=GeminiClient(),
        kg_store=KnowledgeGraphStore(),
    )

    result = await agent.query(
        db=db_session,
        user_query="what was discussed in the last session?",
        max_iterations=3,
    )

    assert result["success"] is True
    answer = result.get("answer", "").lower()
    assert "water management" in answer
    assert "project pelican delta" in answer
