"""Operações curtas: dados intradiários (Yahoo, 15 min, 5 dias) e setups.

Setups calculados por ativo:
- gap de abertura vs fechamento anterior (e vs ADR/EWZ quando houver)
- rompimento da faixa de abertura (primeiros 30 min) para cima/baixo
- posição vs VWAP do dia
- volume anormal: volume de hoje até agora vs média do mesmo horário em 5 dias
- faixa do dia vs ATR diário (quanto do movimento "normal" já foi consumido)
Cada setup vira um candidato com stop e alvo em múltiplos de ATR; o tamanho
sempre vem do RiskBudget.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from ..data.market import USER_AGENT, yahoo_symbol, _require_requests


@dataclass(frozen=True)
class IntraBar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def fetch_intraday(ticker: str, market: str = "BR", interval: str = "15m", range_: str = "5d", timeout: int = 20) -> list[IntraBar]:
    import requests
    _require_requests()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(ticker, market)}"
    r = requests.get(url, params={"interval": interval, "range": range_}, timeout=timeout,
                     headers={"User-Agent": "Mozilla/5.0 " + USER_AGENT})
    r.raise_for_status()
    return parse_intraday(r.json())


def parse_intraday(data: dict) -> list[IntraBar]:
    res = (data.get("chart") or {}).get("result") or []
    if not res:
        return []
    r = res[0]
    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    out = []
    for i, t in enumerate(r.get("timestamp") or []):
        c = (q.get("close") or [None])[i]
        if c is None:
            continue
        out.append(IntraBar(datetime.fromtimestamp(t, tz=timezone.utc), float((q.get("open") or [c])[i] or c),
                            float((q.get("high") or [c])[i] or c), float((q.get("low") or [c])[i] or c), float(c),
                            float((q.get("volume") or [0])[i] or 0)))
    return out


@dataclass(frozen=True)
class ShortSetup:
    ticker: str
    kind: str          # gap_alta | gap_baixa | rompimento_faixa_alta | rompimento_faixa_baixa | reversao_vwap | nenhum
    direction: str     # compra | venda | neutro
    last: float
    gap_pct: float
    vwap: float
    above_vwap: bool
    opening_range: tuple[float, float]
    volume_ratio: float
    range_vs_atr: float
    stop: float | None
    target: float | None
    notes: list[str]


def short_setups(ticker: str, bars: list[IntraBar], atr_daily: float, prev_close: float | None = None,
                 proxy_move_pct: float | None = None) -> ShortSetup:
    """bars: intradiários de 5 dias; usa o último dia. proxy_move_pct: variação
    do ADR/EWZ na véspera para julgar o gap."""
    if not bars:
        return ShortSetup(ticker, "nenhum", "neutro", 0, 0, 0, False, (0, 0), 0, 0, None, None, ["sem dados"])
    days: dict[str, list[IntraBar]] = {}
    for b in bars:
        days.setdefault(b.ts.date().isoformat(), []).append(b)
    keys = sorted(days)
    today = days[keys[-1]]
    prev = days[keys[-2]] if len(keys) > 1 else []
    prev_close = prev_close or (prev[-1].close if prev else today[0].open)
    opn = today[0].open
    gap = opn / prev_close - 1
    n_open = max(1, min(2, len(today)))              # 2 barras de 15 min = 30 min
    orh, orl = max(b.high for b in today[:n_open]), min(b.low for b in today[:n_open])
    tv = sum(b.volume for b in today) or 1.0
    vwap = sum(b.close * b.volume for b in today) / tv
    last = today[-1].close
    k = len(today)
    same_time = [sum(b.volume for b in days[d][:k]) for d in keys[:-1]] or [tv]
    vol_ratio = tv / (sum(same_time) / len(same_time) or 1.0)
    day_range = max(b.high for b in today) - min(b.low for b in today)
    rva = day_range / atr_daily if atr_daily else 0.0
    notes = []
    kind, direction, stop, target = "nenhum", "neutro", None, None
    if abs(gap) >= 0.015:
        kind = "gap_alta" if gap > 0 else "gap_baixa"
        notes.append(f"gap de {gap:+.1%} na abertura")
        if proxy_move_pct is not None:
            notes.append(f"proxy (ADR/EWZ) na véspera: {proxy_move_pct:+.1%}")
            if (gap > 0) != (proxy_move_pct > 0):
                notes.append("gap contra o proxy: candidato a fechar o gap")
    if k > n_open and last > orh and last > vwap:
        kind, direction = "rompimento_faixa_alta", "compra"
        stop, target = round(orl, 2), round(last + 1.0 * atr_daily, 2)
    elif k > n_open and last < orl and last < vwap:
        kind, direction = "rompimento_faixa_baixa", "venda"
        stop, target = round(orh, 2), round(last - 1.0 * atr_daily, 2)
    elif kind.startswith("gap") and ((gap > 0 and last < vwap) or (gap < 0 and last > vwap)):
        kind, direction = "reversao_vwap", "venda" if gap > 0 else "compra"
        stop = round(max(b.high for b in today), 2) if gap > 0 else round(min(b.low for b in today), 2)
        target = round(prev_close, 2)
    if vol_ratio >= 1.8:
        notes.append(f"volume {vol_ratio:.1f}x o normal para este horário")
    elif direction != "neutro" and vol_ratio < 0.8:
        notes.append("volume fraco: setup sem confirmação")
    if rva >= 1.2:
        notes.append(f"dia já andou {rva:.1f}x o ATR: entrada tardia")
    return ShortSetup(ticker, kind, direction, round(last, 4), round(gap, 4), round(vwap, 4), last > vwap,
                      (round(orl, 4), round(orh, 4)), round(vol_ratio, 2), round(rva, 2), stop, target, notes)


def fetch_many(tickers: list[str], market: str, errors: list[str], sleep: float = 0.4) -> dict[str, list[IntraBar]]:
    out = {}
    for t in tickers:
        try:
            out[t] = fetch_intraday(t, market)
        except Exception as e:  # noqa: BLE001
            errors.append(f"intradia {t}: {type(e).__name__}: {str(e)[:100]}")
        time.sleep(sleep)
    return out
