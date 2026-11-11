# 07. Roadmap

## Fase 0 (feita): base de cálculo e regras
Risco, opções, fundamentos, FIIs, cripto, fontes, sentimento, livro-razão, ciclo semanal, paper broker, testes.

## Fase 1 (próximas 2-4 semanas): dados reais e observação
- Lista de observação: 15 ações BR, 15 EUA, 10 FIIs, 5 cripto, com ficha fundamentalista preenchida por ativo.
- Coletores agendados: cotações (Stooq), cripto (CoinGecko), RSS de RI/CVM/SEC, funding (Coinglass).
- IV rank diário dos ativos com opções líquidas.
- Relatório diário automático: o que mudou, alertas, sentimento, calendário do dia.

## Fase 2 (4-8 semanas): paper trading
- Conta simulada com o `PaperBroker`, ordens só via `RiskGate`.
- Duas estratégias por vez, no máximo: (a) venda de prêmio com risco definido em IV alta; (b) swing fundamentalista com stop técnico.
- Fechamento semanal com `WeeklyCycle`; revisão escrita toda sexta.
- Critério para avançar: 8 semanas, drawdown < 10%, Sharpe > 1, zero violações de risco.

## Fase 3: conta real, internacional, multi-horário
- Corretora com API e mercados BR + EUA + cripto (ex.: Interactive Brokers para ações/opções globais; exchange regulada para cripto; corretora BR com API para B3). Chaves ficam com você; o sistema recebe só o que precisa.
- Adaptador `Broker` real por corretora; mesma `RiskGate`.
- Operação por janelas: Ásia (madrugada BRT, via futuros/cripto), Europa (manhã), EUA/BR (tarde), cripto (noite e fim de semana, só com lucro retido).
- Começar com 10-20% do capital planejado; subir só após 4 semanas reais sem violação.

## Fase 4: inteligência
- Análise profunda por LLM dos itens filtrados (releases, 8-K, fatos relevantes) com saída estruturada: "muda a tese? sim/não/por quê".
- Backtest de estratégias de opções com dados históricos de IV.
- Modelos de vol (GARCH) para comparar com IV.
- Painel web com posições, gregas de carteira, risco consumido no dia/semana.

## O que não entra, em nenhuma fase
Informação privilegiada, venda descoberta de opções, alavancagem sobre principal, operação sem stop e sem tese.
