"""Test agenda_item model"""

from datetime import datetime

import pytest
from sqlalchemy import select

from core.database import Base, get_engine
from models.agenda_item import AgendaItem
from models.session import Session as SessionModel


@pytest.mark.asyncio
async def test_agenda_item_stable_id_generation(db_session):
    """Test that agenda_item_id follows the format: {session_id}_a{index}"""
    session = SessionModel(
        session_id="s_125_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House of Assembly Sitting",
        sitting_number="125",
        chamber="house",
    )
    db_session.add(session)
    await db_session.flush()

    agenda_item = AgendaItem(
        agenda_item_id="s_125_2026_01_06_a0",
        session_id="s_125_2026_01_06",
        agenda_index=0,
        title="Road Traffic (Amendment) Bill 2025",
        description="Bill to update road safety regulations",
        primary_speaker="John Bradshaw",
    )
    db_session.add(agenda_item)
    await db_session.commit()

    result = await db_session.execute(
        select(AgendaItem).where(AgendaItem.agenda_item_id == "s_125_2026_01_06_a0")
    )
    fetched = result.scalar_one()

    assert fetched is not None
    assert fetched.agenda_item_id == "s_125_2026_01_06_a0"
    assert fetched.session_id == "s_125_2026_01_06"
    assert fetched.agenda_index == 0
    assert fetched.title == "Road Traffic (Amendment) Bill 2025"


@pytest.mark.asyncio
async def test_agenda_item_optional_fields(db_session):
    """Test that description and primary_speaker can be null"""
    session = SessionModel(
        session_id="s_125_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House of Assembly Sitting",
        sitting_number="125",
        chamber="house",
    )
    db_session.add(session)
    await db_session.flush()

    agenda_item = AgendaItem(
        agenda_item_id="s_125_2026_01_06_a0",
        session_id="s_125_2026_01_06",
        agenda_index=0,
        title="Budget 2026",
    )
    db_session.add(agenda_item)
    await db_session.commit()

    result = await db_session.execute(
        select(AgendaItem).where(AgendaItem.agenda_item_id == "s_125_2026_01_06_a0")
    )
    fetched = result.scalar_one()

    assert fetched is not None
    assert fetched.description is None
    assert fetched.primary_speaker is None
