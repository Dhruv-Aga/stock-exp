"""Order placement and stop-loss management."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.broker.kite_client import KiteClient, OrderResult
from src.broker.symbol_map import kite_product, round_quantity
from src.db import record_order

logger = logging.getLogger(__name__)


@dataclass
class TradeIntent:
    symbol: str
    side: int  # 1 buy/long, -1 sell/short
    quantity: float
    price: float
    stop_price: float
    reason: str


class OrderManager:
    def __init__(self, client: KiteClient):
        self.client = client

    def _txn_type(self, side: int, *, entry: bool) -> str:
        if entry:
            return "BUY" if side == 1 else "SELL"
        return "SELL" if side == 1 else "BUY"

    def enter(self, intent: TradeIntent) -> OrderResult:
        qty = round_quantity(intent.symbol, intent.quantity)
        product = kite_product(intent.symbol)
        result = self.client.place_order(
            symbol=intent.symbol,
            transaction_type=self._txn_type(intent.side, entry=True),
            quantity=qty,
            order_type="MARKET",
            product=product,
        )
        record_order(
            order_id=result.order_id or "FAILED",
            symbol=intent.symbol,
            side="BUY" if intent.side == 1 else "SELL",
            quantity=qty,
            order_type="MARKET",
            status=result.status,
            dry_run=result.dry_run,
            reason=intent.reason,
            price=intent.price,
            stop_price=intent.stop_price,
        )
        if result.status in ("PLACED", "DRY_RUN"):
            self.place_stop_loss(intent, qty)
        return result

    def exit(self, intent: TradeIntent, *, position_side: int) -> OrderResult:
        qty = round_quantity(intent.symbol, intent.quantity)
        product = kite_product(intent.symbol)
        result = self.client.place_order(
            symbol=intent.symbol,
            transaction_type=self._txn_type(position_side, entry=False),
            quantity=qty,
            order_type="MARKET",
            product=product,
        )
        record_order(
            order_id=result.order_id or "FAILED",
            symbol=intent.symbol,
            side="SELL" if position_side == 1 else "BUY",
            quantity=qty,
            order_type="MARKET",
            status=result.status,
            dry_run=result.dry_run,
            reason=intent.reason,
            price=intent.price,
            stop_price=intent.stop_price,
        )
        return result

    def place_stop_loss(self, intent: TradeIntent, qty: int) -> OrderResult:
        product = kite_product(intent.symbol)
        if intent.side == 1:
            txn = "SELL"
            trigger = round(intent.stop_price, 2)
            price = round(trigger * 0.995, 2)
        else:
            txn = "BUY"
            trigger = round(intent.stop_price, 2)
            price = round(trigger * 1.005, 2)

        result = self.client.place_order(
            symbol=intent.symbol,
            transaction_type=txn,
            quantity=qty,
            order_type="SL",
            product=product,
            price=price,
            trigger_price=trigger,
        )
        record_order(
            order_id=result.order_id or "FAILED-SL",
            symbol=intent.symbol,
            side=txn,
            quantity=qty,
            order_type="SL",
            status=result.status,
            dry_run=result.dry_run,
            reason="stop_loss",
            price=price,
            stop_price=trigger,
        )
        return result
