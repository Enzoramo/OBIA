# Checkpoints econômicos: teste com agentes reais

Na primeira rodada otimizada, o OBIA consumiu **1.911.995 tokens**, incluindo
criação e manutenção dos checkpoints: **36,5% menos que os 3.011.207 da versão
anterior**. Ainda consumiu **97,6% mais que o novo baseline de 967.784 tokens**.
Reduzir o custo do OBIA não estabeleceu economia líquida nesta tarefa.

Foram 18 novas execuções, seis pares, mesmo modelo solicitado `gpt-6-astra`, esforço
`xhigh`, mesmas fixtures e mesmos 16 critérios independentes. Todos passaram nos
dois braços. A auditoria também encontrou problemas de consistência textual na
memória; eles são apresentados abaixo, sem confundi-los com o resultado funcional.

## O que mudou

- `save`/`patch` verificam o texto persistido sob o lock e devolvem um recibo
  compacto. A situação do índice fica separada: um erro no índice não oculta uma
  nota salva. Não é preciso repetir `read` e `check` após um recibo válido.
- `recall --view brief --with-sources` inclui definições citadas e inventário de
  IDs no mesmo snapshot, respeitando orçamento e omissões explícitas.
- O fluxo comum da skill permite reutilizar conteúdo/SHA já disponíveis e
  registrar somente mudanças pertinentes. Seções não lidas continuam exigindo
  expansão antes de substituição. Histórico e conflitos permanecem protegidos.
- O ack de hooks continua separado, condicionado ao SHA e ao turno observado.
  Nenhum evento foi simulado, nem configuração/confiança de hooks alterada.

Implementação: `206849b`; protocolo congelado/harness: `ccc8545`. Ver
[protocolo econômico](economical-checkpoints-protocol.md),
[dados completos](economical-agent-measurements-2026-11-18.json) e
[avaliação anterior](real-agent-evaluation.md).

## Comparação principal: seis pares novos

Média de tokens por par; cada linha reúne três repetições:

| Histórico | Baseline novo | Criação do checkpoint | Retomada + manutenção | OBIA inclusivo | Acréscimo sobre baseline |
|---|---:|---:|---:|---:|---:|
| Curto | 116.995 | 100.959 | 189.551 | 290.510 | +148,3% |
| Longo | 205.600 | 147.976 | 198.845 | 346.822 | +68,7% |

Totais efetivamente medidos, sem arredondamento:

| Etapa | OBIA anterior | OBIA econômico |
|---|---:|---:|
| Criação dos seis checkpoints | 1.147.977 | 746.806 |
| Seis retomadas com manutenção | 1.863.230 | 1.165.189 |
| Total OBIA | 3.011.207 | 1.911.995 |
| Comandos executados | 166 | 122 |
| Ações de ferramenta | 170 | 128 |
| Entrada sem cache | 353.759 | 285.610 |
| Saída, incluindo raciocínio | 71.080 | 57.105 |

Os comandos caíram **26,5%**, a entrada sem cache **19,3%** e a saída **19,7%**.
Nas 12 fases OBIA auditadas, o recibo eliminou leituras/checks redundantes depois
da gravação. A recuperação, expansão de seções e atualização da nota continuam
custando chamadas. Os agentes ainda escreveram notas iniciais de 6.769–8.633 bytes;
a instrução de concisão não produziu checkpoints mínimos.

O baseline também variou: 917.518 tokens na avaliação anterior e 967.784 agora.
Assim, a comparação histórica é descritiva; cache, variação do modelo e decisões
autônomas não estão isolados. O baseline contemporâneo é a comparação principal.
No histórico longo, somente retomada/manutenção custou 596.536 contra 616.800 do
baseline; o custo inicial de 443.929 eliminou essa pequena vantagem. Isso não
constitui evidência de amortização em múltiplas retomadas, que não foram medidas.

## Qualidade e auditoria

- Os dois braços passaram **16/16 em cada um dos seis pares**: 96 verificações por
  braço, 192 no conjunto. Isso cobre funcionamento, política atual e retenção da
  incerteza sobre latência; não demonstra equivalência geral de qualidade.
- Checkpoints iniciais/finais estruturalmente válidos em 6/6, com estado inicial
  ativo, final concluído e versão anterior preservada. Fixtures protegidas
  permaneceram intactas. Auditoria de 18/18 traces não observou desvio de escopo;
  declarações de testes foram consistentes com as execuções.
- **short-0, long-0 e long-1:** Corrections conservou frases no presente sobre
  implementação ainda ausente/stub, apesar do Resume correto. Nos dois longos,
  outra correção dizia que o estado fora superado, sem remover a contradição.
- **short-1:** citações agrupadas como `[S1, S2]` não eram reconhecidas pelo matcher
  de IDs individuais. As fontes existiam, mas sua descoberta automática ficava
  incompleta. Isso não deve ser apresentado como memória plenamente equivalente.
- Ambiguidade inicial sobre o flag de cancelamento em short-0 e long-2 foi
  resolvida pela leitura de H03, implementação/testes corretos e nota final.
  short-2 e long-2 não apresentaram as inconsistências finais acima.

Esses achados motivaram `bcc1271`: suporte consistente a citações agrupadas na
validação/recuperação/check e instrução explícita para reconciliar estado atual
em Resume, Facts, Constraints e Corrections. A correção terá uma validação
adicional de todas as seis retomadas, conforme o
[protocolo de reconciliação](checkpoint-reconciliation-protocol.md). Os resultados
da primeira rodada acima permanecem preservados.

## Contagem e limites

Tokens vêm de `turn.completed.usage`, conferidos contra os eventos e hashes.
Entrada em cache é subconjunto da entrada; raciocínio é subconjunto da saída.
Total = entrada + saída, sem somá-los duas vezes. Não é medição de dinheiro.
Na primeira rodada otimizada foram **2.879.779 tokens únicos** somando os dois
braços, incluindo os 746.806 de criação e toda manutenção nas retomadas.

São fixtures sintéticas, uma tarefa com duas extensões de histórico e uma única
retomada explícita via CLI. Não mede injeção automática de hooks, comparação com
compaction nativa, horas humanas ou comportamento de todo projeto. Orquestração,
desenvolvimento, auditorias auxiliares e checkpoints deste chat ficam fora dos
agentes medidos; não alegamos contar todo o custo de produzir a pesquisa.
Prompts, comandos e respostas brutos ficam privados. Os arquivos públicos contêm
código sintético, números e observações de auditoria.
