# Handoff integrado: tokens e qualidade — 19/11/2026

A versão final do adaptador estruturado consumiu **801.966 tokens OBIA contra
965.327 do baseline**, economia agregada de **16,9%**, incluindo criação e
atualização dos checkpoints. Os 16 critérios passaram em todas as retomadas;
a auditoria das doze notas iniciais/finais não encontrou perda de requisitos,
correções, fontes ou incerteza nem contradições de estado atuais.

O ganho ficou concentrado nos históricos longos: **29,6% de economia**. Nos curtos,
o OBIA ainda custou **5,3% a mais**, e dois dos seis pares regrediram. É um resultado
do **modo integrado opcional**, não uma medição do fluxo padrão com hooks. Tokens
totais menores não demonstram preço faturado menor: entrada não cacheada, saída e
tempo somado de execução aumentaram nesta amostra.

A primeira rodada **não atingiu o objetivo**: +21,5% tokens e nove notas com estado
de persistência desatualizado. Seus resultados e custos foram mantidos; nenhuma
execução ou baseline daquela rodada foi reutilizado na validação final.

## O que mudou

O adaptador opcional `handoff.py` fornece schema e memória ao agente. O agente
produz um checkpoint estruturado junto da resposta, e o chamador valida e grava
essa saída usando o armazenamento OBIA existente. Operações de memória deixam
de exigir chamadas de ferramenta feitas pelo modelo. A geração e a manutenção
do texto continuam consumindo tokens e entram integralmente na medição.

O adaptador não chama modelos, rede ou hooks. Confere SHA, leitura após gravação,
histórico e ownership; recusa substituir notas legadas ou alteradas por humanos.
Falhas depois de uma gravação identificam o recibo conhecido, sem permitir uma
tentativa cega de sobrescrita. O protocolo precisa de integração explícita do
host; esta avaliação não mede o fluxo interativo padrão nem a injeção dos hooks.

## Rodada inicial: resultado negativo preservado

Fonte `ec19026`; [protocolo congelado](integrated-handoff-protocol.md) antes das
execuções e [dados completos](integrated-agent-measurements-2026-11-19.json).
São três pares por tamanho de histórico e 18 execuções novas. Modelo
`gpt-6-astra`, esforço `xhigh`, baseline e grader iguais aos estudos anteriores.

Totais por três pares, em tokens de entrada + saída:

| Histórico | Baseline | Criação | Retomada + atualização | OBIA inclusivo | Acréscimo |
|---|---:|---:|---:|---:|---:|
| Curto | 347.052 | 160.842 | 341.458 | 502.300 | 44,7% |
| Longo | 552.709 | 97.897 | 492.670 | 590.567 | 6,9% |
| Total | 899.761 | 258.739 | 834.128 | 1.092.867 | 21,5% |

| Par | Baseline | OBIA inclusivo | Economia líquida |
|---|---:|---:|---:|
| Curto 0 | 92.222 | 177.149 | −92,1% |
| Curto 1 | 127.267 | 153.444 | −20,6% |
| Curto 2 | 127.563 | 171.707 | −34,6% |
| Longo 0 | 162.433 | 193.567 | −19,2% |
| Longo 1 | 195.052 | 189.976 | 2,6% |
| Longo 2 | 195.224 | 207.024 | −6,0% |

Os seis agentes baseline fizeram 40 comandos; a criação OBIA fez 9 e as retomadas
46. As 24 operações determinísticas prepare/capture somaram 0,200 segundo de tempo
decorrido. Elas não fazem chamadas de modelo, mas não são trabalho computacional
gratuito. Os três escritores de histórico longo produziram checkpoints sem
ferramentas; alguns escritores curtos e retomadas releram o histórico fornecido.

A auditoria verificou comandos, testes declarados, fontes e os corpos iniciais e
finais. Os requisitos aceitos, correções e incerteza de latência foram retidos;
não houve desvio de escopo observado. Contudo, cinco notas iniciais e quatro
finais ainda diziam que sua gravação estava pendente mesmo depois do capture.
Validade estrutural e 16/16 no grader não resolvem essa contradição semântica.

## Correção e nova avaliação

A revisão `8a4acdc` separa estado da tarefa de estado da gravação, que pertence
ao recibo. Também orienta reutilizar evidência histórica já fornecida, recuperar
fontes quando houver lacunas/conflitos e agrupar observações independentes.
Arquivos atuais, fatos voláteis e implementação continuam exigindo verificação.
Não há teto de ferramentas, corte de testes nem redução de esforço do modelo.

