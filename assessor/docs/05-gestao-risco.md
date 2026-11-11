# 05. Gestão de risco: margem de erro calculada e acordada

Este é o contrato entre você e o sistema. Nada opera fora dele.

## Orçamento de risco (`RiskBudget`)

| Limite | Padrão | Significado |
|---|---|---|
| Por operação | 1% do capital | Perda se o stop for atingido |
| Por dia | 3% | Atingiu: para o dia |
| Por semana | 6% | Atingiu: para a semana seguinte e escreve revisão |
| Posição máxima | 20% | Nenhum ativo acima disso |
| Tema correlacionado | 40% | Ex.: bancos BR + juros |

Tamanho de posição: `quantidade = (capital × risco%) / |entrada − stop|`, limitado pela posição máxima e pelo caixa. O **stop define o tamanho, não o contrário**.

## Margem de erro
- Um sistema com 50% de acerto e payoff 1,5:1 tem edge positivo, mas sequências de 8 perdas seguidas são **esperadas** (prob. ≈ 0,4% por sequência; em 500 operações, quase certo). O orçamento semanal existe para sobreviver a isso.
- `risk_of_ruin(p, risco, nível)` compara cenários: com 1% por operação e 55% de acerto, a chance de perder metade do capital é desprezível; com 5%, deixa de ser.
- Kelly: usar **meio-Kelly** no máximo (`kelly_fraction`), porque as estimativas de p e b erram.

## Alavancagem só sobre lucro (`LeveragePolicy`)
- Base alavancável = lucro retido (ainda não retirado) × (1 − colchão de 30%).
- Notional máximo = principal + base alavancável × multiplicador (padrão 2x).
- Sem lucro retido: 1:1 sobre o principal. Sempre.

## Ciclo semanal (`WeeklyCycle`)
- Segunda a sexta: opera bolsas (BR 10h-17h, EUA 11h30-18h horário de Brasília) e cripto.
- Sexta após o fechamento: fecha ou protege posições (collar/puts) que atravessam o fim de semana.
- Fim de semana: retira 70% do lucro realizado da semana (configurável); 30% fica como base de alavancagem; cripto só com esse retido.
- Perda semanal ≥ 6%: pausa e revisão escrita obrigatória (o que a tese dizia, o que aconteceu, o que muda).

## Porteiro de ordens (`RiskGate`)
Recusa: ordem sem tese, compra sem stop, risco acima do limite, estouro do limite diário/semanal, posição acima do máximo, alavancagem fora da política. Toda recusa fica registrada.

## Métricas de acompanhamento
Drawdown máximo, Sharpe, Sortino, VaR e CVaR históricos (`advisor.risk.metrics`). Metas iniciais: drawdown máximo < 10%, Sharpe > 1 em paper por 8 semanas antes de real.

## Erros que o sistema impede por construção
- Aumentar posição perdedora ("preço médio") sem nova tese e novo stop.
- Vender opção descoberta.
- Operar resultado com alavancagem.
- "Recuperar" perda do dia aumentando tamanho.
