# Avaliação com agentes reais — 18 de novembro de 2026

**Neste piloto, a OBIA não economizou tokens.** Para uma única retomada via CLI,
incluindo criar e atualizar checkpoints, foram **3.011.207 tokens**, contra
**917.518** com o histórico completo: **3,28 vezes o consumo**.
Os dois métodos passaram nos mesmos critérios funcionais e de retenção.

A conclusão vale para este protocolo, modelo e tarefa. Não demonstra que a OBIA
sempre custa mais, nem invalida a redução de tamanho do pacote de recuperação:
mede uma operação mais ampla, com agentes executando ferramentas e mantendo a memória.

## O que foi medido

Foram seis pares, com três repetições de histórico curto e três de histórico
longo, totalizando **18 execuções reais concluídas**. Usou-se `codex-cli
0.169.0-alpha.11.1`, com modelo solicitado `gpt-6-astra` e esforço `xhigh` nos dois
braços. O protocolo foi registrado em Git antes das execuções; o harness corrigido
estava no commit `73a4e5e`, avaliando o código OBIA publicado em `2351b6b`.

No baseline, um agente novo recebe o histórico completo e implementa/verifica
um seletor de fila local. Com OBIA, um agente real primeiro cria um checkpoint;
outro, sem o contexto anterior, recupera a nota, implementa/verifica a mesma
função e atualiza/confere o checkpoint. O custo dessa manutenção final está na
retomada; não há precisão para atribuir cada token a uma operação isolada dentro
do turno.

