"""Calendário de divulgações: tudo que tem data e move preço.

Fontes:
1. Regras de recorrência (oficiais, com horário em Brasília): IBGE, BCB, Tesouro,
   Caged, Conab, Fed, BLS, BEA, EIA, USDA, OPEP, NOAA, vencimentos de opções.
2. Reuniões com data fixa (Copom, FOMC, OPEP+): tabela do ano, marcada
   "confirmar" quando a fonte oficial ainda não foi lida.
3. Resultados das empresas da lista: Yahoo calendarEvents (earningsDate).
4. Itens sem data (guerra, clima extremo, greves): não entram no calendário;
   são tratados pela camada de notícias. Aqui entram só os que têm data
   (relatórios de furacões, ENSO, safra, eleições, cúpulas).

Saída: lista de eventos por dia com impacto esperado e preparação.
"""
from __future__ import annotations

import calendar as _cal
import json
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone


@dataclass
class Event:
    data: str                 # YYYY-MM-DD
    hora_brt: str             # "09:00" ou "" quando indefinida
    evento: str
    fonte: str
    categoria: str            # macro_br | macro_us | macro_global | commodities | clima | geopolitica | empresas | mercado
    ativos: list[str]
    impacto: str              # alto | medio | baixo
    o_que_esperar: str
    preparacao: str
    confirmar: bool = False


def _nth_weekday(y: int, m: int, weekday: int, n: int) -> date:
    d = date(y, m, 1)
    off = (weekday - d.weekday()) % 7
    return d + timedelta(days=off + 7 * (n - 1))


def _business_day(y: int, m: int, n: int) -> date:
    d = date(y, m, 1); k = 0
    while True:
        if d.weekday() < 5:
            k += 1
            if k == n:
                return d
        d += timedelta(days=1)


FIXED_2026 = [
    ("2026-12-09", "18:30", "Copom: decisão da Selic", "Banco Central", "macro_br", ["BOVA11", "ITUB4", "BBAS3", "HGLG11", "MXRF11", "KNRI11"], "alto",
     "Juros definem bancos, FIIs e câmbio; comunicado às 18h30, mercado reage no dia seguinte.", "Nenhuma posição alavancada; FIIs de papel ganham com juro alto, tijolo perde.", True),
    ("2026-12-09", "16:00", "FOMC: decisão de juros dos EUA e projeções", "Federal Reserve", "macro_us", ["SPY", "QQQ", "NVDA", "BTC", "ETH", "GC=F"], "alto",
     "Dot plot e coletiva às 16h30 movem dólar, Treasury e cripto.", "Reduzir tamanho em cripto e tecnologia na véspera; esperar a coletiva.", True),
    ("2026-11-30", "", "OPEP+: reunião ministerial (cotas de produção)", "OPEP", "commodities", ["PETR4", "PRIO3", "BZ=F"], "alto",
     "Corte = Brent sobe = PETR4/PRIO3 sobem; aumento = o inverso.", "Não abrir petróleo na véspera; operar o gap da segunda com proxy BZ=F.", True),
    ("2026-11-15", "", "Cúpula do G20 (Líderes)", "G20", "geopolitica", ["DX-Y.NYB", "EWZ"], "medio",
     "Comunicados sobre comércio e clima; raramente move preço no dia.", "Só observar.", True),
    ("2026-11-30", "", "Fim da temporada de furacões do Atlântico", "NOAA", "clima", ["CL=F", "BZ=F"], "baixo",
     "Risco de parada de refino no Golfo acaba.", "Prêmio de risco do petróleo cai.", False),
]


