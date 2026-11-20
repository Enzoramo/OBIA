# Recuperação orientada à tarefa — 20 de novembro de 2026

O OBIA agora aceita `--focus` na recuperação de uma tarefa conhecida. A versão
foi instalada localmente. No piloto com seis agentes reais, o fluxo por foco
consumiu **947.064 tokens**, 8,22% menos que o baseline e 16,72% menos que a
recuperação breve, incluindo planejamento e checkpoints.

A condição de qualidade não passou: baseline e breve obtiveram 29/29; foco,
28/29. A divergência está na soma de custos parcialmente conhecidos. Portanto,
o resultado não demonstra economia com qualidade equivalente. O placar original
permanece publicado, sem reparo das implementações ou repetição dos agentes.

## Implementação

O commit `c5fc531` acrescenta seleção lexical determinística de seções completas.
Resume, restrições, decisões, correções, hipóteses e seções reconhecidas de
incerteza permanecem no núcleo obrigatório. As fontes citadas vêm do mesmo
snapshot, junto com o SHA necessário para expandir a leitura.

A resposta informa quais seções foram omitidas e distingue ausência de
correspondência de falta de espaço. O limite considera o JSON serializado,
sem cortar seções. Se o núcleo não cabe, o helper exige uma leitura integral.
Metadados não padronizados também provocam fallback integral. Um novo foco não
é suprimido apenas porque o SHA já era conhecido. O modo não chama modelos nem
lê automaticamente o conteúdo de notas vinculadas.

Exemplo, a partir da pasta da skill instalada:

```sh
python3 scripts/desktop.py --config-dir CONFIG recover \
  --session SESSION --path PROJECT_ROOT --task TASK \
  --focus 'renderer ledger accounting unknown costs'
```

Sem `--focus`, o comportamento anterior continua disponível. A seleção é
lexical: pode deixar de encontrar informação pertinente. As omissões precisam
ser inspecionadas, e qualquer seção necessária pode ser lida pelo SHA retornado.
Consulte o [fluxo desktop](../skills/obia/references/desktop.md) e os
[comandos](../skills/obia/references/commands.md).

## Protocolo e custos

O protocolo v1 foi congelado em `2153105`, antes dos agentes. Ele corrigiu a
ambiguidade anterior: `schema` inteiro 1 e `workflow` igual a `integrated_handoff`
passaram a ser obrigatórios, e todas as fixtures válidas receberam esses campos.
Os 29 critérios incluem erros de formato, uso desconhecido, custos extras,
qualidade estrita, regressões, privacidade e preservação dos inputs.

Três planejadores novos inspecionaram as mesmas cópias de 23 arquivos públicos.
Cada um recebeu depois a mesma correção aceita, substituindo agregados
armazenados por cálculo pelo ledger. Três agentes novos implementaram um
renderizador de relatórios. O baseline recebeu seu próprio histórico em texto;
os braços OBIA recuperaram suas próprias notas. Ambos os braços de memória
receberam a mesma orientação de organização, sem conteúdo escrito pelo avaliador
ou preenchimento artificial. Só a retomada do foco recebeu `--focus`.

Todos usaram o modelo observado `gpt-6-astra`, esforço `medium`, sem overrides.
Nenhuma execução de estudo anterior foi reutilizada. Houve seis executores e
nove turnos de trabalho, sem repetição. O histórico do baseline foi conferido
antes da retomada: os dois pedidos técnicos completos estavam presentes; blocos
opacos e raciocínio não foram transferidos.

| Fluxo | Planejamento | Retomada | Total |
|---|---:|---:|---:|
| Baseline | 420.022 | 611.867 | **1.031.889** |
| Breve | 803.516 | 333.687 | **1.137.203** |
| Foco | 684.912 | 262.152 | **947.064** |

Cada braço OBIA teve três marcos de checkpoint: plano inicial, plano corrigido e
conclusão, com uma gravação intermediária adicional no plano inicial de cada
braço. Os oito recibos foram verificados. Redação, gravação, ack, recuperação,
expansões, implementação e testes
estão incluídos nas fases acima. O custo causal isolado de um checkpoint não foi
estimado. Os seis executores somaram **3.116.156 tokens**; desenvolvimento,
orquestração, revisão e publicação pelo agente principal/revisores estão fora
dessa soma, que não representa o custo total do projeto.

