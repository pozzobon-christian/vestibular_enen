"""Livro-razão de operações: registro auditável, posições e P&L."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Trade:
    ts: str                 # ISO-8601 UTC
    ticker: str
    market: str             # BR | US | cripto
    side: str               # buy | sell
    quantity: float
    price: float
    fees: float = 0.0
    thesis: str = ""        # por que entramos
    stop: float | None = None
    target: float | None = None
    risk_amount: float = 0.0
    tags: list[str] = field(default_factory=list)

    @property
    def signed_qty(self) -> float:
        return self.quantity if self.side == "buy" else -self.quantity


@dataclass
class Position:
    ticker: str
    market: str
    quantity: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    def unrealized(self, mark: float) -> float:
        return (mark - self.avg_price) * self.quantity


class Ledger:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self.trades: list[Trade] = []
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.trades.append(Trade(**json.loads(line)))

    def record(self, trade: Trade) -> None:
        if not trade.thesis:
            raise ValueError("toda operação precisa de tese registrada")
        self.trades.append(trade)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(trade), ensure_ascii=False) + "\n")

    def positions(self) -> dict[str, Position]:
        pos: dict[str, Position] = {}
        for t in sorted(self.trades, key=lambda x: x.ts):
            p = pos.setdefault(t.ticker, Position(t.ticker, t.market))
            q = t.signed_qty
            if p.quantity == 0 or (p.quantity > 0) == (q > 0):
                total_cost = p.avg_price * p.quantity + t.price * q
                p.quantity += q
                p.avg_price = total_cost / p.quantity if p.quantity else 0.0
            else:
                closing = min(abs(q), abs(p.quantity)) * (1 if p.quantity > 0 else -1)
                p.realized_pnl += (t.price - p.avg_price) * closing - t.fees
                p.quantity += q
                if p.quantity == 0:
                    p.avg_price = 0.0
                elif (p.quantity > 0) != (closing > 0):
                    p.avg_price = t.price
        return pos

    def realized_pnl(self, since: datetime | None = None) -> float:
        if since is None:
            return sum(p.realized_pnl for p in self.positions().values())
        # recomputa só com trades desde `since` para posições fechadas no período
        tmp = Ledger()
        for t in self.trades:
            if datetime.fromisoformat(t.ts) >= since:
                tmp.trades.append(t)
        return sum(p.realized_pnl for p in tmp.positions().values())

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