def recurring(start: date, end: date) -> list[Event]:
    ev: list[Event] = []
    d = start
    while d <= end:
        y, m, wd = d.year, d.month, d.weekday()
        # semanais
        if wd == 0:
            ev.append(Event(d.isoformat(), "08:25", "Boletim Focus (expectativas Selic, IPCA, câmbio)", "Banco Central", "macro_br", ["BOVA11", "BRL=X"], "medio",
                            "Revisões de Selic e inflação ajustam juros futuros na abertura.", "Ler antes das 10h; muda a leitura de bancos e FIIs."))
        if wd == 2:
            ev.append(Event(d.isoformat(), "12:30", "Estoques de petróleo dos EUA (EIA)", "EIA", "commodities", ["PETR4", "PRIO3", "CL=F", "BZ=F"], "medio",
                            "Queda de estoque acima do esperado = petróleo sobe.", "Evitar abrir petróleo 30 min antes."))
        if wd == 3:
            ev.append(Event(d.isoformat(), "10:30", "Pedidos de seguro-desemprego dos EUA", "Dept. of Labor", "macro_us", ["SPY", "QQQ"], "baixo",
                            "Surpresas grandes mexem com Treasury e dólar.", "Só observar."))
        if wd == 4 and 15 <= d.day <= 21:
            ev.append(Event(d.isoformat(), "", "Vencimento mensal de opções (B3 e EUA, 3ª sexta)", "B3 / CBOE", "mercado", ["PETR4", "VALE3", "BOVA11", "SPY", "NVDA"], "medio",
                            "Gamma alto: preço gravita para strikes com mais aberto; volatilidade na última hora.", "Não iniciar swing no dia; stops mais largos ou ficar fora."))
        # mensais (datas aproximadas pelas regras usuais; confirmar nas agendas oficiais)
        if d == _nth_weekday(y, m, 4, 1):
            ev.append(Event(d.isoformat(), "10:30", "Payroll (emprego nos EUA)", "BLS", "macro_us", ["SPY", "QQQ", "DX-Y.NYB", "BTC"], "alto",
                            "Forte = juro sobe = dólar sobe, cripto e tecnologia caem.", "Sem posição nova em cripto/tecnologia na véspera; operar após 10h35.", True))
        if d.day == 10 and wd < 5 or (d.day in (11, 12) and _business_day(y, m, 1).day <= 2 and wd < 5 and d.day == 10 + (7 - date(y, m, 10).weekday() if date(y, m, 10).weekday() >= 5 else 0)):
            ev.append(Event(d.isoformat(), "09:00", "IPCA do mês anterior", "IBGE", "macro_br", ["BOVA11", "MXRF11", "HGLG11", "BRL=X"], "alto",
                            "Inflação acima do esperado = juros futuros sobem = FIIs e bolsa caem; FIIs IPCA+ ganham no rendimento.", "Conferir consenso no Focus; sem ordem de B3 entre 9h e 10h15.", True))
        if d.day in (12, 13) and wd < 5 and d == max(x for x in [date(y, m, 12), date(y, m, 13)] if x.weekday() < 5):
            ev.append(Event(d.isoformat(), "10:30", "CPI (inflação dos EUA)", "BLS", "macro_us", ["SPY", "QQQ", "NVDA", "BTC", "GC=F"], "alto",
                            "Acima do esperado = Treasury sobe = tudo cai, cripto mais.", "Reduzir cripto na véspera; esperar 10h35.", True))
        if d.day == 25 and wd < 5:
            ev.append(Event(d.isoformat(), "09:00", "IPCA-15 (prévia da inflação)", "IBGE", "macro_br", ["BOVA11", "MXRF11"], "medio",
                            "Antecipa o IPCA; mesmo efeito, menor.", "Ler antes das 10h.", True))
        if d.day in (10, 11, 12) and wd < 5 and d == min(x for x in [date(y, m, 10), date(y, m, 11), date(y, m, 12)] if x.weekday() < 5):
            ev.append(Event(d.isoformat(), "13:00", "WASDE: oferta e demanda agrícola mundial", "USDA", "commodities", ["SLCE3", "SMTO3", "ZS=F", "ZC=F"], "medio",
                            "Safra e estoques de soja/milho; move agro e câmbio no Brasil.", "Relevante para agro e para o real (exportações).", True))
        if d == _business_day(y, m, 8):
            ev.append(Event(d.isoformat(), "09:00", "Levantamento de safra (Conab)", "Conab", "commodities", ["SLCE3", "SMTO3", "BRL=X"], "baixo",
                            "Estimativa de produção de grãos.", "Observar para agro.", True))
        if d == _nth_weekday(y, m, 3, 4):
            ev.append(Event(d.isoformat(), "", "Caged: emprego formal no Brasil", "Ministério do Trabalho", "macro_br", ["BOVA11", "MGLU3", "ITUB4"], "baixo",
                            "Consumo e crédito.", "Só observar.", True))
        if d == _nth_weekday(y, m, 3, 2):
            ev.append(Event(d.isoformat(), "", "Boletim ENSO (El Niño / La Niña)", "NOAA", "clima", ["SLCE3", "SMTO3", "ZS=F", "ELET3"], "baixo",
                            "La Niña = seca no Sul e chuva no Norte; afeta safra e hidrelétricas.", "Agro e energia em prazo de meses."))
        d += timedelta(days=1)
    return ev


def earnings_for(tickers: list[tuple[str, str]], errors: list[str], sleep: float = 0.5) -> list[Event]:
    """Datas de resultado via Yahoo calendarEvents."""
    from .data.market import yahoo_symbol, yahoo_quote_summary
    out = []
    for t, m in tickers:
        try:
            res = yahoo_quote_summary(yahoo_symbol(t, m), "calendarEvents")
            ed = ((res.get("calendarEvents") or {}).get("earnings") or {}).get("earningsDate") or []
            for item in ed[:1]:
                ts = item.get("raw") if isinstance(item, dict) else item
                if ts:
                    dd = datetime.fromtimestamp(ts, tz=timezone.utc).date()
                    out.append(Event(dd.isoformat(), "", f"Resultado trimestral: {t}", "RI / CVM / SEC", "empresas", [t], "alto",
                                     "Maior movimento do trimestre no ativo; vol implícita alta antes, crush depois.",
                                     "Nunca atravessar resultado alavancado; posição normal só com stop; ler release e call.", True))
        except Exception as e:  # noqa: BLE001
            errors.append(f"calendario {t}: {type(e).__name__}: {str(e)[:80]}")
        time.sleep(sleep)
    return out


def build_calendar(tickers: list[tuple[str, str]], days_ahead: int = 35, with_earnings: bool = True,
                   errors: list[str] | None = None) -> list[dict]:
    errors = errors if errors is not None else []
    start, end = date.today(), date.today() + timedelta(days=days_ahead)
    ev = recurring(start, end)
    for row in FIXED_2026:
        if start <= date.fromisoformat(row[0]) <= end:
            ev.append(Event(*row))
    if with_earnings:
        ev += [e for e in earnings_for(tickers, errors) if start <= date.fromisoformat(e.data) <= end]
    seen = set(); out = []
    for e in sorted(ev, key=lambda x: (x.data, x.hora_brt)):
        key = (e.data, e.evento)
        if key not in seen:
            seen.add(key); out.append(asdict(e))
    return out


def events_today_and_tomorrow(cal: list[dict]) -> list[dict]:
    t0, t1 = date.today().isoformat(), (date.today() + timedelta(days=1)).isoformat()
    return [e for e in cal if e["data"] in (t0, t1)]
