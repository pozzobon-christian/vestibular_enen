# 01. Fundamentos: conhecer a empresa antes de operar

## Checklist de conhecimento de uma empresa (obrigatório antes da 1ª ordem)

1. **O que ela vende e para quem.** Segmentos de receita, geografia, sazonalidade.
2. **Como ganha dinheiro.** Margem bruta, EBITDA e líquida nos últimos 5 anos; tendência.
3. **Vantagem competitiva (moat).** Custo, marca, rede, regulação, switching cost. Se não há, é commodity: só vale a preço de commodity.
4. **Capital.** ROIC vs. custo de capital. Empresa que investe abaixo do custo de capital destrói valor mesmo crescendo.
5. **Dívida.** Dívida líquida/EBITDA, perfil de vencimento, moeda, covenants.
6. **Caixa.** Lucro vira caixa? FCO/Lucro líquido > 0,8 é saudável. FCF depois de capex de manutenção.
7. **Alocação de capital.** Dividendos, recompras, M&A: o histórico mostra se a gestão respeita o acionista.
8. **Governança.** Controlador, tag along, partes relacionadas, remuneração, auditoria com ressalva.
9. **Riscos listados no Formulário de Referência (CVM) / Item 1A do 10-K (SEC).** Ler. Sempre.
10. **Catalisadores e calendário.** Resultados, vencimento de opções, assembleias, decisões regulatórias.

## Múltiplos e como ler

| Múltiplo | Fórmula | Uso | Armadilha |
|---|---|---|---|
| P/L | Preço / LPA | Rapidez | Lucro não recorrente distorce |
| EV/EBITDA | (Mcap + dívida - caixa) / EBITDA | Compara empresas com dívidas diferentes | EBITDA ignora capex pesado |
| P/VP | Preço / VPA | Bancos, seguradoras, FIIs | Ativos intangíveis não aparecem |
| FCF yield | FCF / Mcap | O que realmente sobra | Capex de crescimento vs. manutenção |
| ROIC | NOPAT / capital investido | Qualidade | Capital investido mal medido |
| Dívida líq./EBITDA | | Segurança | Setores cíclicos: EBITDA some na baixa |

Implementação: `advisor.fundamentals.ratios` e `score_company` (regras legíveis, 0-100).

## Valuation

- **DCF**: projeta FCF, desconta pelo WACC, adiciona perpetuidade. Sensível a premissas: sempre fazer 3 cenários (base, pessimista, otimista) e operar só se o preço estiver abaixo do pessimista com margem.
- **Múltiplos comparáveis**: pares do setor; ajustar por crescimento e ROIC.
- **Número de Graham**: `sqrt(22,5 × LPA × VPA)`; filtro rápido para value.
- **Margem de segurança**: comprar com ≥ 30% de desconto sobre o valor justo do cenário base.

## Onde ler os documentos

- Brasil: CVM (ITR, DFP, Formulário de Referência), site de RI, B3.
- EUA: SEC EDGAR (10-K anual, 10-Q trimestral, 8-K eventos, DEF 14A proxy, Form 4 insiders, 13F posições de gestores).
- Resultado: ler o release, ouvir a call (perguntas dos analistas são o melhor trecho), comparar guidance vs. consenso.

## Calendário de resultados

Os maiores movimentos de preço acontecem em resultados. Regras:
- Nunca segurar posição alavancada através de resultado.
- Com opções, a vol implícita sobe antes e desaba depois (crush): vender vol antes, comprar depois, salvo tese forte.
