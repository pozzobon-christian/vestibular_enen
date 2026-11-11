# 06. Fontes de informação: oficiais e alternativas

Objetivo: ver antes e reagir melhor. Antecipar o mercado significa **processar informação pública mais rápido e com mais contexto**, nunca usar informação privilegiada.

## Linha legal (inegociável)
- Brasil: uso de informação relevante não divulgada é crime (Lei 6.385/76, art. 27-D), com pena de prisão e multa; a CVM monitora padrões de negociação antes de fatos relevantes.
- EUA: Rule 10b-5; a SEC processa inclusive quem recebe a dica ("tippee").
- Grupos pagos que vendem "informação antecipada" são, na melhor hipótese, fraude; na pior, prova em processo. Não entram no sistema.
- Vazamentos em fóruns anônimos não são "edge": são ruído ou crime.

## Camada 1: oficiais (peso 1,0 no sentimento)
CVM (fatos relevantes), B3, Banco Central (Focus, Copom, SGS), IBGE, RI das empresas, Fundos.net (FIIs), SEC EDGAR (10-K/10-Q/8-K/13F/Form 4), Federal Reserve, BLS/BEA, CBOE (VIX, put/call), CFTC (COT), bancos centrais globais, comunicados de exchanges e protocolos.

## Camada 2: dados públicos "não óbvios" (o que a maioria não lê)
- **Form 4 / CVM 44**: compras de insiders declaradas. Legal, público e preditivo em agregado.
- **13F**: posições trimestrais de grandes gestores (45 dias de atraso).
- **COT**: posicionamento de especuladores em futuros (extremos revertem).
- **FINRA ATS**: volume em dark pools por ticker, semanal.
- **Fluxo incomum de opções**: grandes prêmios OTM de curto prazo via fita consolidada.
- **Desbloqueios de tokens, hacks, TVL** (DefiLlama), **funding/OI/liquidações** (Coinglass), **fluxos de exchange** (Glassnode/CryptoQuant), **ETF flows** diários.
- **Google Trends** e volume de buscas: topo de euforia de varejo.

## Camada 3: mídias alternativas públicas (peso 0,2-0,35)
X/Twitter, Reddit, StockTwits, Telegram/Discord públicos. Uso: detectar **pico anormal de menções** (`aggregate_sentiment.spike_ratio > 3`) e narrativa em formação. Nunca como tese isolada: 80% é ruído, mas squeezes e manias começam ali.

## Pipeline (ver roadmap)
1. Coletores por fonte (RSS/API) gravam itens brutos com timestamp.
2. Sentimento por léxico filtra e detecta picos.
3. Itens filtrados vão para análise profunda (LLM) com a pergunta: "isto muda a tese de algum ativo da carteira ou da lista de observação?"
4. Alerta com proposta de ação dentro do `RiskBudget`. Decisão final humana até o sistema provar resultado em paper.

Catálogo completo: `python -m advisor.cli sources`.
