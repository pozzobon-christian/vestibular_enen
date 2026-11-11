# 02. Manual de opções: do básico ao operacional

Objetivo: operar opções com precisão matemática e disciplina, melhor que o operador médio. Tudo aqui tem implementação em `advisor.options`.

## 1. Conceitos

- **Call**: direito de comprar ao strike. **Put**: direito de vender ao strike.
- **Comprado (titular)** paga prêmio, risco limitado ao prêmio. **Vendido (lançador)** recebe prêmio, risco pode ser ilimitado (call descoberta) ou grande (put).
- **Europeia** só exerce no vencimento (índices na B3, SPX nos EUA). **Americana** exerce a qualquer momento (ações na B3 e nos EUA).
- **Moneyness**: ITM (tem valor intrínseco), ATM, OTM.
- **Prêmio = valor intrínseco + valor extrínseco (tempo + volatilidade).**
- **B3**: calls vencem na 3ª sexta do mês; códigos: letra A-L = call jan-dez, M-X = put jan-dez. EUA: vencimentos semanais, mensais (3ª sexta), LEAPS.

## 2. Precificação

**Black-Scholes-Merton** (`black_scholes`): entradas spot, strike, tempo (anos), taxa livre de risco contínua (Selic/SOFR), vol anual, dividend yield.
- Paridade put-call: `C - P = S·e^(-qT) - K·e^(-rT)`. Se quebrar, há arbitragem ou erro de dado.
- **Binomial CRR** (`binomial_american`) para americanas: put americana vale mais que europeia; call sem dividendos praticamente igual.
- **Vol implícita** (`implied_volatility`): o preço de mercado "contém" uma vol. Comparar IV com vol realizada (histórica) é a base de toda estratégia de volatilidade.

## 3. Gregas (`greeks`)

| Grega | Mede | Como usar |
|---|---|---|
| Delta | Δpreço opção / Δpreço ativo | Exposição direcional; também aproxima prob. de terminar ITM |
| Gamma | Δdelta / Δpreço | Comprado em gamma ganha em movimento; vendido perde. Explode perto do vencimento ATM |
| Theta | Perda por dia | Vendedor recebe, comprador paga. Acelera nos últimos 30 dias |
| Vega | Δpreço / 1pp de vol | Comprar quando IV baixa, vender quando alta |
| Rho | Δpreço / 1pp de juros | Relevante no Brasil (juros altos) e em LEAPS |

Carteira: somar gregas ponderadas por quantidade. Limites de carteira: delta líquido, vega líquido e gamma próximos do vencimento são os três números a vigiar.

## 4. Volatilidade: a verdadeira mercadoria

- **IV rank / IV percentil**: onde a IV atual está no último ano. IV rank > 50: vender prêmio; < 20: comprar prêmio.
- **Skew**: puts OTM têm IV maior (medo de queda). Smile em cripto e eventos.
- **Estrutura a termo**: vencimento curto com IV maior que o longo = evento próximo.
- **Crush pós-evento**: IV cai 30-60% após resultado. Vender straddle antes só com tamanho mínimo e risco definido (iron fly), nunca descoberto.
- **Vol realizada**: `annualized_volatility` dos retornos diários. Edge = IV − RV esperada.

## 5. Estratégias (com implementação)

| Estratégia | Visão | Débito/Crédito | Risco | Função |
|---|---|---|---|---|
| Venda coberta | Lateral/alta leve | Crédito | Queda da ação | `covered_call` |
| Put coberta por caixa | Quer comprar mais barato | Crédito | Ação cai muito | `cash_secured_put` |
| Trava de alta (calls) | Alta moderada | Débito | Limitado | `bull_call_spread` |
| Trava de baixa (puts) | Baixa moderada | Débito | Limitado | `bear_put_spread` |
| Trava de alta (puts) | Alta/lateral, IV alta | Crédito | Limitado | `bull_put_spread` |
| Trava de baixa (calls) | Baixa/lateral, IV alta | Crédito | Limitado | `bear_call_spread` |
| Iron condor | Lateral, IV alta | Crédito | Limitado | `iron_condor` |
| Straddle comprado | Movimento forte | Débito | Prêmio | `long_straddle` |
| Strangle comprado | Movimento forte, mais barato | Débito | Prêmio | `long_strangle` |
| Borboleta | Preço-alvo específico | Débito pequeno | Limitado | `butterfly_call` |
| Collar | Proteger carteira | ~zero | Limita ganho | `collar` |
| Calendário/diagonal | Vol curta > longa | Débito | Limitado | precificar perna longa com BSM |

Cada `Strategy` devolve `summary()`: custo, break-evens, lucro máximo, perda máxima. **Regra**: perda máxima ≤ risco por operação do `RiskBudget`.

## 6. Gestão da operação

- **Entrada**: só com IV rank conhecido e tese escrita (direção + vol + prazo).
- **Tamanho**: perda máxima da estrutura = risco permitido. Para vendas descobertas, não operar (risco indefinido viola o princípio 1).
- **Saída de vendas de prêmio**: zerar com 50% do prêmio capturado ou a 21 dias do vencimento (gamma risk). Stop em 2× o prêmio recebido.
- **Saída de compras**: alvo em 100% ou stop em 50% do prêmio; não deixar virar pó.
- **Rolagem**: rolar só se a tese continua; rolar para receber crédito, nunca pagando para "esperar".
- **Exercício e dividendos (B3/EUA)**: call ITM com dividendo próximo pode ser exercida antes. Puts ITM profundas em juros altos também.
- **Vencimento**: nunca carregar posição vendida ATM para o dia do vencimento sem acompanhamento.

## 7. Brasil: particularidades

- Juros altos tornam calls caras e puts baratas (rho). Venda coberta rende bem em Selic alta.
- Liquidez concentrada em PETR4, VALE3, BOVA11, BBAS3, ITUB4 e poucos mais; spreads largos fora disso.
- Margem de garantia pela B3: títulos públicos e ações aceitos; simular margem antes.
- Tributação: 15% sobre ganho líquido (20% day trade), sem isenção de R$ 20 mil para opções; day trade e swing compensam entre si dentro da categoria. Guardar notas.
- Opções sobre índice (IBOV) e dólar: europeias, liquidação financeira.

## 8. EUA

- Opções sobre ações: 100 ações por contrato; liquidez enorme, spreads de centavos.
- Índices (SPX, NDX): europeias, liquidação em dinheiro, tratamento fiscal 60/40 para residentes nos EUA (consultar sua tributação como não residente).
- 0DTE (vencem no dia): gamma extremo; só com risco definido e tamanho mínimo.
- Margem: Reg T vs. portfolio margin; a corretora cobra manutenção diária.

## 9. Programa de estudo (ordem)

1. Payoffs de todas as estratégias acima à mão e com `Strategy.pnl_curve`.
2. Reproduzir Black-Scholes e gregas; testar paridade.
3. IV rank diário de 10 ativos por 30 dias (planilha).
4. Paper trading: 4 semanas vendendo prêmio com IV rank > 50 e risco definido.
5. Paper trading: 4 semanas comprando vol antes de eventos com IV rank < 20.
6. Revisão escrita de cada semana: o que a tese dizia, o que aconteceu, o que o risco permitiu.
7. Leitura: Natenberg (Option Volatility & Pricing), Hull (Options, Futures and Other Derivatives), Sinclair (Volatility Trading), Taleb (Dynamic Hedging) para avançado.
