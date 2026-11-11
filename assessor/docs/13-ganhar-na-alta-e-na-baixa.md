# 13. Ganhar na alta e na baixa: posicionamento por regime

## O princípio
O mercado tem três regimes e a carteira tem três modos. O sistema calcula o regime todo dia pelo índice (`market_regime`: preço vs médias de 50 e 200 dias, inclinação de 60 dias, queda da máxima de 120 dias, VIX) e o painel mostra o modo em vigor.

| Regime | Modo | O que fazer |
|---|---|---|
| Alta (preço > MM50 > MM200, t ≥ 1) | Ofensivo | Compras normais a favor da tendência; vendas só em ativos com tendência própria de baixa |
| Lateral | Neutro | Metade do tamanho; operações curtas de 1 a 5 pregões; FIIs de papel; caixa ≥ 30% |
| Baixa (preço < MM50 < MM200 ou queda ≥ 15% da máxima) | Defensivo | Sem compras novas em ações; caixa ≥ 50%; proteção em dólar e ouro; vendas a favor da tendência com risco definido; cripto só com lucro retido |

Hoje (11/11/2026): BOVA11 está 8% abaixo da MM50 e 16% abaixo da máxima de 60 dias. Regime de baixa, modo defensivo. É por isso que a alocação de amanhã é parcial e a única compra de ação é a de força relativa (WEGE3).

## Como ganhar na baixa, por estágio de capital

| Capital | Instrumentos de baixa disponíveis | Como |
|---|---|---|
| até R$ 3.000 | Caixa, dólar (ETF IVVB11 ou fundo cambial), ouro (GOLD11), FIIs de papel, venda de ações que já tem antes da queda | A primeira forma de ganhar na baixa é não perder: o stop e o caixa fazem isso. Dólar e ouro sobem quando o Brasil cai |
| R$ 3.000 a 10.000 | Puts na B3 (compra de put = lucro na queda, risco limitado ao prêmio); travas de baixa | Put de BOVA11 ou do ativo em tendência de baixa, 30 a 60 dias, risco = prêmio pago dentro do orçamento |
| acima de R$ 10.000 | Venda a descoberto via aluguel (BTC: Banco de Títulos da B3); vendas de perpétuos em cripto na Bybit; opções nos EUA | Short com stop obrigatório e tamanho pelo risco; nunca contra tendência de alta |

Regras para operar vendido: só a favor do regime e da tendência própria do ativo (score ≥ 50 de baixa); stop acima da máxima recente; alvo 2x o risco; tamanho pelo `RiskBudget`; nunca em ativo com short interest alto e float pequeno (risco de squeeze); nunca atravessar resultado vendido.

## Estudos que fundamentam (todos públicos)
1. **Moskowitz, Ooi e Pedersen, "Time Series Momentum" (2012).** Seguir a tendência de 12 meses em 58 mercados gera retorno em altas e baixas; é a base do modo defensivo.
2. **Jegadeesh e Titman, "Returns to Buying Winners and Selling Losers" (1993).** Momentum de 3 a 12 meses: comprar os que subiram, vender os que caíram.
3. **Asness, Moskowitz e Pedersen, "Value and Momentum Everywhere" (2013).** Combinar valor e momento reduz as quedas da carteira.
4. **Faber, "A Quantitative Approach to Tactical Asset Allocation" (2007).** Regra simples: acima da média de 10 meses compra, abaixo vai para caixa; evita as grandes quedas de 1929, 2000 e 2008.
5. **Antonacci, "Dual Momentum" (2014).** Momento absoluto e relativo: sair para renda fixa quando o ativo perde do caixa.
6. **Fama e French (1992, 2015).** Fatores de valor, tamanho, lucratividade e investimento: o que explica retorno no longo prazo.
7. **Lo e MacKinlay, "A Non-Random Walk Down Wall Street" (1999).** Evidência de previsibilidade de curto prazo.
8. **Daniel e Moskowitz, "Momentum Crashes" (2016).** Quando o momentum quebra: após quedas fortes, na virada; por isso o modo defensivo não vende na mínima.
9. **Hong e Stein, "Bad News Travels Slowly" (2000)** e **Tetlock, "Giving Content to Investor Sentiment" (2007).** Notícia negativa e sentimento de mídia têm efeito mensurável e com atraso: base do estudo de evento.
10. **Barber e Odean, "Trading Is Hazardous to Your Wealth" (2000).** Quem opera demais perde; limite de 2 ordens por dia vem daqui.
11. **Bollen, Mao e Zeng, "Twitter Mood Predicts the Stock Market" (2011)** e críticas posteriores: sentimento de rede social tem sinal fraco e instável; por isso peso baixo.

## Livros para a baixa
1. **Following the Trend**, Andreas Clenow. Sistema de tendência completo, comprado e vendido, com regras.
2. **Trend Following**, Michael Covel. Quem ganhou nas quedas de 1987, 2000 e 2008 e como.
3. **Dual Momentum Investing**, Gary Antonacci. Regra de troca entre risco e caixa.
4. **The Art of Short Selling**, Kathryn Staley. Como identificar empresa que vai cair: contabilidade, governança, promoção.
5. **Short Selling: Strategies, Risks and Rewards**, Frank Fabozzi (org.). O mecanismo e os riscos (squeeze, aluguel).
6. **A Grande Aposta** (*The Big Short*), Michael Lewis. Tese de baixa construída com dados públicos e paciência.
7. **Quando os Gênios Falham**, Roger Lowenstein. Alavancagem mata até os melhores: por que o principal nunca alavanca.
8. **Hedge Fund Market Wizards**, Jack Schwager. Operadores que ganham nos dois lados e como pensam o risco.
9. **Trading in the Zone**, Mark Douglas. A cabeça para aceitar o stop e operar vendido sem torcer.
10. **The Little Book of Market Wizards / Reminiscences** já estão na biblioteca geral; reler o capítulo de 1929.

## O que o sistema faz com isso
- `market_regime` define o modo; o painel mostra; os briefings respeitam.
- Operações curtas já geram "venda" quando duas camadas apontam baixa (vendas executáveis hoje só via puts após R$ 3.000 ou em ativos que já estão na carteira).
- Em modo defensivo, o briefing das 6h propõe proteção (dólar/ouro) antes de qualquer compra.
