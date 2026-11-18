"""Série histórica oficial da B3 (COTAHIST), gratuita, diária, desde 1986.

Layout fixo de 245 posições (documento "SeriesHistoricas_Layout" da B3).
Preços NÃO são ajustados por proventos: ótimo para retornos dentro do mesmo
dia (abertura -> fechamento); para gaps entre dias, os dias de provento são
detectados e excluídos em advisor.cases.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"


@dataclass(frozen=True)
class DailyBar:
    day: str          # AAAA-MM-DD
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume_brl: float
    trades: int


def _px(s: str) -> float:
    return int(s) / 100.0


def parse_line(line: str) -> DailyBar | None:
    """Uma linha do COTAHIST. Só registros de cotação (tipo 01), mercado à vista
    (TPMERC 010), lote padrão (CODBDI 02) ou ETF/FII (CODBDI 12/14)."""
    if len(line) < 245 or line[0:2] != "01":
        return None
    codbdi = line[10:12]
    if codbdi not in ("02", "12", "14") or line[24:27] != "010":
        return None
    d = line[2:10]
    return DailyBar(
        day=f"{d[0:4]}-{d[4:6]}-{d[6:8]}",
        ticker=line[12:24].strip(),
        open=_px(line[56:69]), high=_px(line[69:82]), low=_px(line[82:95]), close=_px(line[108:121]),
        trades=int(line[147:152]), volume_brl=int(line[170:188]) / 100.0,
    )


def parse_cotahist(text: str, tickers: set[str] | None = None) -> list[DailyBar]:
    out = []
    for line in text.splitlines():
        b = parse_line(line)
        if b and (tickers is None or b.ticker in tickers):
            out.append(b)
    return out


def fetch_year(year: int, tickers: set[str], timeout: int = 120) -> list[DailyBar]:
    """Baixa o ZIP anual oficial e devolve só os tickers pedidos."""
    import requests
    r = requests.get(URL.format(year=year), timeout=timeout, headers={"User-Agent": "assessor-investimentos/0.1"}, verify=True)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = z.namelist()[0]
    text = z.read(name).decode("latin-1")
    return parse_cotahist(text, tickers)
