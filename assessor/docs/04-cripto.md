# 04. Criptoativos: operar 24/7 com risco controlado

## Por que entra na carteira
- Mercado contínuo (fim de semana, madrugada): cobre os horários que ações não cobrem.
- Baixa correlação parcial com bolsas em alguns regimes; alta correlação em crises de liquidez (não conte com diversificação quando mais precisa).

## Regras específicas
1. O orçamento de risco em **dinheiro** é o mesmo das ações. Como a vol é 3-5x maior, a posição é 3-5x menor.
2. Fim de semana: só com lucro retido (`LeveragePolicy`), nunca com principal.
3. Custódia: exchange só para o que está operando; o resto em carteira própria. Exchange quebra (Mt. Gox, FTX).
4. Nada de alavancagem em perpétuos acima de 2x, e só com stop na própria exchange.
5. Altcoins: apenas top 50 por liquidez, com auditoria, > 1 ano de vida, mcap/FDV > 0,4.

## Métricas (`advisor.crypto`)
- **mcap/FDV**: baixo = muito token ainda vai ser desbloqueado (pressão vendedora programada; checar calendário no DefiLlama/TokenUnlocks).
- **Volume/mcap**: < 1% ilíquido; > 100% suspeito.
- **Fluxo líquido para exchanges**: entrada = intenção de venda; saída = acumulação.
- **Funding rate**: > 0 comprados pagam vendidos. Extremos (z-score > 2) tendem a reverter (`funding_signal`).
- **Open interest / mcap**: alto = cascata de liquidação possível.
- **On-chain BTC/ETH**: MVRV, SOPR, reservas em exchange, endereços ativos, hash rate, dominância.

## Eventos que movem
- Macro: Fed, CPI, liquidez em dólar (cripto é ativo de risco de beta alto).
- ETFs à vista: fluxos diários publicados pelos emissores.
- Halving (BTC), upgrades (ETH), desbloqueios, listagens/deslistagens, hacks (DefiLlama lista em tempo real), ações regulatórias (SEC, CVM).
- Liquidações em cascata: Coinglass mostra mapa de liquidação; movimentos de fim de semana com livro fino são comuns.

## Fontes públicas rápidas
CoinGecko/CMC (preço), Coinglass (derivativos), Glassnode/CryptoQuant (on-chain), DefiLlama (TVL/hacks/unlocks), Etherscan/mempool (carteiras), comunicados oficiais dos protocolos, X/Telegram/Discord públicos (narrativa; peso baixo no sentimento).

## Tributação Brasil
Ganho de capital: isento até R$ 35 mil/mês vendidos em exchanges nacionais; acima, 15-22,5%. Exchanges estrangeiras/autocustódia: regras da Lei 14.754/23 (15% sobre rendimentos no exterior). Declarar todas as posições.
