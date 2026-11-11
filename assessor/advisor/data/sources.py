"""Catálogo de fontes de informação.

Dois grupos:
- oficiais: reguladores, bolsas, relações com investidores, bancos centrais.
- alternativas: fóruns públicos, redes sociais, on-chain, dados de posicionamento.

Regra legal (não negociável): só usamos informação PÚBLICA. Antecipar o mercado
aqui significa reagir mais rápido e melhor a informação pública, nunca operar
com informação privilegiada (crime: Lei 6.385/76 art. 27-D no Brasil;
Securities Exchange Act Rule 10b-5 nos EUA).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str
    kind: str            # "oficial" | "alternativa"
    market: str          # "BR" | "US" | "global" | "cripto"
    url: str
    what: str
    access: str          # "web" | "api" | "rss" | "feed"
    latency: str         # quão cedo a informação aparece aqui


SOURCES: list[Source] = [
    # ---- Brasil, oficiais
    Source("CVM - Fatos relevantes e comunicados", "oficial", "BR",
           "https://www.gov.br/cvm", "fatos relevantes, ITR/DFP, formulários de referência", "web/feed", "tempo real (obrigação legal)"),
    Source("B3 - Notícias e dados de mercado", "oficial", "BR",
           "https://www.b3.com.br", "cotações, opções (séries, vencimentos), aluguel, leilões", "web/api", "tempo real / fechamento"),
    Source("Banco Central - Focus, Copom, SGS", "oficial", "BR",
           "https://www.bcb.gov.br", "Selic, boletim Focus, atas, séries temporais (API SGS)", "api", "calendário oficial"),
    Source("IBGE - IPCA, PIB, PNAD", "oficial", "BR", "https://www.ibge.gov.br", "macro", "api", "calendário oficial"),
    Source("RI das empresas (site + webcasts)", "oficial", "BR", "varia", "releases, guidance, calls de resultado", "web/rss", "tempo real"),
    Source("Fundos.net (CVM) para FIIs", "oficial", "BR",
           "https://fnet.bmfbovespa.com.br", "relatórios gerenciais, informes mensais, assembleias", "web", "mensal"),
    # ---- EUA, oficiais
    Source("SEC EDGAR", "oficial", "US", "https://www.sec.gov/edgar", "10-K, 10-Q, 8-K, 13F (posições de grandes gestores), Form 4 (insiders)", "api/rss", "tempo real"),
    Source("Federal Reserve", "oficial", "US", "https://www.federalreserve.gov", "FOMC, atas, discursos, dot plot", "web/rss", "calendário"),
    Source("BLS / BEA", "oficial", "US", "https://www.bls.gov", "payroll, CPI, PIB", "api", "calendário"),
    Source("CBOE", "oficial", "US", "https://www.cboe.com", "VIX, put/call ratio, volumes de opções", "web", "diário"),
    Source("CFTC - COT report", "oficial", "US", "https://www.cftc.gov", "posicionamento de especuladores e hedgers em futuros", "web", "semanal (sexta)"),
    Source("Nasdaq/NYSE - calendários", "oficial", "US", "https://www.nasdaq.com", "earnings, IPOs, dividendos, halts", "web", "diário"),
    # ---- global
    Source("ECB, BoJ, BoE, PBoC", "oficial", "global", "varia", "política monetária que move câmbio e risco global", "web", "calendário"),
    Source("Calendário econômico (Investing/TradingEconomics)", "alternativa", "global",
           "https://tradingeconomics.com/calendar", "agregador de indicadores e consenso", "web", "tempo real"),
    # ---- cripto
    Source("CoinGecko / CoinMarketCap", "alternativa", "cripto", "https://www.coingecko.com", "preços, mcap, volume, supply", "api", "tempo real"),
    Source("Glassnode / CryptoQuant / Dune", "alternativa", "cripto", "varia", "on-chain: fluxos de exchange, HODL waves, SOPR, MVRV", "api/web", "horária/diária"),
    Source("Coinglass", "alternativa", "cripto", "https://www.coinglass.com", "funding, open interest, liquidações, long/short ratio", "web", "tempo real"),
    Source("DefiLlama", "alternativa", "cripto", "https://defillama.com", "TVL, hacks, desbloqueios de tokens", "api", "tempo real"),
    Source("Etherscan / mempool.space", "alternativa", "cripto", "varia", "transações de baleias, carteiras rotuladas", "api", "tempo real"),
    Source("Comunicados oficiais de exchanges/protocolos", "oficial", "cripto", "varia", "listagens, deslistagens, incidentes, upgrades", "web/rss", "tempo real"),
    # ---- mídias e fluxo de sentimento (públicas)
    Source("X/Twitter (contas de analistas, empresas, reguladores)", "alternativa", "global", "https://x.com", "narrativas em formação, reação a eventos", "api", "tempo real"),
    Source("Reddit (r/wallstreetbets, r/investimentos, r/CryptoCurrency)", "alternativa", "global", "https://www.reddit.com", "sentimento de varejo, squeezes, memes", "api", "tempo real"),
    Source("Telegram/Discord públicos", "alternativa", "cripto", "varia", "narrativas de altcoins, alertas de baleias", "bot", "tempo real"),
    Source("StockTwits", "alternativa", "US", "https://stocktwits.com", "sentimento por ticker", "api", "tempo real"),
    Source("Google Trends", "alternativa", "global", "https://trends.google.com", "interesse de busca (topo de euforia)", "web", "diário"),
    Source("Dark pools / FINRA ATS data", "alternativa", "US", "https://otctransparency.finra.org", "volume em dark pools por ticker (dados públicos, semanais)", "web", "semanal"),
    Source("Fluxo de opções incomum (unusual options activity)", "alternativa", "US", "varia", "grandes apostas em opções, públicas por consolidated tape", "api", "tempo real"),
    Source("Ações de insiders (Form 4 / CVM 44)", "oficial", "global", "varia", "compras e vendas DECLARADAS de executivos: informação pública e legal", "feed", "até 2 dias úteis"),
]


def list_sources(kind: str | None = None, market: str | None = None) -> list[Source]:
    out = SOURCES
    if kind:
        out = [s for s in out if s.kind == kind]
    if market:
        out = [s for s in out if s.market in (market, "global")]
    return out
