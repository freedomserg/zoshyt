"""Схема V1: гарантії, які тримає БД, а не код (крок 4 плану і ADR-0015, тести (а)–(ж)).

Тести (а)–(д) — під роллю zoshyt_app, як у api і bot; (е)–(ж) — під
zoshyt_readonly, як людина під ssh-тунелем. Дані вигадані (ADR-0009).
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from zoshyt.db.models import Event, School, SchoolMember, Teacher

FOREIGN_KEY_VIOLATION = "23503"  # SQLSTATE


def _event(school_id: uuid.UUID, seq: int, actor_teacher_id: uuid.UUID | None = None) -> Event:
    return Event(
        school_id=school_id,
        seq=seq,
        event_type="TestHappened",
        event_version=1,
        payload={"note": "вигадані дані"},
        actor_teacher_id=actor_teacher_id,
        occurred_at=datetime.now(UTC),
    )


async def _school(session: AsyncSession, name: str = "Тестова школа") -> School:
    school = School(id=uuid.uuid4(), name=name)
    session.add(school)
    await session.flush()
    return school


async def test_a_insert_event_as_app(session: AsyncSession) -> None:
    """(а) INSERT у events під zoshyt_app працює: з актором і без (системна подія)."""
    school = await _school(session)
    teacher = Teacher(id=uuid.uuid4(), display_name="Викладач 1")
    session.add(teacher)
    await session.flush()
    with_actor = _event(school.id, seq=1, actor_teacher_id=teacher.id)
    system = _event(school.id, seq=2)
    session.add_all([with_actor, system])
    await session.commit()

    assert with_actor.id is not None  # sequence для bigserial доступний app-ролі
    assert await session.scalar(select(func.count()).select_from(Event)) == 2
    # server_default спрацьовує в БД, тому значення читаємо звідти.
    assert await session.scalar(select(School.tz).where(School.id == school.id)) == "Europe/Kyiv"


async def test_b_update_and_delete_events_denied(app_engine: AsyncEngine) -> None:
    """(б) UPDATE і DELETE по events під zoshyt_app → permission denied."""
    async with AsyncSession(app_engine) as s:
        school = await _school(s)
        s.add(_event(school.id, seq=1))
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


async def test_c_duplicate_seq_rejected(session: AsyncSession) -> None:
    """(в) Дубль (school_id, seq) для ІСНУЮЧОЇ школи → IntegrityError;
    той самий seq в іншій школі — ок."""
    school = await _school(session)
    other = await _school(session, name="Інша школа")
    session.add_all([_event(school.id, seq=1), _event(other.id, seq=1)])
    await session.commit()

    session.add(_event(school.id, seq=1))
    with pytest.raises(IntegrityError, match="events_school_id_seq_key"):
        await session.commit()


async def test_d_second_owner_rejected(session: AsyncSession) -> None:
    """(г) Другий owner однієї школи → one_owner_per_school; owner + teacher — ок."""
    school = await _school(session)
    teachers = [Teacher(id=uuid.uuid4(), display_name=f"Викладач {i}") for i in range(3)]
    session.add_all(teachers)
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


async def test_e_event_for_unknown_school_rejected(session: AsyncSession) -> None:
    """(д) INSERT події з неіснуючим school_id → помилка FK (SQLSTATE 23503)."""
    session.add(_event(uuid.uuid4(), seq=1))
    with pytest.raises(IntegrityError, match="events_school_id_fkey") as exc_info:
        await session.commit()

    assert getattr(exc_info.value.orig, "sqlstate", None) == FOREIGN_KEY_VIOLATION


# --- Роль zoshyt_readonly (ADR-0015): людина під ssh-тунелем лише читає ---


async def test_f_readonly_can_select_events(
    app_engine: AsyncEngine, readonly_engine: AsyncEngine
) -> None:
    """(е) SELECT з events під zoshyt_readonly — ок."""
    async with AsyncSession(app_engine) as s:
        school = await _school(s)
        s.add(_event(school.id, seq=1))
        await s.commit()

    async with AsyncSession(readonly_engine) as s:
        assert await s.scalar(select(func.count()).select_from(Event)) == 1
        assert await s.scalar(select(School.name)) == "Тестова школа"


async def test_g_readonly_cannot_insert_event(
    app_engine: AsyncEngine, readonly_engine: AsyncEngine
) -> None:
    """(є) INSERT у events під zoshyt_readonly → permission denied."""
    async with AsyncSession(app_engine) as s:
        # id беремо ДО commit: після нього об'єкт застарілий, а сесія закрита.
        school_id = (await _school(s)).id
        await s.commit()

    async with AsyncSession(readonly_engine) as s:
        s.add(_event(school_id, seq=1))
        with pytest.raises(ProgrammingError, match="permission denied for table events"):
            await s.commit()


async def test_h_readonly_cannot_insert_school(readonly_engine: AsyncEngine) -> None:
    """(ж) INSERT у schools під zoshyt_readonly → permission denied."""
    async with AsyncSession(readonly_engine) as s:
        s.add(School(id=uuid.uuid4(), name="Школа, якої не буде"))
        with pytest.raises(ProgrammingError, match="permission denied for table schools"):
            await s.commit()
