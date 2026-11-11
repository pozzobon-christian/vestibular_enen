# 14. O motor de decisão: de onde vem cada número

Nada aqui é caixa-preta. Cada camada tem uma fórmula, um peso e um arquivo. Abaixo, o que entra, como é pesado e onde está.

## 1. Os livros não entram no motor. Eles escreveram as regras do motor

| Regra no código | Livro ou estudo de origem |
|---|---|
| Tamanho = risco permitido ÷ (entrada − stop), nunca pelo entusiasmo (`risk/sizing.py`) | Van Tharp, *Trade Your Way to Financial Freedom*; Schwager, *Market Wizards* |
| Meio-Kelly no máximo; risco de ruína calculado (`kelly_fraction`, `risk_of_ruin`) | Thorp; Gunther, *Axiomas de Zurique*; Lowenstein, *Quando os Gênios Falham* |
| Margem de segurança e score fundamentalista (`fundamentals/analysis.py`) | Graham, *O Investidor Inteligente*; Fisher; Lynch |
| Regime por médias de 50/200 dias e queda da máxima; caixa quando abaixo (`market_regime`) | Faber (2007); Antonacci, *Dual Momentum*; Clenow, *Following the Trend* |
| Seguir tendência com t-stat e ADX, não com opinião (`signals/trend.py`) | Moskowitz, Ooi e Pedersen (2012); Covel, *Trend Following* |
| Peso baixo para sentimento de rede social; notícia só com evidência medida (`signals/events.py`) | Tetlock (2007); Bollen (2011) e suas refutações; Kahneman, *Rápido e Devagar* |
| Boiada em três fases; não ser liquidez de saída (`influencers/herd.py`) | Kindleberger, *Manias, Pânicos e Crashes*; Mackay; Cialdini, *Influência* |
| Máximo de 2 ordens por dia; pausa após perda semanal (`WeeklyCycle`, `RiskGate`) | Barber e Odean (2000); Douglas, *Trading in the Zone* |
| Não comprar "porque caiu muito"; não vender na mínima da virada | Daniel e Moskowitz, *Momentum Crashes* (2016); Taleb, *Iludidos pelo Acaso* |
| Alavancar só lucro, nunca principal (`LeveragePolicy`) | Taleb, *Antifrágil*; Lowenstein |

Quando você lê um livro da biblioteca, o ganho não é "saber mais": é entender por que a regra existe e, se discordar com evidência, mudar a regra no código, não a disciplina no momento da ordem.

## 2. Influenciadores e portais: a equação do sentimento

**Passo 1, o texto vira número** (`signals/sentiment.py`):

`score(texto) = Σ(palavras positivas − palavras negativas, com negação invertendo e intensificador ×1,5) ÷ √(nº de palavras)`, limitado a [−1, 1].

**Passo 2, a fonte pesa** (quem fala importa mais do que o que diz):

| Fonte | Peso |
|---|---|
| Regulador, RI da empresa, banco central | 1,0 |
| Imprensa financeira | 0,7 |
| Analista identificado | 0,6 |
| X | 0,35 |
| Reddit | 0,30 |
| Telegram, Discord | 0,25 |
| Desconhecida | 0,20 |

**Passo 3, o tempo apaga** (`aggregate_sentiment`): cada item vale `peso × 0,5^(idade em horas ÷ 12)`. Uma notícia de 24 horas atrás vale um quarto. O agregado é a média ponderada; o rótulo só vira "positivo" acima de +0,15 e "negativo" abaixo de −0,15.

**Passo 4, o pico de menções** é um sinal separado: `menções na hora de pico ÷ média por hora`. Acima de 3, alguém está empurrando o ativo, e isso alimenta a detecção de campanha.

**Passo 5, o influenciador é julgado pelo histórico, não pelo alcance** (`influencers/track_record.py`): cada chamada é comparada ao retorno em 1, 5 e 20 dias. Sai o acerto por horizonte e a **assinatura de pump** = fração das compras em que o ativo subiu em 1 dia e estava abaixo do preço da chamada em 20 dias. Acima de 0,5, quem segue esse autor é liquidez de saída, e a confiança da campanha cai 0,15 por pumper.

