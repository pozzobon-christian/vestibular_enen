"""Conector ao vivo com a B3 via MetaTrader 5 da corretora.

Requisitos (no computador do usuário, Windows):
1. Conta em corretora que ofereça MT5 para B3 (ex.: Rico, Clear, XP, Genial) e
   o terminal MT5 instalado e logado.
2. `pip install MetaTrader5` (pacote oficial, só funciona no Windows com o terminal aberto).
3. Variáveis de ambiente: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER (nunca no código).

Modos:
- "papel" (padrão): lê cotações reais, simula a ordem e grava em data/live/papel.jsonl.
- "real": só se LIVE_TRADING=1 no ambiente E a tese estiver aprovada no
  laboratório E o porteiro de risco aprovar a ordem. Sem as três, recusa.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Quote:
    symbol: str; bid: float; ask: float; last: float; ts: str


class MT5Connector:
    def __init__(self, mode: str = "papel", approved_theses: set[str] | None = None, client=None):
        self.mode = mode
        self.approved = approved_theses or set()
        self.mt5 = client          # injetável para teste; senão importa o pacote oficial
        self.log = Path("data/live/papel.jsonl")

    def connect(self) -> None:
        if self.mt5 is None:
            import MetaTrader5 as mt5   # noqa: N813  (só Windows)
            self.mt5 = mt5
        ok = self.mt5.initialize(login=int(os.environ["MT5_LOGIN"]), password=os.environ["MT5_PASSWORD"], server=os.environ["MT5_SERVER"]) \
            if os.environ.get("MT5_LOGIN") else self.mt5.initialize()
        if not ok:
            raise RuntimeError(f"MT5 não conectou: {self.mt5.last_error()}")

    def quote(self, symbol: str) -> Quote:
        self.mt5.symbol_select(symbol, True)
        t = self.mt5.symbol_info_tick(symbol)
        return Quote(symbol, t.bid, t.ask, t.last, datetime.fromtimestamp(t.time, tz=timezone.utc).isoformat())

    def bars(self, symbol: str, timeframe: str = "M1", n: int = 500) -> list[dict]:
        tf = getattr(self.mt5, f"TIMEFRAME_{timeframe}")
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, n)
        return [{"ts": int(r["time"]) * 1000, "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]), "c": float(r["close"]), "v": float(r["real_volume"] or r["tick_volume"])} for r in rates]

    def order(self, symbol: str, side: str, qty: int, sl: float, tp: float, thesis: str, risk_ok: bool) -> dict:
        q = self.quote(symbol)
        px = q.ask if side == "buy" else q.bid
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "symbol": symbol, "side": side, "qty": qty, "price": px, "sl": sl, "tp": tp, "thesis": thesis, "mode": self.mode}
        real = self.mode == "real" and os.environ.get("LIVE_TRADING") == "1" and thesis in self.approved and risk_ok
        if self.mode == "real" and not real:
            rec["status"] = "recusada: precisa LIVE_TRADING=1, tese aprovada no laboratório e porteiro aprovado"
        elif real:
            req = {"action": self.mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": float(qty),
                   "type": self.mt5.ORDER_TYPE_BUY if side == "buy" else self.mt5.ORDER_TYPE_SELL,
                   "price": px, "sl": sl, "tp": tp, "deviation": 5, "comment": thesis[:20],
                   "type_time": self.mt5.ORDER_TIME_DAY, "type_filling": self.mt5.ORDER_FILLING_RETURN}
            res = self.mt5.order_send(req)
            rec["status"] = f"enviada: retcode {getattr(res, 'retcode', None)}"
        else:
            rec["status"] = "papel"
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec


def download_history(conn: "MT5Connector", symbol: str = "WIN$N", timeframe: str = "M5", years: int = 10,
                     out_dir: Path = Path("data/mt5")) -> Path:
    """Baixa anos de candles intradiários do MT5 da corretora (ex.: WIN$N =
    mini-índice contínuo, WDO$N = mini-dólar, PETR4). É a fonte que resolve o
    'day trade de 10 anos': as corretoras guardam M1/M5 de vários anos."""
    from datetime import timedelta
    mt5 = conn.mt5
    end = datetime.now(timezone.utc); start = end - timedelta(days=365 * years)
    conn.mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_range(symbol, getattr(mt5, f"TIMEFRAME_{timeframe}"), start, end)
    rows = [{"ts": int(r["time"]) * 1000, "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
             "c": float(r["close"]), "v": float(r["real_volume"] or r["tick_volume"])} for r in (rates if rates is not None else [])]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{symbol.replace('$', '_')}_{timeframe}.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path
