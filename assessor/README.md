# Assessor de Investimentos: ações, opções, FIIs e cripto

Sistema de apoio à decisão e execução com **gestão de risco obrigatória**.
Nenhuma ordem chega à corretora sem passar pelo porteiro de risco (`RiskGate`).

## O que já existe

| Módulo | O que faz |
|---|---|
| `advisor.risk` | Orçamento de risco acordado, tamanho de posição por stop, Kelly fracionado, risco de ruína, alavancagem **somente sobre lucro**, drawdown, Sharpe, VaR/CVaR |
| `advisor.options` | Black-Scholes-Merton, gregas, vol implícita, binomial (americanas), 11 estratégias com payoff, break-evens, lucro/perda máximos |
| `advisor.fundamentals` | Múltiplos (P/L, EV/EBITDA, ROIC, FCF yield...), score transparente 0-100 com alertas, DCF, número de Graham |
| `advisor.fiis` | Métricas e score de FIIs/REITs: P/VP, DY vs. renda fixa, vacância, concentração, alavancagem, liquidez |
| `advisor.crypto` | Métricas de mercado/on-chain, flags de risco (FDV, fluxo p/ exchanges, funding, auditoria), sinal contrarian de funding |
| `advisor.data` | Catálogo de 28 fontes (oficiais e alternativas) e conectores: Stooq (cotações), CoinGecko, RSS |
| `advisor.signals` | Sentimento por léxico PT/EN ponderado por fonte e tempo, detector de pico de menções, indicadores técnicos |
| `advisor.portfolio` | Livro-razão auditável (JSONL), ciclo semanal com retirada de lucro, corretora simulada (paper) |
| `docs/` | Material de estudo: fundamentos, manual de opções, FIIs, cripto, risco, fontes, roadmap |

## Rodar

```bash
cd assessor
pip install -e ".[dev]"
python -m pytest -q
python -m advisor.cli size --capital 100000 --entry 30 --stop 28.5
python -m advisor.cli option --spot 30 --strike 32 --days 30 --rate 0.11 --vol 0.35 --type call
python -m advisor.cli iv --price 0.9 --spot 30 --strike 32 --days 30 --rate 0.11
python -m advisor.cli strategy --name bull_call_spread --args 30,1.5,33,0.5
python -m advisor.cli sources --kind oficial --market BR
python -m advisor.cli week --start 100000 --end 103500
```

## Princípios (não negociáveis)

1. **Margem de erro calculada e acordada antes.** `RiskBudget` define o máximo por operação, dia e semana. O sistema recusa o que ultrapassar.
2. **Alavancagem só sobre lucro.** `LeveragePolicy` permite alavancar apenas o lucro retido, com colchão; o principal opera 1:1.
3. **Só informação pública.** Monitoramos canais oficiais e mídias alternativas públicas para reagir mais rápido. Operar com informação privilegiada é crime e não entra aqui. Ver `docs/06-fontes-de-informacao.md`.
4. **Tudo registrado.** Toda operação tem tese, stop e risco gravados no livro-razão.
5. **Paper antes de real.** Nenhuma estratégia vai para conta real sem 4 semanas de paper trading com resultado documentado.

## Expectativas honestas

Nenhum sistema "sabe melhor que qualquer humano" de forma garantida. O que é possível e é o alvo aqui: disciplina perfeita de risco, cobertura de informação mais ampla e rápida que uma pessoa consegue sozinha, e precificação de opções sem erro de conta. Lucro consistente vem da combinação disso com paciência. Ver `docs/07-roadmap.md` para as etapas.
