"""Спільний предок моделей SQLAlchemy.

Base.metadata знає про всі таблиці, оголошені через моделі — саме її
читає alembic --autogenerate (env.py). Моделей поки нема: структура
таблиць — окреме обговорення перед першою міграцією.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
