# 10. Corretoras escolhidas e setup de casa

## Corretoras: decisão

| Mercado | Principal | Reserva | Quando abrir |
|---|---|---|---|
| B3 (ações, FIIs, opções) | **BTG Pactual Digital** (corretagem zero, R$ 1 por exercício de opção) | **Rico** (MetaTrader 5, para automação futura) | Hoje. Ativa em horas |
| Cripto em reais | **Mercado Bitcoin** (pediu licença no BC, API pública) | **Foxbit** | Hoje. Ativa em minutos |
| Cripto global e derivativos | **OKX** ou **Bybit** (na lista de pedidos do BC, API madura) | | Após conferir a lista do Banco Central |
| EUA (ações e opções) | **Interactive Brokers** (API, US$ 0,65 por contrato) | **tastytrade** (interface de opções) | Quando o capital passar de R$ 3.000 |

Pontos a confirmar antes de operar: se a Rico mantém MT5 com opções; se Binance protocolou pedido no BC; tabela de taxas oficial de cada uma. Tributação: contas no exterior entram na declaração e o ganho é tributado entre 15% e 22,5%; cripto segue a Lei 14.754/23.

## Setup de casa

### Hardware
- **Computador:** qualquer notebook dos últimos 5 anos com 8 GB de RAM resolve. Não é preciso máquina cara; o sistema roda no GitHub.
- **Telas:** 2 monitores é o ponto ideal. Esquerda: painel (`dashboard/index.html`) + corretora. Direita: gráfico do ativo da semana (TradingView grátis) + notícias.
- **Celular:** notificações do GitHub (workflow falhou) e da corretora (ordens executadas, stop).
- **Internet:** conexão com cabo quando for enviar ordem; 4G como reserva.
- **No-break ou bateria:** evita ficar preso em posição durante uma queda de luz.

### Software (tudo gratuito)
1. **Painel:** abra `assessor/dashboard/index.html` no navegador; ele lê `data/dashboard-data.json` da branch no GitHub e atualiza sozinho a cada 10 minutos. Após o merge em `main`, fica publicado no GitHub Pages.
2. **Gráficos:** TradingView (plano grátis) com watchlist igual à `data/watchlist.json`.
3. **Corretoras:** app + home broker web. Alertas de preço na própria corretora.
4. **Calendário:** Google Agenda com os eventos da semana: Copom, FOMC, IPCA, payroll, resultados dos ativos em carteira, vencimento de opções (3ª sexta).
5. **Registro:** `data/carteira.json` é o diário de operações; cada linha tem tese e stop. Sem isso, o painel não reconhece a operação.
6. **Telegram/WhatsApp:** canal próprio só para alertas (próxima etapa: o monitor envia resumo).

### Rotina de tela (15 minutos, 3 vezes ao dia)
- 9h45: painel, notícias oficiais, campanhas em fase "início", ordens do dia com stop.
- 17h30: fechamento B3, revisar stops, registrar operações em `carteira.json`.
- 22h: EUA e cripto; nada de ordem nova depois das 23h.

### O que não fazer
- Operar pelo celular na rua sem stop já definido.
- Seguir alerta de grupo pago.
- Mudar regra de risco no meio da semana.
