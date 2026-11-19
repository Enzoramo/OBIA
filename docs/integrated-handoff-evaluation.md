# Handoff integrado: tokens e qualidade — 19/11/2026

A primeira rodada do adaptador estruturado **não atingiu o objetivo**: consumiu
**1.092.867 tokens OBIA contra 899.761 do baseline**, incluindo criação e atualização
dos checkpoints, um acréscimo de **21,5%**. Os 16 critérios funcionais/retenção
passaram em todas as retomadas, mas nove das doze notas continham uma afirmação
desatualizada sobre sua própria persistência. Esses resultados e custos permanecem
registrados; uma segunda rodada independente avalia a correção.

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
antes de iniciar outras 18 execuções, com baseline e checkpoints novos. Seus
resultados ainda estão em avaliação. A melhoria de instruções faz parte do
tratamento OBIA: este desenho não isola seu efeito do efeito da memória.

## Contagem e limites

Os números vêm dos eventos reais `turn.completed.usage`, conferidos por SHA.
Entrada em cache e saída de raciocínio são subconjuntos, não parcelas somadas de
novo. Toda execução paga continua no ledger, inclusive se o capture posterior
falhar. Custo desconhecido nunca vira zero; falta de evidência impede sucesso.
O exportador também confere os bytes atuais e históricos contra os recibos.

A primeira rodada consumiu **1.992.628 tokens únicos** somando ambos os braços.
Desenvolvimento, este chat, auditorias auxiliares e seus checkpoints não entram
na comparação. Não medimos preço faturado, horas humanas, compactação nativa ou
qualidade geral. É uma tarefa sintética pequena, sujeita à variação do modelo e
do cache; os resultados não autorizam prometer economia em qualquer projeto.