Os dados são os campos `turn.completed.usage` emitidos pela CLI. Incluem entrada
e saída acumuladas durante o turno, leituras, ferramentas, tentativas malsucedidas,
instruções, criação e manutenção de memória. **Não são estimativas por caracteres.**
Cache é parte da entrada; raciocínio é parte da saída: nenhum foi contado duas
vezes, conforme a [definição de uso de tokens](https://help.openai.com/en/articles/4936856-understanding-and-counting-tokens).
A autoria do benchmark e as mensagens/checkpoints deste chat de orquestração
ficam fora dessa comparação, assim como o trabalho anterior comum que produziu o
histórico. Não é uma conta de todos os tokens gastos para construir a pesquisa.

## Custo incluindo checkpoints

Valores em **mil tokens, média por retomada**, três pares em cada linha:

| Histórico | Baseline integral | Criar checkpoint | Retomar + manter checkpoint | OBIA total | Acréscimo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Curto | 122,7 | 140,5 | 312,4 | 452,9 | +269,0% |
| Longo | 183,1 | 242,1 | 308,7 | 550,8 | +200,8% |

A criação inicial sozinha já custou mais que o baseline médio nos dois casos.
Mesmo retirando essa criação da comparação, a retomada **com manutenção final**
consumiu 154,5% mais no caso curto e 68,6% mais no longo. Portanto, simplesmente
amortizar o primeiro checkpoint não demonstra um ponto de equilíbrio neste fluxo.
Não foi medido um ciclo de retomadas com outra política de manutenção.

Resultados individuais, incluindo toda a criação e manutenção:

| Par | Baseline | OBIA | Acréscimo |
| --- | ---: | ---: | ---: |
| Curto 1 | 109.695 | 506.082 | +361,4% |
| Curto 2 | 111.701 | 446.023 | +299,3% |
| Curto 3 | 146.838 | 406.680 | +177,0% |
| Longo 1 | 194.611 | 594.294 | +205,4% |
| Longo 2 | 194.233 | 521.077 | +168,3% |
| Longo 3 | 160.440 | 537.051 | +234,7% |

São três repetições de uma tarefa por tamanho, com ordem alternada dos braços.
A variação é visível; não há amostra suficiente para uma estimativa universal ou
um teste estatístico de equivalência entre métodos.

## Cache, comandos e tempo

Somando os seis pares:

| Categoria | Baseline | OBIA, incluindo checkpoints |
| --- | ---: | ---: |
| Entrada total | 900.910 | 2.940.127 |
| Entrada em cache, incluída acima | 784.000 | 2.586.368 |
| Entrada sem cache | 116.910 | 353.759 |
| Saída, incluindo raciocínio | 16.608 | 71.080 |
| Total entrada + saída | 917.518 | 3.011.207 |

Cerca de 87%–88% da entrada veio de cache. Ainda assim, a OBIA teve mais entrada
sem cache e mais saída. Esses números não devem ser convertidos diretamente em
um preço: não foi medida cobrança financeira da conta.

O baseline executou **41 comandos shell**; a OBIA executou **166**, somando
criação e retomada. Incluindo operações de edição, foram 47 ações de ferramenta
contra 170. As traces mostram leitura de instruções/fontes, elaboração de JSON,
gravar/ler/conferir notas e alguns diagnósticos desnecessários. Cada nova rodada
pode processar novamente contexto já acumulado. Isso ajuda a explicar por que
uma nota menor não se traduziu em menor consumo total; não é uma atribuição causal
exata de tokens por comando.

A duração média somada dos agentes por par foi cerca de **74 s no baseline** e
**282–298 s na OBIA**, conforme o tamanho do histórico. Dois pares rodaram em
paralelo; essas somas não são o tempo de parede do experimento nem trabalho humano
poupado. Latência do serviço e cache não foram controlados.

## Qualidade e persistência

O avaliador foi definido antes das execuções e não foi copiado para os ambientes
dos agentes. Cada retomada recebeu 13 verificações funcionais e três de retenção.
Os dois métodos obtiveram **16/16 em todas as seis retomadas**: 96 verificações
aprovadas por braço. Isso demonstra ausência de regressão nos critérios testados,
sem demonstrar uma melhoria geral de qualidade ou redução de alucinações.

Os critérios incluem limites de tempo/tentativas, cancelamento, ordem, filtragem
antes da deduplicação, limite de resultados e preservação da entrada. A política
mudou de 3 para 2 tentativas após o checkpoint inicial: todos consultaram o valor
atual. A alegação de latência inferior a 10 ms permaneceu explicitamente não
verificada. As declarações sobre testes foram confrontadas com saídas de comandos
e artefatos sintéticos de verificação.

Na OBIA, **6/6 checkpoints iniciais** eram válidos e mantinham a tarefa ativa;
**6/6 checkpoints finais** estavam atualizados, válidos e completos, com SHA
alterado e a versão anterior preservada. Os arquivos protegidos e as seis cópias
do código da skill permaneceram intactos.

Houve **um desvio de escopo**, separado da pontuação funcional: na retomada curta
1, o agente com OBIA listou e sondou intérpretes Python temporários fora da pasta
do fixture. Não foram observadas leituras de conversas privadas nem alterações
na configuração. Esse desvio e seus custos permanecem no resultado principal.
Excluindo o par inteiro apenas como análise de sensibilidade, o acréscimo do caso
curto ainda é **229,8%**. Os outros pares não tiveram esse desvio observado.
A auditoria dirigida não é uma prova geral de segurança do agente.

## Tentativa inválida e custo da preparação

A primeira rodada foi interrompida porque a cópia temporária não incluía a
dependência YAML vendorizada da instalação real. O problema foi identificado
antes de qualquer par completo. A correção adicionou a dependência e uma checagem
prévia; tarefas, prompts, modelo e critérios permaneceram iguais. Não houve
repetição seletiva para substituir um resultado desfavorável.

Duas execuções dessa rodada terminaram; outras duas foram interrompidas sem
consumo final disponível. Somando os dois resultados conhecidos ao teste de
conectividade, houve **373.147 tokens adicionais conhecidos** de preparação,
fora da comparação principal. O total dessa preparação é maior ou igual a esse
valor; os dois consumos interrompidos são **desconhecidos**, não zero.
O relatório agregado preserva esses registros separadamente.
As execuções válidas somaram 3.928.725 tokens entre os dois braços. Com a preparação
conhecida, o experimento consumiu pelo menos 4.301.872 tokens contabilizados,
incluindo cache, além das duas execuções interrompidas e deste chat de orquestração.

## Interpretação e próximos testes

A redução anterior de **60,4%** dizia respeito ao texto de um pacote sintético
mais suas fontes. Aqui houve agentes reais, instruções repetidas, verificações,
escrita de checkpoints e várias chamadas. São métricas diferentes. O resultado
atual não sustenta anunciar economia líquida de tokens para este fluxo.

A prioridade sugerida é reduzir o trabalho por checkpoint: menos leituras
repetidas, menos etapas de gravar/ler/conferir e manutenção proporcional à mudança.
Qualquer alteração deve manter os critérios de qualidade e ser medida novamente.
Ainda faltam tarefas mais complexas, vários ciclos de retomada e comparações com
resumos manuais e compactação nativa.

Este teste usou o helper explicitamente em novos agentes CLI. **Não mediu a
retomada com o pacote automaticamente injetado pelos hooks**, que pode evitar
chamadas, nem a confiabilidade dos eventos de ciclo de vida. Nenhum evento foi
fabricado. Configuração pessoal e confiança dos hooks conservaram seus hashes;
raw traces ficaram fora do repositório público.

## Evidência e reprodução

- [Protocolo](real-agent-evaluation-protocol.md), [harness](../tools/evaluate_real_agents.py)
  e [fixtures/avaliador](../tools/agent_eval_cases.py).
- [Resultados por etapa e par](real-agent-measurements-2026-11-18.json), com usage
  real, SHA das traces, métricas de qualidade e observações da auditoria.
- [Agregador](../tools/summarize_agent_evaluation.py), que confere usage contra os
  eventos e verifica os hashes antes de exportar.

A execução consome uso real do Codex; siga o comando do protocolo para reproduzir.
A estrutura do repositório foi validada por 77 testes locais. As traces completas
são locais; somente dados sintéticos, agregados e código de reprodução entram no Git.
