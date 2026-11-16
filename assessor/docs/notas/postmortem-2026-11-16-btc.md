# Post-mortem: compra de BTC sugerida em 11/11/2026

## O que aconteceu
Sugeri a 1ª parcela de BTC (R$ 50) a US$ 73.721 com a tese "capitulação, RSI 34, entrada em grade". Em 5 dias o preço caiu 13% (mínima US$ 64.120). Se executada, o stop de −10% teria sido acionado: perda de R$ 5 (1% do capital), dentro do orçamento, mas evitável.

## O que os motores já diziam naquele dia (medido no banco)
| Camada | Leitura em 11/11 | O que fiz |
|---|---|---|
| Tendência | baixa, score 65, t-stat −3,5, rompimento de baixa de 20 dias | ignorei; tratei como "oportunidade" |
| Estabilização | nenhuma: fechamento abaixo da máxima de 3 dias e abaixo da média de 5 | não verifiquei |
| Proxies de cripto | ETH baixa 100, COIN baixa 85, IBIT −6,8% e MSTR −14% em 5 dias | não cruzei |
| Análogos | 67% positivos em 20 dias, mas com n = 6 (mínimo é 8) | usei como se fosse evidência |
| Votação de duas camadas | 1 a favor (análogos, inválido) e 1 contra (tendência): reprovada | não submeti a ordem à votação |
| Regime | neutro para BTC; defensivo no Ibovespa | — |

## Causa raiz
Erro de processo, não de azar: a ordem de cripto foi escrita à mão a partir de uma narrativa e não passou pelo mesmo cruzamento que eu exigia para ações. RSI 34 não é sobrevenda, "capitulação" não é sinal mensurável, e amostra de 6 análogos não é evidência.

## O que mudou nos motores (16/11)
1. **Porteiro de tese** (`signals/gate.py`): toda ordem, inclusive as escritas no plano, passa pela votação e pelas regras abaixo; o veredito aparece no painel como "aprovada" ou "BLOQUEADA" com os motivos.
2. **Contra a tendência só com estabilização**: fechamento acima da máxima dos 3 dias anteriores e da média de 5 dias (espelho para venda). RSI sozinho nunca autoriza.
3. **Análogos só contam com n ≥ 8**; abaixo disso viram "neutro".
4. **Composto de risco cripto**: IBIT caindo em 5 dias, COIN/MSTR em baixa, BTC na mínima de 20 dias. Dois de três acesos bloqueiam compra sem estabilização.
5. **Regime próprio para cripto** (`market_regime` sobre BTC), além de Ibovespa e S&P.
6. **Stop estrutural**: abaixo da mínima de 5 dias ou 1 ATR, o que for mais largo dentro do orçamento; fim do "−10%" arbitrário.
7. **Cripto entra no cruzamento de operações curtas** com as mesmas cinco camadas, inclusive intradia.

## Teste de regressão
`tests/test_gate.py::test_btc_11_11_would_be_blocked` reproduz os dados de 11/11 e garante que a ordem é bloqueada por três motivos: contra a tendência sem estabilização, risco cripto negativo e votação insuficiente.

## Resultado aplicado hoje
Com os dados de 16/11 o porteiro bloqueia a 1ª parcela de BTC (tendência baixa 85, sem estabilização, composto de risco negativo). A grade fica suspensa até haver estabilização; a alternativa PETR4 e a ordem de WEGE3 passam.
