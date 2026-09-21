import os
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Date,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://"
    "trade_user:trade_pass@localhost:5432/trade_recon"
)


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trades"

    __table_args__ = (
        UniqueConstraint(
            "trade_id",
            "source",
            name="uq_trade_id_source",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    trade_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    side: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )

    trade_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    settlement_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    broker: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    account: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )


def create_db_engine(
    database_url: str | None = None,
) -> Engine:
    return create_engine(
        database_url or get_database_url(),
        pool_pre_ping=True,
    )


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
