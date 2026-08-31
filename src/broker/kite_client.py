"""Zerodha Kite Connect client wrapper with dry-run support."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from config import KITE_INTERVAL_MAP
from src import settings
from src.broker.symbol_map import kite_exchange, kite_tradingsymbol

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    order_id: str
    dry_run: bool
    status: str
    message: str = ""


class KiteClient:
  """Thin wrapper around pykiteconnect. Works in dry-run without credentials."""

  def __init__(self, *, dry_run: bool | None = None):
    self.dry_run = settings.dry_run_mode() if dry_run is None else dry_run
    self._kite = None
    self._instruments: dict[str, dict] = {}
    self._token_by_symbol: dict[str, int] = {}

    if not self.dry_run and settings.kite_configured():
      self._connect()

  def _connect(self) -> None:
    try:
      from kiteconnect import KiteConnect
    except ImportError as exc:
      raise RuntimeError(
        "kiteconnect package not installed. Run: pip install kiteconnect"
      ) from exc

    self._kite = KiteConnect(api_key=settings.kite_api_key())
    self._kite.set_access_token(settings.kite_access_token())
    logger.info("Connected to Zerodha Kite Connect")

  @property
  def is_live(self) -> bool:
    return self._kite is not None and not self.dry_run

  def login_url(self) -> str:
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=settings.kite_api_key())
    return kite.login_url()

  def generate_session(self, request_token: str) -> dict[str, Any]:
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=settings.kite_api_key())
    return kite.generate_session(request_token, api_secret=settings.kite_api_secret())

  def _require_live(self):
    if self.dry_run or not self._kite:
      raise RuntimeError("Live Kite connection required but not available")

  def load_instruments(self, exchange: str = "NSE") -> None:
    if self.dry_run or not self._kite:
      return
    rows = self._kite.instruments(exchange)
    for row in rows:
      key = f"{row['exchange']}:{row['tradingsymbol']}"
      self._instruments[key] = row
      self._token_by_symbol[key] = row["instrument_token"]

  def instrument_token(self, symbol: str) -> int | None:
    key = f"{kite_exchange(symbol)}:{kite_tradingsymbol(symbol)}"
    if key in self._token_by_symbol:
      return self._token_by_symbol[key]
    if self.dry_run:
      return None
    self.load_instruments(kite_exchange(symbol))
    return self._token_by_symbol.get(key)

  def historical_data(
    self,
    symbol: str,
    interval: str,
    *,
    days: int = 59,
  ) -> pd.DataFrame | None:
    if self.dry_run or not self._kite:
      return None

    token = self.instrument_token(symbol)
    if not token:
      return None

    kite_interval = KITE_INTERVAL_MAP.get(interval, "15minute")
    end = datetime.now()
    start = end - timedelta(days=days)
    rows = self._kite.historical_data(token, start, end, kite_interval)
    if not rows:
      return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df.rename(
      columns={
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
      }
    )
    return df[["Open", "High", "Low", "Close", "Volume"]]

  def quote(self, symbol: str) -> dict | None:
    if self.dry_run or not self._kite:
      return None
    key = f"{kite_exchange(symbol)}:{kite_tradingsymbol(symbol)}"
    data = self._kite.quote([key])
    return data.get(key)

  def positions(self) -> dict:
    if self.dry_run or not self._kite:
      return {"net": [], "day": []}
    return self._kite.positions()

  def holdings(self) -> list[dict]:
    if self.dry_run or not self._kite:
      return []
    return self._kite.holdings()

  def margins(self) -> dict:
    if self.dry_run or not self._kite:
      return {}
    return self._kite.margins()

  def profile(self) -> dict:
    if self.dry_run or not self._kite:
      return {}
    return self._kite.profile()

  def place_order(
    self,
    *,
    symbol: str,
    transaction_type: str,
    quantity: int,
    order_type: str = "MARKET",
    product: str | None = None,
    price: float | None = None,
    trigger_price: float | None = None,
    tag: str | None = None,
  ) -> OrderResult:
    exchange = kite_exchange(symbol)
    tradingsymbol = kite_tradingsymbol(symbol)
    product = product or "CNC"
    tag = tag or settings.order_tag()

    if self.dry_run or not self._kite:
      fake_id = f"DRY-{datetime.now().strftime('%Y%m%d%H%M%S')}-{tradingsymbol}"
      msg = (
        f"DRY RUN {transaction_type} {quantity} {tradingsymbol} "
        f"{order_type} product={product}"
      )
      if trigger_price:
        msg += f" trigger={trigger_price:.2f}"
      logger.info(msg)
      return OrderResult(order_id=fake_id, dry_run=True, status="DRY_RUN", message=msg)

    from kiteconnect import KiteConnect

    params = {
      "variety": KiteConnect.VARIETY_REGULAR,
      "exchange": exchange,
      "tradingsymbol": tradingsymbol,
      "transaction_type": transaction_type,
      "quantity": quantity,
      "product": product,
      "order_type": order_type,
      "validity": KiteConnect.VALIDITY_DAY,
      "tag": tag,
    }
    if price is not None:
      params["price"] = price
    if trigger_price is not None:
      params["trigger_price"] = trigger_price

    try:
      order_id = self._kite.place_order(**params)
      return OrderResult(
        order_id=str(order_id), dry_run=False, status="PLACED", message="Order placed"
      )
    except Exception as exc:
      logger.exception("Order failed for %s", tradingsymbol)
      return OrderResult(order_id="", dry_run=False, status="FAILED", message=str(exc))

  def cancel_order(self, order_id: str, variety: str = "regular") -> bool:
    if self.dry_run or not self._kite:
      logger.info("DRY RUN cancel order %s", order_id)
      return True
    try:
      self._kite.cancel_order(variety=variety, order_id=order_id)
      return True
    except Exception:
      logger.exception("Cancel failed for %s", order_id)
      return False

  def orders(self) -> list[dict]:
    if self.dry_run or not self._kite:
      return []
    return self._kite.orders()
