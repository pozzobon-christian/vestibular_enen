# 09. Plano: de R$ 500 a R$ 5.000 reinvestindo tudo

## A verdade sobre os números

Multiplicar por 10 não acontece em semanas. Com reinvestimento integral:

| Retorno semanal médio | Semanas até R$ 5.000 |
|---|---|
| 1% | 232 (4,5 anos) |
| 2% | 117 (2,2 anos) |
| 3% | 78 (1,5 ano) |
| 5% | 48 (11 meses) |

Um retorno de 2% ao mês já coloca você acima da maioria dos fundos. Um retorno de 3% **por semana** sustentado seria histórico. O plano abaixo mira a sobrevivência e a consistência; a velocidade vem de aportes novos, não de alavancagem. Com R$ 500, a alavancagem sobre lucro está desligada: não há lucro retido para alavancar.

## Por que R$ 500 muda as regras

- **Opções na B3** exigem estruturas de dezenas de reais de prêmio e os spreads comem a margem; em contas pequenas, a corretagem de exercício e o lote de 100 inviabilizam. Liberadas só a partir de R$ 3.000 (`data/plano.json`).
- **Corretoras internacionais** cobram mínimos (IBKR US$ 1 por ordem, câmbio mínimo US$ 2): em R$ 500 isso é 2% por operação só de custo. EUA só quando o capital passar de R$ 3.000.
- **Ações e FIIs no Brasil** têm corretagem zero nas grandes corretoras e **mercado fracionário** (1 ação). Cripto é fracionária e opera 24/7.

Conclusão: a estratégia inicial é B3 fracionária + BTC/ETH, com custo quase zero.

## Alocação inicial (R$ 500)

| Bloco | Valor | O quê | Como escolher |
|---|---|---|---|
| Ações BR fracionário | R$ 200 | 3 a 4 empresas com score fundamentalista ≥ 60 e sinal técnico favorável | `score_company` + tendência (preço acima da média de 50 dias) |
| FIIs | R$ 100 | 2 FIIs com score ≥ 70 e DY acima do CDI | `fii_score`; rendimentos reinvestidos |
| Cripto | R$ 150 | BTC 70% / ETH 30% | compra por grade: 1/3 hoje, 1/3 em uma semana, 1/3 em queda de 10% |
| Caixa | R$ 50 | reserva para oportunidade de boiada em fase "início" | nunca zera |

## Regras de risco deste estágio (`data/plano.json`)

- Por operação 2%, por dia 4%, por semana 8%: percentuais maiores que o padrão porque R$ 500 não divide em 1%. **Em dinheiro:** R$ 10 por operação, R$ 20 por dia, R$ 40 por semana.
- Posição máxima 25% (R$ 125).
- Retirada semanal: 0% até a meta. Após R$ 5.000, volta a regra de retirar 70% do lucro.
- Perda semanal de 8%: pausa de uma semana e revisão escrita.

## Rotina semanal

- **Domingo à noite:** ler `data/RELATORIO.md` e o painel; escolher no máximo 2 operações da semana com tese e stop escritos em `data/carteira.json`.
- **Dias úteis, 15 minutos:** painel às 9h45 (pré-abertura B3), 17h30 (fechamento), 22h (EUA e cripto).
- **Sexta:** fechar o que não tem tese para o fim de semana; cripto só com o que já é lucro.
- **Métrica que importa:** número de semanas sem violar regra. Lucro vem depois.

## Marcos

| Patrimônio | O que muda |
|---|---|
| R$ 1.000 | passa a usar limites padrão (1% por operação) |
| R$ 3.000 | libera opções com risco definido (travas) e conta nos EUA |
| R$ 5.000 | meta; volta a retirada semanal de 70% do lucro e começa a alavancagem sobre lucro |
