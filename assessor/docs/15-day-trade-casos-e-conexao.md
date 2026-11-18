# 15. Day trade: casos documentados, o que testamos e como conectar à B3

## Parte 1. Casos de sucesso e de fracasso documentados

Separar o que tem evidência do que é história de influenciador. Cada caso diz o mecanismo, quem ganha, e se serve para nós.

| Caso | O que mostra | Quem ganha de fato | Serve para nós? |
|---|---|---|---|
| **Chague, De-Losso e Giovannetti (FGV, 2019)**: todos os day traders de mini-índice da B3, 2013-2015 | 97% dos que persistiram 300+ dias perderam; 1,1% ganhou mais que um salário mínimo por dia | uma minoria com disciplina e custo baixo; e quem vende cursos | sim, como aviso: é o caso-base |
| **Barber, Lee, Liu e Odean (Taiwan, 2014)**: 15 anos, todos os day traders | menos de 1% lucrativo de forma consistente; os consistentes têm escala e custo mínimo | os que têm vantagem de custo e de execução | sim: confirma que custo decide |
| **Renaissance (Medallion), Citadel, Virtu** | ganham todo dia com day trade | robôs de altíssima frequência, colocação junto à bolsa, rebate de taxas, milhares de ativos | não: a vantagem é infraestrutura, não tese |
| **Market making de varejo** | provê liquidez e ganha o spread | quem tem latência baixa | não, com R$ 500 |
| **Momentum intradiário (Gao, Han, Li e Zhou, 2018)** | 1ª meia hora prevê a última meia hora no S&P | fundos com custo quase zero em futuros | **testar no mini-índice**; em ações perdeu por custo |
| **Noite contra dia (Lou, Polk e Skouras, 2019)** | nos EUA, o ganho das ações acontece quase todo de noite; o pregão é próximo de zero | quem carrega posição de um dia para o outro | testamos na B3: ver Parte 2 |
| **Rompimento da faixa de abertura (Crabel, 1990; Zarattini e Aziz, 2023)** | funcionou em futuros de índice por décadas, com filtros de volatilidade | operadores de futuros com custo baixo | **testar no mini-índice com dados de 1 minuto** |
| **Reversão de gap** | gaps grandes tendem a devolver parte | quem filtra por notícia (gap sem notícia reverte, com notícia continua) | testado: ver Parte 2 |
| **Influenciadores de "R$ 1.000 por dia"** | prints de dias bons | o curso e a corretora parceira | não: viés de sobrevivência, sem histórico auditável |

**Três regras que todos os casos de sucesso têm em comum**
1. **Custo mínimo por operação.** Em ações, a ida e volta custa ~0,09%; no mini-índice, ~0,015%. Por isso o day trade profissional na B3 é feito em mini-índice e mini-dólar.
2. **Tese com mecanismo e com amostra grande.** Centenas de operações, testadas fora da amostra.
3. **Risco por operação pequeno e fixo.** Ninguém que sobrevive arrisca mais de 1% a 2% por operação.

## Parte 2. O que testamos com 10 anos de dados oficiais da B3

Fonte: arquivos COTAHIST da B3 (2016-2026), 13 ativos, mais o Ibovespa. Operação: entra na abertura, sai no fechamento, stop pela mínima/máxima do dia. Validação: 2016-2022 descobre, 2023-hoje confirma, e a tese precisa ganhar em 7 de cada 10 anos. Resultado completo em `data/cases/estudo-10-anos.json`.

**Ações (custo 0,09%): nenhuma tese aprovada.**
- **Reversão de gap de alta** foi a mais forte nos 10 anos (2.099 operações, +0,12% por operação, t-stat 2,3), mas **morreu a partir de 2023** (−0,03%). Vantagem que existiu e foi arbitrada.
- **Reversão de gap de baixa** sem stop: fraca até 2022, forte de 2023 para cá (+0,26%). Inconsistente.
- **Comprar depois de queda forte, primeiro dia do mês, sexta-feira**: perdem dinheiro de forma consistente.
- **Seguir gap (continuação)**: perde forte; o mercado brasileiro reverte gaps mais do que continua.

O teste do mini-índice e a decomposição noite contra dia estão no mesmo relatório.

## Parte 3. Como conectar à B3 de verdade

| Caminho | O que dá | Custo | O que precisa |
|---|---|---|---|
| **MetaTrader 5 da corretora** (Rico, Clear, XP, Genial) | cotação em tempo real, histórico de 1 minuto de anos para WIN e WDO, envio de ordem por Python | grátis com conta | computador Windows com MT5 aberto e logado |
| **ProfitDLL (Nelogica)** | tempo real, livro de ofertas, ordens | assinatura mensal | Windows e assinatura |
| **Cedro / brapi tempo real** | cotações via API | pago | chave de API |
| **Feed direto da B3 (UMDF)** | tudo, com latência mínima | contrato institucional | não é para pessoa física |

**O conector MT5 já está escrito** (`advisor/live/mt5.py`): lê cotações, baixa anos de candles de 1 ou 5 minutos do mini-índice (`download_history`), envia ordens em modo papel e só envia ordem real com três travas: `LIVE_TRADING=1` no computador, tese aprovada no laboratório e porteiro de risco aprovado.

**Passos para ligar**
1. Abrir conta numa corretora com MT5 para B3 (a BTG não oferece MT5; Rico, Clear, XP e Genial oferecem). Habilitar day trade em mini-índice.
2. Instalar o MT5 da corretora num computador Windows e deixar logado.
3. `pip install MetaTrader5` e definir MT5_LOGIN, MT5_PASSWORD e MT5_SERVER como variáveis de ambiente (nunca no chat).
4. Conectar esse computador a esta sessão (Remote Control do app Claude). Aí eu baixo 10 anos de candles de 5 minutos do mini-índice, rodo o laboratório com dados intradiários reais e deixo o robô em papel por duas semanas.
5. Só depois, com tese aprovada e papel positivo, um contrato de mini-índice com stop pequeno.

**Aviso de tamanho**: cada ponto do mini-índice vale R$ 0,20. Um stop de 100 pontos custa R$ 20, o dobro do risco por operação do plano atual (R$ 10). Com R$ 500 de capital, o mini-índice só cabe com stops curtos demais para o ruído do ativo. O mais realista é começar em papel e entrar com dinheiro quando o capital permitir stop de 150 a 200 pontos dentro de 2% de risco, ou seja, a partir de ~R$ 1.500 a R$ 2.000.