O [protocolo da segunda rodada](integrated-context-reuse-protocol.md) foi comitado
antes de iniciar outras 18 execuções, com baseline e checkpoints novos.
[Dados completos da versão final](integrated-reuse-measurements-2026-11-19.json).
A melhoria de instruções faz parte do tratamento OBIA: este desenho não isola
seu efeito do efeito da memória. Fonte da execução: `8a4acdc`.

| Histórico | Baseline novo | Criação | Retomada + atualização | OBIA inclusivo | Economia líquida |
|---|---:|---:|---:|---:|---:|
| Curto | 350.764 | 55.368 | 313.833 | 369.201 | −5,3% |
| Longo | 614.563 | 98.018 | 334.747 | 432.765 | 29,6% |
| Total | 965.327 | 153.386 | 648.580 | 801.966 | 16,9% |

| Par | Baseline novo | OBIA inclusivo | Economia líquida |
|---|---:|---:|---:|
| Curto 0 | 129.681 | 143.028 | −10,3% |
| Curto 1 | 127.139 | 112.438 | 11,6% |
| Curto 2 | 93.944 | 113.735 | −21,1% |
| Longo 0 | 225.492 | 149.230 | 33,8% |
| Longo 1 | 194.097 | 150.953 | 22,2% |
| Longo 2 | 194.974 | 132.582 | 32,0% |

Os seis escritores fizeram **zero comandos de ferramenta**, mantendo a geração
por modelo inteiramente contabilizada. A criação caiu de 258.739 para 153.386
tokens (40,7%). As retomadas OBIA fizeram 36 comandos contra 43 do baseline;
prepare/capture somaram 0,214 segundo em 24 operações determinísticas.

Todos os checkpoints foram validados, gravados e relidos; histórico e ownership
conferem com os SHAs. Todas as doze retomadas passaram nos 13 testes funcionais e
três critérios de retenção, sem alteração dos arquivos protegidos. A auditoria
verificou retenção inicial, reconciliação final, fontes, comandos e alegações de
testes. Há uma limitação explícita no baseline curto 1: os testes executados e
seus resultados são observáveis, mas o diretório alternativo alegado não consta
da trace. Esse detalhe não foi tratado como verdadeiro nem como falso.

O baseline variou de 899.761 para 965.327 tokens (+7,3%) entre rodadas; o OBIA caiu
26,6%. A comparação principal é pareada com o baseline novo. Modelo, esforço e
prompts iguais não eliminam variação entre execuções; três repetições por tamanho
e uma única tarefa não estabelecem equivalência geral ou significância ampla.

### Tokens totais, cache e duração são medidas diferentes

| Medida na rodada final | Baseline | OBIA inclusivo |
|---|---:|---:|
| Entrada total | 947.490 | 762.201 |
| Entrada em cache (parte da entrada) | 806.784 | 530.304 |
| Entrada não cacheada | 140.706 | 231.897 |
| Saída total | 17.837 | 39.765 |
| Tokens totais | 965.327 | 801.966 |
| Soma das durações das execuções | 486,7 s | 997,9 s |

As durações OBIA incluem 278,3 s de criação e 719,6 s de retomada/manutenção;
são somas por braço, não o relógio total do experimento com dois workers.
Não houve ganho de duração nesta amostra. Preço depende de tarifas/cache que
não foram medidos; a redução de tokens totais não deve ser apresentada como
economia financeira demonstrada.

## Contagem e limites

Os números vêm dos eventos reais `turn.completed.usage`, conferidos por SHA.
Entrada em cache e saída de raciocínio são subconjuntos, não parcelas somadas de
novo. Toda execução paga continua no ledger, inclusive se o capture posterior
falhar. Custo desconhecido nunca vira zero; falta de evidência impede sucesso.
O exportador também confere os bytes atuais e históricos contra os recibos.

A primeira rodada consumiu **1.992.628 tokens únicos** somando ambos os braços;
a validação final consumiu **1.767.293**. As **36 execuções novas** totalizam
**3.759.921 tokens medidos**, sem retries, replays ou custos de geração omitidos.
As evidências brutas ficam em arquivo privado com 580 arquivos; os 36 eventos
foram conferidos byte a byte após arquivamento. SHA-256 do arquivo:
`51ab315cd2312ad67d3e6c02c9553f4d226cec2d3751d107337528693de27876`.
Desenvolvimento, este chat, auditorias auxiliares e seus checkpoints não entram
na comparação. Não medimos preço faturado, horas humanas, compactação nativa ou
qualidade geral. É uma tarefa sintética pequena, sujeita à variação do modelo e
do cache; os resultados não autorizam prometer economia em qualquer projeto.
