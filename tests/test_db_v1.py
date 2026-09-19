"""Схема V1: гарантії, які тримає БД, а не код (крок 4 плану, тести (а)–(г)).

Усі запити — під роллю zoshyt_app, як у api і bot. Дані вигадані (ADR-0009).
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from zoshyt.db.models import Event, School, SchoolMember, Teacher


def _event(school_id: uuid.UUID, seq: int) -> Event:
    return Event(
        school_id=school_id,
        seq=seq,
        event_type="TestHappened",
        event_version=1,
        payload={"note": "вигадані дані"},
        occurred_at=datetime.now(UTC),
    )


async def test_insert_event_as_app(session: AsyncSession) -> None:
    """(а) INSERT у events під zoshyt_app працює (і sequence для id доступний)."""
    school = School(id=uuid.uuid4(), name="Тестова школа")
    session.add(school)
    await session.flush()
    event = _event(school.id, seq=1)
    session.add(event)
    await session.commit()

    assert event.id is not None
    assert await session.scalar(select(func.count()).select_from(Event)) == 1
    # server_default спрацьовує в БД, тому значення читаємо звідти.
    assert await session.scalar(select(School.tz).where(School.id == school.id)) == "Europe/Kyiv"


async def test_update_and_delete_events_denied(app_engine: AsyncEngine) -> None:
    """(б) UPDATE і DELETE по events під zoshyt_app → permission denied."""
    school_id = uuid.uuid4()
    async with AsyncSession(app_engine) as s:
        s.add(_event(school_id, seq=1))
        await s.commit()

    # Окрема сесія на кожну спробу: помилка обриває транзакцію.
    async with AsyncSession(app_engine) as s:
        with pytest.raises(ProgrammingError, match="permission denied for table events"):
            await s.execute(update(Event).values(event_type="Tampered"))

    async with AsyncSession(app_engine) as s:
        with pytest.raises(ProgrammingError, match="permission denied for table events"):
            await s.execute(delete(Event))

    async with AsyncSession(app_engine) as s:
        assert await s.scalar(select(Event.event_type)) == "TestHappened"


async def test_duplicate_seq_rejected(session: AsyncSession) -> None:
    """(в) Дубль (school_id, seq) → IntegrityError; той самий seq в іншій школі — ок."""
    school_id = uuid.uuid4()
    session.add_all([_event(school_id, seq=1), _event(uuid.uuid4(), seq=1)])
    await session.commit()

    session.add(_event(school_id, seq=1))
    with pytest.raises(IntegrityError, match="events_school_id_seq_key"):
        await session.commit()


async def test_second_owner_rejected(session: AsyncSession) -> None:
    """(г) Другий owner однієї школи → one_owner_per_school; owner + teacher — ок."""
    school = School(id=uuid.uuid4(), name="Тестова школа")
    teachers = [Teacher(id=uuid.uuid4(), display_name=f"Викладач {i}") for i in range(3)]
    session.add_all([school, *teachers])
    await session.flush()
    session.add_all(
        [
            SchoolMember(school_id=school.id, teacher_id=teachers[0].id, role="owner"),
            SchoolMember(school_id=school.id, teacher_id=teachers[1].id, role="teacher"),
        ]
    )
    await session.commit()

    session.add(SchoolMember(school_id=school.id, teacher_id=teachers[2].id, role="owner"))
    with pytest.raises(IntegrityError, match="one_owner_per_school"):
        await session.commit()
