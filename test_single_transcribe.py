#!/usr/bin/env python3
import asyncio
import json
import dataclasses
from datetime import datetime
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

from core.database import get_session_maker
from services.gemini import GeminiClient
from parsers.video_transcript import VideoTranscriptionParser
from parsers.models import OrderPaper as ParsedOrderPaper, OrderPaperSpeaker, AgendaItem


async def transcribe_one_video():
    gemini_client = GeminiClient(temperature=0.0)
    parser = VideoTranscriptionParser(
        gemini_client=gemini_client, chunk_size=600, fuzzy_threshold=85
    )

    async with get_session_maker()() as db:
        result = await db.execute(text('''
            SELECT v.id, v.youtube_id, v.title, v.youtube_url, v.order_paper_id,
                   op.session_title, op.session_date, op.sitting_number,
                   op.speakers, op.agenda_items
            FROM videos v
            JOIN order_papers op ON v.order_paper_id = op.id
            WHERE v.transcript IS NULL
            ORDER BY v.session_date DESC
            LIMIT 1
        '''))
        row = result.fetchone()
        
        if not row:
            print("No unmatched videos found")
            return
        
        video_id = row[0]
        youtube_id = row[1]
        title = row[2]
        youtube_url = row[3]
        
        print(f"Processing video: {title}")
        print(f"YouTube ID: {youtube_id}")
        
        order_paper = ParsedOrderPaper(
            session_title=row[5],
            session_date=row[6],
            sitting_number=row[7],
            speakers=[
                OrderPaperSpeaker(
                    name=s.get("name", ""),
                    title=s.get("title"),
                    role=s.get("role"),
                )
                for s in (row[8] or [])
            ],
            agenda_items=[
                AgendaItem(
                    topic_title=a.get("topic_title", ""),
                    primary_speaker=a.get("primary_speaker"),
                    description=a.get("description"),
                )
                for a in (row[9] or [])
            ],
        )
        
        print(f"Order paper has {len(order_paper.speakers)} speakers")
        print(f"Order paper has {len(order_paper.agenda_items)} agenda items")
        print("Starting transcription...")
        
        transcript, _ = parser.transcribe(
            video_url=youtube_url,
            order_paper=order_paper,
            speaker_id_mapping={},
            fps=0.25,
            start_time=0,
            end_time=None,
            auto_chunk=True,
        )
        
        print(f"✓ Transcription complete!")
        speech_blocks = sum(len(ai.speech_blocks) for ai in transcript.agenda_items)
        print(f"  Agenda items: {len(transcript.agenda_items)}")
        print(f"  Total speech blocks: {speech_blocks}")
        
        print("Saving to database...")
        transcript_dict = dataclasses.asdict(transcript)
        await db.execute(
            text("UPDATE videos SET transcript = :transcript, transcript_processed_at = :now WHERE id = :video_id"),
            {"transcript": json.dumps(transcript_dict), "now": datetime.now(), "video_id": video_id}
        )
        await db.commit()
        
        print("✓ Saved to database")


if __name__ == "__main__":
    asyncio.run(transcribe_one_video())
