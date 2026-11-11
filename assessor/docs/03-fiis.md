# 03. Fundos imobiliários (FIIs) e REITs

## Tipos
- **Tijolo**: logística, lajes corporativas, shoppings, renda urbana, hotéis, hospitais. Risco: vacância, inadimplência, ciclo imobiliário.
- **Papel**: CRIs indexados a CDI ou IPCA. Risco: crédito do devedor, marcação a mercado, pré-pagamento.
- **FoF**: fundos de fundos. Dupla camada de taxa; gestor compra outros FIIs com desconto.
- **Desenvolvimento**: obra; risco maior e renda só no fim.
- **REITs (EUA)**: setores adicionais (data centers, torres, self storage, saúde). Dividendos tributados a 30% na fonte para brasileiro sem acordo.

## Métricas (`advisor.fiis`)
- **P/VP**: < 0,95 pode ser oportunidade ou problema; verificar o motivo.
- **DY 12m vs. renda fixa**: spread positivo de 2-4 p.p. sobre CDI/NTN-B é razoável para tijolo.
- **Vacância física e financeira**: > 25% é sinal vermelho, salvo tese de retomada.
- **Concentração de inquilino/imóvel**: > 40% em um inquilino = risco de evento único.
- **Prazo médio dos contratos** e tipo (típico vs. atípico).
- **Alavancagem**: FIIs raramente devem passar de 25% dos ativos.
- **Liquidez**: < R$ 500 mil/dia dificulta sair.
- **Taxas**: ADM + gestão + performance; FoF soma as camadas.
- **Cap rate** (tijolo): NOI / valor dos imóveis; comparar com NTN-B + prêmio.

## Fontes
- Relatório gerencial mensal (site do gestor), informe mensal e trimestral (Fundos.net/CVM), assembleias (emissões, mudanças de taxa).
- Laudos de avaliação anuais: o VP depende deles; ler as premissas (cap rate usado).

## Estratégia de renda
- Carteira-núcleo: 8-15 FIIs, nenhum > 12%, segmentos diversificados, 30-40% em papel para suavizar.
- Reinvestir rendimentos nos meses de pagamento; comprar emissões só com desconto real ao mercado.
- Isenção de IR nos rendimentos para PF (condições: fundo com ≥ 100 cotistas, cotista < 10%). Ganho de capital: 20%.

## Alertas automáticos
`fii_score` devolve a lista de alertas (vacância, dependência de inquilino, DY abaixo da renda fixa, liquidez, contratos curtos). Nenhum FII com ≥ 3 alertas entra na carteira-núcleo.
