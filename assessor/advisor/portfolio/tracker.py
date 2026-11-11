"""Carteira real a partir de data/carteira.json: posições, marcação a mercado
com a tabela `prices`, P&L, aportes e progresso até a meta de data/plano.json."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .ledger import Ledger, Trade

CRYPTO_SYMBOL = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}


def load_portfolio(db, carteira: Path | str = "data/carteira.json", plano: Path | str = "data/plano.json",
                   usdbrl: float | None = None) -> dict:
    c = json.loads(Path(carteira).read_text(encoding="utf-8")) if Path(carteira).exists() else {"aportes": [], "trades": []}
    p = json.loads(Path(plano).read_text(encoding="utf-8")) if Path(plano).exists() else {}
    led = Ledger()
    for t in c.get("trades", []):
        led.trades.append(Trade(ts=f"{t['data']}T12:00:00+00:00", ticker=t["ticker"], market=t.get("mercado", "BR"),
                                side=t["lado"], quantity=float(t["quantidade"]), price=float(t["preco"]),
                                fees=float(t.get("taxas", 0)), thesis=t.get("tese", "registrado"), stop=t.get("stop")))
    aportes = sum(float(a["valor_brl"]) for a in c.get("aportes", []))
    invested = 0.0
    positions = []
    for tk, pos in led.positions().items():
        if pos.quantity == 0:
            continue
        row = db.conn.execute("SELECT close, day FROM prices WHERE ticker=? ORDER BY day DESC LIMIT 1", (tk,)).fetchone()
        mark = row[0] if row else pos.avg_price
        fx = (usdbrl or 1.0) if pos.market in ("US", "cripto") else 1.0
        value = pos.quantity * mark * fx
        cost = pos.quantity * pos.avg_price * fx
        invested += value
        positions.append({"ticker": tk, "mercado": pos.market, "quantidade": pos.quantity, "preco_medio": round(pos.avg_price, 4),
                          "ultimo": round(mark, 4), "data_preco": row[1] if row else None, "valor_brl": round(value, 2),
                          "pnl_brl": round(value - cost, 2), "pnl_pct": round((value / cost - 1) if cost else 0, 4)})
    realized = sum(pp.realized_pnl for pp in led.positions().values())
    cash_flow = sum((-1 if t.side == "buy" else 1) * t.quantity * t.price - t.fees for t in led.trades)
    cash = aportes + cash_flow
    equity = cash + invested
    meta = float(p.get("meta_brl", 0) or 0)
    tempo = time_to_goal(equity, meta, aportes, c.get("aportes", []), float(p.get("retorno_semanal_alvo", 0.02) or 0.02))
    return {
        "tempo_ate_meta": tempo,
        "aportes_brl": round(aportes, 2), "caixa_brl": round(cash, 2), "investido_brl": round(invested, 2),
        "patrimonio_brl": round(equity, 2), "pnl_realizado_brl": round(realized, 2),
        "pnl_total_brl": round(equity - aportes, 2), "retorno_pct": round((equity / aportes - 1) if aportes else 0, 4),
        "meta_brl": meta, "progresso_meta_pct": round(equity / meta, 4) if meta else None,
        "posicoes": positions, "n_trades": len(led.trades), "plano": p, "atualizado": date.today().isoformat(),
        "ordens_planejadas": c.get("ordens_planejadas", []),
    }


def time_to_goal(equity: float, meta: float, aportes: float, aportes_list: list, weekly_target: float) -> dict:
    """Semanas até a meta: pelo ritmo-alvo do plano e pelo ritmo realizado (quando há 4+ semanas)."""
    import math
    from datetime import date as _d
    out = {"retorno_semanal_alvo": weekly_target}
    if not meta or equity <= 0:
        return out
    if equity >= meta:
        out["semanas_pelo_alvo"] = 0; out["status"] = "meta atingida"; return out
    out["semanas_pelo_alvo"] = math.ceil(math.log(meta / equity) / math.log(1 + weekly_target))
    out["data_estimada_pelo_alvo"] = (_d.today() + __import__("datetime").timedelta(weeks=out["semanas_pelo_alvo"])).isoformat()
    try:
        inicio = min(_d.fromisoformat(a["data"]) for a in aportes_list)
        semanas = max(1, (_d.today() - inicio).days / 7)
        if semanas >= 4 and aportes > 0:
            r = (equity / aportes) ** (1 / semanas) - 1
            out["retorno_semanal_realizado"] = round(r, 4)
            out["semanas_pelo_ritmo_atual"] = math.ceil(math.log(meta / equity) / math.log(1 + r)) if r > 0 else None
    except Exception:  # noqa: BLE001
        pass
    return out