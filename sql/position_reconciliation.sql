WITH signed_trades AS (
    SELECT
        trade_id,
        source,
        account,
        symbol,
        CASE
            WHEN side = 'BUY' THEN quantity
            WHEN side = 'SELL' THEN -quantity
            ELSE 0
        END AS signed_quantity
    FROM trades
),

positions AS (
    SELECT
        source,
        account,
        symbol,
        SUM(signed_quantity) AS net_quantity,
        COUNT(*) AS trade_count
    FROM signed_trades
    GROUP BY
        source,
        account,
        symbol
),

internal_positions AS (
    SELECT
        account,
        symbol,
        net_quantity,
        trade_count
    FROM positions
    WHERE source = 'internal'
),

broker_positions AS (
    SELECT
        account,
        symbol,
        net_quantity,
        trade_count
    FROM positions
    WHERE source = 'broker'
),

reconciled_positions AS (
    SELECT
        COALESCE(
            internal.account,
            broker.account
        ) AS account,

        COALESCE(
            internal.symbol,
            broker.symbol
        ) AS symbol,

        COALESCE(
            internal.net_quantity,
            0
        ) AS internal_quantity,

        COALESCE(
            broker.net_quantity,
            0
        ) AS broker_quantity,

        COALESCE(
            internal.net_quantity,
            0
        ) - COALESCE(
            broker.net_quantity,
            0
        ) AS quantity_difference,

        COALESCE(
            internal.trade_count,
            0
        ) AS internal_trade_count,

        COALESCE(
            broker.trade_count,
            0
        ) AS broker_trade_count

    FROM internal_positions AS internal

    FULL OUTER JOIN broker_positions AS broker
        ON internal.account = broker.account
        AND internal.symbol = broker.symbol
),

position_breaks AS (
    SELECT
        account,
        symbol,
        internal_quantity,
        broker_quantity,
        quantity_difference,
        internal_trade_count,
        broker_trade_count,

        CASE
            WHEN internal_trade_count = 0
                THEN 'MISSING_INTERNAL_POSITION'
            WHEN broker_trade_count = 0
                THEN 'MISSING_BROKER_POSITION'
            ELSE 'POSITION_BREAK'
        END AS break_type

    FROM reconciled_positions

    WHERE quantity_difference <> 0
),

ranked_breaks AS (
    SELECT
        account,
        symbol,
        internal_quantity,
        broker_quantity,
        quantity_difference,
        internal_trade_count,
        broker_trade_count,
        break_type,

        ROW_NUMBER() OVER (
            ORDER BY
                ABS(quantity_difference) DESC,
                account,
                symbol
        ) AS break_rank

    FROM position_breaks
)

SELECT
    account,
    symbol,
    internal_quantity,
    broker_quantity,
    quantity_difference,
    internal_trade_count,
    broker_trade_count,
    break_type,
    break_rank
FROM ranked_breaks
ORDER BY break_rank;