**Passo 6, a campanha e a fase** (`influencers/network.py`, `herd.py`): três ou mais autores, mesmo ativo, mesma direção em 24 horas. Início: até 4 autores e sem pumper, confiança +0,1. Lotada: 8 ou mais autores, alcance acima de 200 mil ou mais de 48 horas. Reversão: preço 7% abaixo do pico ou menções caindo 40%.

**Passo 7, a notícia só opera com evidência** (`signals/events.py`): para cada ativo, o estudo de evento mede o retorno médio em 1 e 5 dias após notícias fortes no passado. Regras: duas ou mais fontes independentes, |score| ≥ 0,25, pelo menos 8 eventos históricos. Reação histórica no mesmo sentido acima de 0,3% vira compra ou venda; sentido oposto vira contrarian; sem histórico, "observar". É isso que impede que um portal ou um influenciador, sozinho, gere ordem.

## 3. A tendência é cálculo, não olho

`signals/trend.py`: regressão linear de ln(preço) nos últimos 60 dias. A direção só existe se |t-stat| ≥ 1; é "significativa" com |t| ≥ 2 (+25 pontos). ADX ≥ 25 soma 20. Preço do lado certo das médias de 50 e 200 dias soma 15 cada. Rompimento de 20 dias soma 15. Momento de 3 meses no mesmo sentido soma 10. Score de 0 a 100. Vol de 20 dias 50% acima da de 100 dias = reduzir tamanho.

## 4. Os análogos são distância em oito dimensões

`signals/analogs.py`: o estado de hoje é um vetor com retornos de 5, 20 e 60 dias, distância das médias de 50 e 200, RSI, razão de volatilidade e queda da máxima de 120 dias. A distância para cada dia do passado é euclidiana ponderada (os retornos de 20 dias e a distância da MM50 pesam 1,5). Os 15 dias mais próximos, com 20 dias de separação entre si, formam a amostra; o que aconteceu 5, 10 e 20 dias depois deles é a evidência: mediana, pior, melhor e % de casos positivos.

## 5. A votação que vira ordem

`monitor.short_ops`: cinco camadas votam a favor, contra ou neutro.

| Camada | A favor quando | Contra quando |
|---|---|---|
| Balanço | score ≥ 60 | score < 40 |
| Análogos | ≥ 65% positivos e mediana > +1% em 20 dias | ≤ 35% positivos e mediana < −1% |
| Notícias | ação "compra" com evidência | ação "venda" com evidência |
| Tendência | alta com score ≥ 50 | baixa com score ≥ 50 |
| Intradia | rompimento da faixa de abertura para cima acima do VWAP | para baixo, abaixo do VWAP |

Operação = compra se ≥ 2 a favor e 0 contra; venda se ≥ 2 contra e 0 a favor; senão nada. Stop = 1 ATR, alvo = 2 ATR, razão 2:1, prazo 1 a 5 pregões. Por cima disso, o regime: em modo defensivo não há compra nova em ação sem proteção.

## 6. O porteiro, que ninguém passa

`portfolio/broker.py` (`RiskGate`): recusa ordem sem tese, compra sem stop, risco acima do limite por operação, estouro do limite diário ou semanal, posição acima do máximo, alavancagem fora da política. Tamanho = `(capital × risco%) ÷ |entrada − stop|`. Toda recusa fica registrada.

## 7. O que é heurístico e o que é estatístico (honestidade sobre o motor)

- **Estatístico**: t-stat da tendência, estudo de evento, análogos, histórico de acerto dos influenciadores, VaR e risco de ruína. Dependem de amostra; por isso "observar" é a resposta padrão até haver 8 casos.
- **Heurístico**: os pesos por fonte, os limiares de fase da boiada, os pontos do score fundamentalista e do score de tendência. São transparentes e ajustáveis; foram escolhidos pela literatura acima, não medidos nos seus dados ainda.
- **O que ainda não existe**: um modelo de linguagem lendo cada release (hoje é léxico), calibração dos pesos por backtest nos dados coletados e dados intradiários de volume anormal com mais frequência. Entram quando houver semanas de dados para calibrar.
