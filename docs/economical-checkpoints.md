# Checkpoints econômicos: teste com agentes reais

A validação da versão final ficou em **1.955.653 tokens por seis cenários**, com
criação e manutenção incluídas: **35,1% menos que os 3.011.207 do OBIA anterior**.
As chamadas de comando caíram de **166 para 118 (28,9%)**. Ainda são **102,1% mais
tokens que o baseline de 967.784**: não demonstramos economia líquida nesta tarefa.

Foram **24 novas execuções medidas**: primeiro 18 em seis pares completos, depois
seis novas retomadas para validar correções de qualidade. Estas últimas reutilizam
os mesmos checkpoints iniciais e os custos já medidos de criação/baseline; não são
seis pares independentes novos. Na validação final, todos os 16 critérios passaram
e a auditoria não encontrou contradições atuais restantes nas seis notas.

Modelo solicitado `gpt-6-astra`, esforço `xhigh`, mesmas fixtures e critérios.
Resultados negativos e regressões da primeira rodada permanecem documentados.

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
  Os agentes do experimento não fabricaram eventos de hook; configuração e
  confiança permaneceram intactas.

Implementação: `206849b`; protocolo congelado/harness: `ccc8545`. Ver
[protocolo econômico](economical-checkpoints-protocol.md),
[dados completos](economical-agent-measurements-2026-11-18.json) e
[avaliação anterior](real-agent-evaluation.md).

## Comparação principal: seis pares novos

A primeira rodada otimizada consumiu **1.911.995 tokens OBIA**, redução histórica
de **36,5%**, porém acréscimo de **97,6%** sobre o baseline novo. A qualidade textual
exigiu a correção descrita adiante.

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
em Resume, Facts, Constraints e Corrections. A correção foi validada por seis novas
retomadas, conforme o [protocolo de reconciliação](checkpoint-reconciliation-protocol.md).
Os resultados da primeira rodada acima permanecem preservados.

## Validação da versão final: seis retomadas adicionais

Commit testado `bcc1271`; [dados e auditorias completos](reconciled-agent-measurements-2026-11-18.json).
Todos os seis checkpoints iniciais foram restaurados com o mesmo SHA em workspaces
novos, com implementação inicialmente stub e a mesma mudança de política 3→2.
Os prompts de retomada são idênticos aos da rodada econômica. As soluções e
respostas anteriores não foram colocadas junto do workspace durante a execução.

| Histórico | Criação já medida | Novas retomadas + manutenção | OBIA inclusivo | Baseline reutilizado | Acréscimo |
|---|---:|---:|---:|---:|---:|
| Curto, três cenários | 302.877 | 526.964 | 829.841 | 350.984 | +136,4% |
| Longo, três cenários | 443.929 | 681.883 | 1.125.812 | 616.800 | +82,5% |
| Total | 746.806 | 1.208.847 | 1.955.653 | 967.784 | +102,1% |

O total inclusivo ficou **2,3% acima da primeira rodada econômica**, mantendo
**35,1% de redução sobre o OBIA anterior**. Resultados individuais variaram:
reconciliar melhor a nota não garante uma diminuição em toda execução. Entrada
sem cache: 293.828; saída: 59.265; chamadas de comando: 118; ações de ferramenta:
124. As contagens incluem a criação original, explicitamente reutilizada.

Todos os **16/16 critérios passaram nas seis novas retomadas**. As seis notas
finais mantiveram histórico, política atual 2, latência não verificada, referências
recuperáveis e estado coerente entre Resume, Facts, Constraints e Corrections.
A auditoria não encontrou as afirmações antigas no presente; restrições e estados
anteriores ficaram explicitamente históricos. Zero desvios de escopo observados,
com declarações de testes consistentes com as traces. A avaliação semântica é
adicional ao conjunto original de 16 critérios, não uma alteração retroativa dele.

Ainda houve chamadas inválidas/desnecessárias durante a descoberta, incluindo
mistura de seletores de seção/fonte. Seus custos continuam incluídos. Nenhum
agente fez read/check redundante depois do recibo de gravação. Uma amostra pequena
sem falhas observadas não garante qualidade equivalente em qualquer projeto.

## Contagem e limites

Tokens vêm de `turn.completed.usage`, conferidos contra os eventos e hashes.
Entrada em cache é subconjunto da entrada; raciocínio é subconjunto da saída.
Total = entrada + saída, sem somá-los duas vezes. Não é medição de dinheiro.
Na primeira rodada otimizada foram **2.879.779 tokens únicos** somando os dois
braços, incluindo os 746.806 de criação e toda manutenção nas retomadas. As seis
novas retomadas acrescentaram **1.208.847**: **4.088.626 tokens únicos nas 24
execuções medidas desta melhoria**. As 12 traces de criação/baseline copiadas para
o relatório de replay não foram cobradas outra vez nessa soma.

São fixtures sintéticas, uma tarefa com duas extensões de histórico e uma única
retomada explícita via CLI. Não mede injeção automática de hooks, comparação com
compaction nativa, horas humanas ou comportamento de todo projeto. Orquestração,
desenvolvimento, auditorias auxiliares e checkpoints deste chat ficam fora dos
agentes medidos; não alegamos contar todo o custo de produzir a pesquisa.
Prompts, comandos e respostas brutos ficam privados. Os arquivos públicos contêm
código sintético, números e observações de auditoria.

## Verificação e conservação da evidência

Os 87 testes locais passaram e a skill foi validada. As seis cópias da primeira
rodada coincidem com `ccc8545`; as seis do replay com `bcc1271`. Prompts de retomada,
eventos reutilizados e snapshots iniciais foram comparados byte a byte. A skill
instalada foi atualizada em quatro arquivos e os 11 arquivos versionados foram
conferidos. `hooks.py`, `hooks.json` e `config.toml` permaneceram inalterados.

A evidência bruta foi arquivada privadamente: 511 arquivos; 24 hashes distintos de
eventos medidos; 12 cópias reutilizadas identificadas. SHA-256 do arquivo:
`e24ced12fc6acd77b3f6d3d55f43ec28151af509ac7dcd0d27a1734b22b37ff3`.
Os resultados são reproduzíveis pelos protocolos e scripts versionados, sujeitos
à variação do modelo e do cache. Não há estimativa de preço ou poupança universal.
