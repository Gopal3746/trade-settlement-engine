from collections.abc import Iterable

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from trade_recon.database import TradeRecord
from trade_recon.models import Side, Trade, TradeSource


class TradeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, trade: Trade) -> TradeRecord:
        record = TradeRecord(
            trade_id=trade.trade_id,
            source=trade.source.value,
            symbol=trade.symbol,
            side=trade.side.value,
            quantity=trade.quantity,
            price=trade.price,
            trade_date=trade.trade_date,
            settlement_date=trade.settlement_date,
            broker=trade.broker,
            account=trade.account,
            currency=trade.currency,
        )

        self._session.add(record)

        return record

    def add_many(
        self,
        trades: Iterable[Trade],
    ) -> int:
        count = 0

        for trade in trades:
            self.add(trade)
            count += 1

        return count

    def get_by_source(
        self,
        source: TradeSource,
    ) -> list[Trade]:
        statement = (
            select(TradeRecord)
            .where(
                TradeRecord.source == source.value
            )
            .order_by(TradeRecord.trade_id)
        )

        records = self._session.scalars(statement).all()

        return [
            self._to_domain(record)
            for record in records
        ]

    def count(self) -> int:
        statement = select(TradeRecord)

        return len(
            self._session.scalars(statement).all()
        )

    @staticmethod
    def _to_domain(record: TradeRecord) -> Trade:
        return Trade(
            trade_id=record.trade_id,
            source=TradeSource(record.source),
            symbol=record.symbol,
            side=Side(record.side),
            quantity=record.quantity,
            price=record.price,
            trade_date=record.trade_date,
            settlement_date=record.settlement_date,
            broker=record.broker,
            account=record.account,
            currency=record.currency,
        )

    def add_many_idempotent(
        self,
        trades: Iterable[Trade],
    ) -> tuple[int, int]:
        trade_list = list(trades)

        if not trade_list:
            return 0, 0

        incoming_keys = {
            (
                trade.trade_id,
                trade.source.value,
            )
            for trade in trade_list
        }

        statement = select(
            TradeRecord.trade_id,
            TradeRecord.source,
        ).where(
            tuple_(
                TradeRecord.trade_id,
                TradeRecord.source,
            ).in_(incoming_keys)
        )

        existing_keys = set(
            self._session.execute(statement).all()
        )

        inserted = 0
        skipped_duplicate = 0

        for trade in trade_list:
            key = (
                trade.trade_id,
                trade.source.value,
            )

            if key in existing_keys:
                skipped_duplicate += 1
                continue

            self.add(trade)

            existing_keys.add(key)
            inserted += 1

        return inserted, skipped_duplicate
