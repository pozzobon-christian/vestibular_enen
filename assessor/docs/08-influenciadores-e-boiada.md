# 08. Influenciadores, redes e movimentos de boiada

Objetivo: saber **quem** move preço, **com quem** posta junto, **quando** uma campanha começa e **em que fase** ela está, para entrar cedo, sair antes da multidão e, quando fizer sentido, operar a reversão. Implementação em `advisor.influencers`.

## Como funciona

1. **Registro** (`InfluencerRegistry`): você cadastra perfis públicos (X, YouTube, Instagram, Telegram, Reddit, TikTok, podcasts), país, foco, grupos **declarados** e afiliações divulgadas (casa de análise, corretora, projeto cripto). Começa vazio e é seu; nada é afirmado sobre ninguém sem dado.
2. **Coleta** (`collectors`): Reddit público e canais abertos do Telegram sem chave; X via API v2 (token seu); YouTube via RSS do canal; StockTwits por ticker. Instagram/TikTok só por exportação manual para o JSONL de posts.
3. **Leitura do post** (`Post`): extrai ativos (PETR4, HGLG11, $AAPL, bitcoin) e direção (compra, venda, neutro) por léxico PT/EN com negação e emojis.
4. **Campanhas** (`detect_campaigns`): N autores distintos, mesmo ativo, mesma direção, dentro de 24h. Registra o líder (primeiro post), a ordem dos seguidores, o atraso de cada um e o alcance total.
5. **Rede** (`CoMentionGraph`, `clusters`): dois autores se ligam quando aparecem na mesma campanha. Peso 2 ou mais em campanhas diferentes revela **grupos que apostam juntos**, declarados ou não. `leaders()` mostra quem costuma postar antes dos outros: a origem das campanhas.
6. **Histórico** (`evaluate_calls`, `influencer_stats`): cada chamada é comparada ao retorno do ativo em 1, 5 e 20 dias. Sai o acerto por horizonte, o retorno médio e a **assinatura de pump-and-dump**: fração das compras em que o ativo sobe no dia e está abaixo do preço da chamada em 20 dias. Acima de 0,5, quem segue esse autor é liquidez de saída.
7. **Sinal de boiada** (`herd_signal`): classifica a campanha em fase e devolve a ação, a confiança e a dica de stop.

## As três fases e o que fazer

| Fase | Como reconhecer | Ação |
|---|---|---|
| Início | Até 4 autores, campanha com poucas horas, líderes com histórico bom, sem pumpers | Entrar a favor, tamanho pelo `RiskBudget`, stop na mínima do candle do primeiro post, máximo 1x ATR |
| Lotada | 8+ autores, alcance alto, mais de 48h, seguidores de baixo histórico chegando, pico de menções | Não entrar. Se dentro: realizar metade, stop no custo |
| Reversão | Preço 7% abaixo da máxima do pico ou menções caindo 40%; líderes sumiram ou viraram | Contra a boiada com risco definido (put, trava de baixa) ou ficar fora. Campanha de pumpers tende a devolver tudo |

Campanha iniciada por pumper conhecido: só scalp com alvo em horas, nunca carregar posição. A confiança do sinal cai com cada pumper e sobe com cada autor de histórico bom (acerto 5d ≥ 55% em 10+ chamadas).

## Brasil: o que observar

- Influenciadores de "small caps" e "ações baratas": campanhas quase sempre em papéis de baixa liquidez, onde poucos posts movem preço. Assinatura de pump mais frequente.
- Lives e cortes no YouTube/TikTok chegam com atraso de horas em relação ao X e ao Telegram: a ordem temporal mostra onde a campanha nasce.
- Analistas registrados na CVM têm regras de disclosure (Resolução CVM 20); quem não é registrado e recomenda ativo sem informar conflito está em infração, e o alcance costuma ser maior justamente por isso.
- FIIs: campanhas em emissões e em "descontos sobre VP" costumam coincidir com ofertas de corretoras.

## Global

- Cripto: campanhas nascem em Telegram/Discord/X, com cashtags e emojis; influenciadores pagos por projetos (ver afiliações). Funding e open interest confirmam se a boiada já está alavancada (ver cripto, `funding_signal`).
- EUA: WallStreetBets e X; fluxo incomum de opções confirma quando a campanha virou posição real. Squeezes exigem float pequeno e short interest alto.

## Linha legal

- Monitorar e operar sobre posts públicos é lícito.
- Organizar ou participar de campanha coordenada de compra para vender no topo é manipulação de mercado (Lei 6.385 art. 27-C; nos EUA, Securities Exchange Act §9 e 10b-5). O sistema detecta e explora o movimento; **nunca** publica, incentiva ou coordena.
- Promover ativo sem revelar pagamento é infração do promotor (CVM Res. 20; SEC §17(b)). Vale como indicador de risco, não como modelo.

## Uso

```bash
# posts.jsonl: {"author":"@x","platform":"x","ts":"2025-03-03T12:00:00+00:00","text":"...","engagement":123}
python -m advisor.cli herd --posts posts.jsonl --window 24 --min-authors 3 --stats stats.json
```

`stats.json` é a saída de `influencer_stats` (acerto e assinatura de pump por autor), recalculada semanalmente com preços reais.

## Próximos passos
1. Cadastrar os 30 a 50 perfis mais influentes do Brasil e os 20 globais que você já acompanha, com grupos declarados.
2. Rodar a coleta por 4 semanas antes de operar: a rede e o histórico só valem com dados.
3. Confrontar os clusters descobertos com os grupos declarados: a diferença entre os dois é a informação mais valiosa.

## Monitoramento contínuo e armazenamento

- **Cadastro inicial:** `data/influencers.json` com 37 entradas (22 BR, 15 globais) vindas dos rankings de 2026 (iBest, Usepora, Anbima Finfluence, HiveInfluence, Coinbound, Favikon, Bullish Bears). Handles de YouTube são resolvidos para channel_id em tempo de coleta; os marcados "a confirmar" devem ser conferidos na plataforma.
- **Watchlist de preços:** `data/watchlist.json` (BR, US, cripto) alimenta o cruzamento chamada × retorno.
- **Banco:** `data/monitor.db` (SQLite) com tabelas posts, prices, campaigns, herd_signals, influencer_stats e runs. Exportações em `data/exports/*.jsonl` e relatório em `data/relatorio.json`, todos versionados no git a cada execução.
- **Agendamento:** workflow `monitor.yml` roda a cada 6 horas. O cron do GitHub só dispara na branch padrão; até o merge, rodar à mão por `workflow_dispatch`.
- **X/Twitter:** exige o segredo `X_BEARER_TOKEN` no repositório; sem ele, as contas do X ficam sem coleta e os demais seguem.
