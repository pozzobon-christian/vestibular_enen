"""Orquestrador 24 horas: um único ponto que sabe que horas são em cada
mercado, decide o que rodar e mantém o estado de todas as estratégias.

Mercados (horário de Brasília):
- Cripto: 24 horas, 7 dias.
- B3: pregão 10h00-17h55 (pré-abertura 9h45; leilão de fechamento 17h55-18h00).
- EUA: 10h30/11h30-17h00/18h00 conforme horário de verão dos EUA.
Tarefas por janela: ver PLANO. Saída: data/estado-24h.json (lido pelo painel).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BRT = ZoneInfo("America/Sao_Paulo"); NY = ZoneInfo("America/New_York")
STATE = Path("data/estado-24h.json")

PLANO = [
    {"quando": "toda hora, 24x7", "tarefa": "cripto: sinal de tendência do BTC/ETH, risco cripto, robô de papel do day trade (se houver tese aprovada)"},
    {"quando": "05h55 dias úteis", "tarefa": "briefing global: madrugada, calendário, regime, ordens do dia"},
    {"quando": "B3 aberta (10h-17h55), de hora em hora", "tarefa": "intradia: rompimentos, gaps, volume anormal, stops das posições abertas"},
    {"quando": "17h40 dias úteis", "tarefa": "sinal do efeito noite: comprar no leilão de fechamento das ações aprovadas"},
    {"quando": "17h47 dias úteis", "tarefa": "fechamento: carteira, P&L, ordens de amanhã"},
    {"quando": "EUA abertos, de hora em hora", "tarefa": "ações e opções dos EUA (quando houver conta), fluxo de IBIT/COIN/MSTR"},
    {"quando": "1º pregão do mês", "tarefa": "momentum do índice: BOVA11 contra CDI; rolagem da venda coberta"},
    {"quando": "domingo 20h", "tarefa": "recalcula os backtests de 10 anos, histórico de acerto dos influenciadores e revisão semanal"},
]


def sessions(now_utc: datetime) -> dict:
    b = now_utc.astimezone(BRT); n = now_utc.astimezone(NY)
    weekday = b.weekday() < 5
    b3 = weekday and (b.hour, b.minute) >= (10, 0) and (b.hour, b.minute) < (17, 55)
    us = n.weekday() < 5 and (n.hour, n.minute) >= (9, 30) and n.hour < 16
    return {"agora_brasilia": b.strftime("%Y-%m-%d %H:%M"), "cripto": True, "b3_aberta": b3, "eua_abertos": us,
            "fim_de_semana": not weekday}


def due_tasks(now_utc: datetime) -> list[str]:
    b = now_utc.astimezone(BRT); s = sessions(now_utc); out = ["cripto"]
    if s["b3_aberta"]:
        out.append("b3_intradia")
    if b.weekday() < 5 and b.hour == 17 and 35 <= b.minute < 55:
        out.append("efeito_noite")
    if s["eua_abertos"]:
        out.append("eua")
    if b.weekday() == 6 and b.hour == 20:
        out.append("backtests_semanais")
    return out


def _closes(db, t):
    return db.conn.execute("SELECT day, open, close FROM prices WHERE ticker=? ORDER BY day", (t,)).fetchall()


def current_signals(db, cdi: dict[str, float] | None = None) -> dict:
    """Sinal de HOJE de cada estratégia, com os mesmos parâmetros do backtest."""
    out = {}
    btc = [r[2] for r in _closes(db, "BTC")]
    for ma in (50, 100, 200):
        if len(btc) >= ma:
            m = sum(btc[-ma:]) / ma
            out[f"btc_tendencia_{ma}"] = {"posicao": "comprado" if btc[-1] > m else "caixa", "preco": round(btc[-1]), "media": round(m),
                                         "distancia_pct": round((btc[-1] / m - 1) * 100, 1)}
    bova = _closes(db, "BOVA11")
    if len(bova) > 211 and cdi:
        r = bova[-1][2] / bova[-211][2] - 1
        rf = math.prod(1 + cdi.get(d, 0.0) for d, _, _ in bova[-210:]) - 1
        out["bova11_momentum_vs_cdi"] = {"posicao": "BOVA11" if r > rf else "CDI", "retorno_10m": round(r, 4), "cdi_10m": round(rf, 4),
                                         "rebalanceia": "1º pregão do mês"}
    approved = Path("data/cases/estrategias-10-anos.json")
    if approved.exists():
        rep = json.loads(approved.read_text(encoding="utf-8"))
        winners = [t for t, v in rep.get("acoes", {}).items()
                   if v.get("efeito_noite", {}).get("ao_ano", -1) > max(v.get("comprar_e_segurar", {}).get("ao_ano", 0), 0.10)]
        out["efeito_noite"] = {"ativos_aprovados": winners, "acao": "comprar no leilão de fechamento (17h55) e vender no de abertura (10h00)" if winners else "nenhum ativo aprovado",
                               "regra": "só ativos cujo efeito noite em 10 anos superou comprar e segurar e o CDI médio"}
    return out


def run(now_utc: datetime | None = None, db=None) -> dict:
    from .storage import MonitorDB
    now_utc = now_utc or datetime.now(timezone.utc)
    db = db or MonitorDB("data/monitor.db")
    cdi_path = Path("data/cases/cdi.json")
    cdi = json.loads(cdi_path.read_text(encoding="utf-8")) if cdi_path.exists() else None
    state = {"gerado_em": now_utc.isoformat(), "sessoes": sessions(now_utc), "tarefas_agora": due_tasks(now_utc),
             "plano_24h": PLANO, "sinais_hoje": current_signals(db, cdi)}
    lab = Path("data/daytrade/lab.json")
    if lab.exists():
        L = json.loads(lab.read_text(encoding="utf-8"))
        approved = [f"{m}:{k}" for m, r in L.get("acoes", {}).items() for k, v in r.get("agregado_por_tese", {}).items() if v["avaliacao"]["aprovada"]]
        approved += [k for k, v in L.get("resultados", {}).items() if v["avaliacao"]["aprovada"]]
        state["day_trade"] = {"teses_aprovadas": approved, "robo_de_papel": "ligado" if approved else "desligado: nenhuma tese aprovada"}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2)[:3000])