| Medida inclusiva | Baseline | Breve | Foco |
|---|---:|---:|---:|
| Entrada não cacheada | 107.139 | 71.522 | 49.595 |
| Entrada cacheada | 913.920 | 1.051.776 | 884.480 |
| Saída | 10.830 | 13.905 | 12.989 |
| Chamadas de ferramentas | 18 | 22 | 20 |
| Execuções de comandos | 33 | 37 | 33 |
| Soma da duração dos turnos | 260,859 s | 330,615 s | 315,445 s |

Os totais vêm do último contador cumulativo de cada sessão, com identidade e
fechamento verificados. Cache e raciocínio são subconjuntos; não foram somados
novamente. A retomada por foco foi mais barata, mas a criação da memória também
custou tokens. O breve terminou 10,21% acima do baseline. Foco gerou mais saída e
teve maior duração inclusiva que o baseline; não afirmamos ganho financeiro ou
de velocidade.

## Qualidade e esclarecimento prospectivo

Os agentes executaram nove testes no baseline, oito no breve e nove no foco,
incluindo os dois relatórios e verificações de CLI. O foco executou a CLI no
relatório reuse e num caminho inválido; ambos os relatórios foram testados pela
API. A verificação independente deu 29/29, 29/29 e
28/29, respectivamente. Os 23 arquivos de origem permaneceram intactos; cada
retomada adicionou somente os dois arquivos permitidos.

No caso divergente, duas execuções custam 100 e 20 tokens; uma terceira informa
entrada 45, saída desconhecida e total declarado 50. O foco retorna braços
desconhecidos como `null`, medição incompleta, sucesso falso e nenhum percentual.
Ele soma 45 ao limite inferior conhecido, produzindo `known_total_tokens=165`.
O avaliador espera 120, contando apenas execuções com entrada e saída conhecidas.
A divergência não é uma declaração falsa de economia.

O contrato v1 dizia que o custo da execução parcial era desconhecido, mas não
explicitava a contribuição de seus componentes conhecidos para essa soma. A
versão 2, commit `6063abf`, esclarece prospectivamente: `known_total_tokens` soma
somente execuções completas; um limite inferior por componentes, se exposto,
precisa de outro nome. Excluir uma parcela desconhecida da soma não significa
que seu custo real seja zero.

Esse esclarecimento não foi entregue aos agentes do piloto. **A versão 2 ainda
não foi avaliada numa nova coorte real.** Os resultados continuam vinculados ao
protocolo v1 e `primary_success=false`; nenhuma interpretação posterior substitui
o critério congelado. O [protocolo](task-focused-protocol.md) registra a distinção.

A auditoria independente confirmou retenção semântica e persistência. A regra
de uso desconhecido estava tanto na nota corrigida quanto no pacote recebido
pelo agente focalizado. O breve expandiu Renderer accounting e Deferred hook
diagnostics; o foco recebeu Renderer accounting diretamente e também expandiu
o diagnóstico adiado, que não coube no orçamento. Não houve evidência de perda
da regra na recuperação. Essa auditoria não substitui o placar funcional.

## Limites e evidências

Um único cenário com planejamentos independentes não separa o efeito do seletor
da variação entre planos e implementações. A transferência do histórico para
um agente novo também não equivale a continuar um chat com prefixo já em cache.
A diferença numérica não deve ser generalizada para uso diário.

Os subagentes não receberam SessionStart diretamente e os acks dos braços OBIA
têm identidade de turno nula. Não há comprovação do Stop nativo. Este trabalho não alterou configuração ou confiança dos hooks e não fabricou
eventos. O código dos hooks e o hash de `hooks.json` permanecem iguais. O hash
de `config.toml` mudou fora das operações deste trabalho: seu mtime é 17:42:55
UTC, após o último executor terminar às 17:38:45 UTC. A origem e o conteúdo
completo da alteração não foram determinados; não restauramos o arquivo nem
afirmamos igualdade integral dessa configuração. Os seis executores registraram
`gpt-6-astra/medium`; a diferença está documentada nos dados.

Os [dados públicos](task-focused-measurements-2026-11-20.json) preservam as seis
medições, hashes de origem, grades, escopo, auditoria e recibo do arquivo local
saneado. Conversas privadas, bootstrap e raciocínio não são publicados. O
repositório passou em **160 testes locais**; os três testes do protocolo também
passaram após o esclarecimento textual da versão 2.
