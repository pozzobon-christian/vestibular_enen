# 12. Como os sinais se cruzam para agir antes da maioria

"Antes de todos" não é saber algo que ninguém sabe. É (1) olhar fontes públicas que a maioria não olha, (2) olhar mais cedo no dia, (3) cruzar camadas que a maioria lê separadas e (4) agir só quando duas camadas independentes concordam. Tudo lícito; a vantagem é velocidade e disciplina.

## As quatro camadas

| Camada | O que coleta | Quando chega | Módulo |
|---|---|---|---|
| Fluxo global | Futuros dos EUA, Ásia, Europa, Brent, minério, dólar, Treasury, VIX, ADRs, IBIT, BTC/ETH | 24h, com destaque para 5h-10h | `monitor morning` |
| Informação | 19 feeds oficiais e de imprensa com sentimento e ativos extraídos; posts de 37 influenciadores e comunidades | tempo real da coleta (a cada 6h; por disparo nos briefings) | `news`, `influencers` |
| Evidência | Estudo de evento (reação histórica a notícia por ativo) e histórico de acerto por influenciador | acumula com o tempo | `signals.events`, `influencers.track_record` |
| Cálculo | Tendência (t-stat, ADX, rompimento), momento, regime de vol, RSI/ATR | fechamento diário | `signals.trend`, `signals.technical` |

## Onde chegamos antes

1. **Madrugada (5h55).** ADRs de Petrobras, Vale e Itaú, o EWZ e os futuros já precificaram a noite 4 horas antes da B3 abrir. Brent às 6h antecipa PETR4 e PRIO3; minério e Hang Seng antecipam VALE3; DXY e Treasury antecipam bancos e BOVA11. Quem olha às 10h está atrasado.
2. **Campanha em fase "início".** Três autores no mesmo ativo em 24h, antes de virar matéria. O sistema vê o pico de menções horas antes da imprensa, e sabe se quem começou tem histórico de acerto ou assinatura de pump.
3. **Feeds oficiais na origem.** CVM, SEC, Fed e Banco Central entram no banco no momento da publicação; o resumo da imprensa vem depois.
4. **Cripto 24/7.** Funding extremo e fluxo para exchanges no fim de semana antecipam a segunda-feira das ações ligadas a cripto (COIN, MSTR, IBIT).

## A regra de cruzamento (o que vira ordem)

Uma ordem exige **duas camadas independentes concordando** e a terceira não contradizendo:

| Combinação | Leitura | Ação |
|---|---|---|
| Fluxo global a favor + tendência a favor | O mundo e o preço dizem o mesmo | Entrada normal, tamanho pelo stop |
| Notícia forte com 2+ fontes + estudo de evento com reação histórica no mesmo sentido | A notícia costuma mover este ativo | Entrada no dia, saída em 1 a 5 dias (horizonte da evidência) |
| Notícia forte + estudo de evento com reação oposta | O mercado "vende a notícia" | Contrarian, tamanho reduzido |
| Campanha "início" + líder com acerto ≥ 55% + tendência não contrária | Boiada começando com quem acerta | Entrada curta, stop 1 ATR |
| Campanha "lotada" ou líder pumper | Chegamos tarde ou é armadilha | Não entrar; se dentro, realizar metade |
| Notícia forte sem histórico (n < 8) | Não sabemos como este ativo reage | Observar, registrar, não operar |
| Tendência forte mas vol 20d > 1,5× vol 100d | Movimento real, mas instável | Metade do tamanho |
| Qualquer sinal com stop fora do orçamento de risco | Não cabe | Recusado pelo `RiskGate` |

Prioridade quando há conflito: evidência medida > cálculo de tendência > fluxo global > opinião de influenciador. Sentimento de rede social sozinho nunca é ordem.

## O ciclo diário

5h55 coleta e briefing global → ordens do dia com condição de abertura → 10h B3 abre, ordem só se a condição for atendida → 17h47 fechamento, stops e resultado → coleta a cada 6h alimenta as campanhas e o estudo de evento → sábado revisão de cripto e influenciadores → sexta revisão escrita da semana.

## O que ainda falta para ficar mais cedo

- Intradiário: cotações de 1 minuto e volume anormal (hoje é diário).
- Fluxo de opções incomum e dark pools (EUA) e posições de insiders (CVM 44 / Form 4).
- Alertas por push ou WhatsApp no momento do sinal, em vez de esperar o briefing.
- X e Reddit ativos (dependem dos segredos no repositório).
- Histórico: o estudo de evento precisa de 8+ casos por ativo; em 3 a 4 semanas de coleta os primeiros ativos passam a operar por notícia.
