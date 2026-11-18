# Laboratório de day trade: primeiro veredito (18/11/2026)

## O que foi testado
Cinco teses intradiárias em ações (B3: 10 ativos; EUA: 8 ativos), candles de 15 minutos dos últimos 60 dias, saída obrigatória no fim do pregão, 70% dos dias para teste e 30% fora da amostra, custos de ida e volta incluídos (B3 0,09%; EUA 0,10%). Mais quatro teses em cripto (BTC e ETH, 180 dias, custo 0,15%).

Critérios de aprovação (todos obrigatórios): 100+ operações; expectância de 0,05% por operação depois dos custos; profit factor 1,3 no teste e 1,1 fora da amostra; drawdown até 10%.

## Resultado
| Tese | B3 teste / fora | EUA teste / fora |
|---|---|---|
| Rompimento da faixa de abertura (ORB) | PF 0,90 / 1,09 | 0,53 / 0,60 |
| Reversão ao VWAP | 0,76 / 0,82 | 0,62 / 0,69 |
| Rompimento com volume (momentum) | 0,86 / 1,29 | 0,65 / 1,03 |
| Momentum da última meia hora (Gao et al. 2018) | 0,40 / 0,63 | 0,29 / 0,15 |
| Reversão de gap de abertura | 0,68 / 0,53 | 0,52 / 0,96 |

Cripto: nenhuma tese acima de PF 0,76 em BTC e ETH.

**Nenhuma tese aprovada.** Momentum na B3 foi o mais perto (PF 1,29 fora da amostra), mas perdeu dinheiro no período de teste (PF 0,86): instável, provável ruído.

## Por quê
1. **Custo maior que a vantagem.** Os efeitos documentados na literatura (momentum intradiário, reversão de gap) rendem centésimos de ponto percentual por operação; o custo de ida e volta é de 0,09% a 0,15%. Em contas pequenas o custo come a borda.
2. **15 minutos é lento para day trade.** As teses de rompimento perdem a entrada; dados de 1 minuto ou tick são necessários e não estão disponíveis de graça para a B3.
3. **Evidência brasileira.** Estudo da FGV (Chague, De-Losso e Giovannetti, 2019) com todos os day traders de mini-índice na B3 entre 2013 e 2015: 97% dos que persistiram por mais de 300 dias perderam dinheiro.
4. **IR de 20% sobre o lucro de day trade** na B3 reduz ainda mais a margem de uma tese marginal.

## O que fica funcionando
- `python -m advisor.daytrade lab`: roda todas as teses e grava `data/daytrade/lab.json`.
- Workflow "Laboratorio de day trade": rodar à mão; o robô de papel a cada 15 minutos liga quando houver uma tese aprovada.
- Nenhuma tese vai para papel ou dinheiro real sem passar pelos critérios.

## Próximas teses candidatas (com dado que temos ou podemos obter)
1. Gap da B3 contra o movimento das ADRs na madrugada (Petrobras, Vale, Itaú): explora informação que chega antes da abertura.
2. Swing de 2 a 10 dias em vez de intradiário: custo dilui; o backtest diário já mostrou +5% contra −5% do índice.
3. ORB e momentum apenas em dias de volume anormal ou após notícia com evidência (filtro de contexto).
