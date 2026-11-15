# Quanto a OBIA poupa em trabalho e tokens

Análise de 15 de novembro de 2026, baseada na implementação
[`0ddb65f`](https://github.com/Enzoramo/OBIA/commit/0ddb65fb2e9e76ad87279c6d0f095fbd6ee40a8e).

A OBIA já permite recuperar decisões, restrições e próximos passos sem o
utilizador reconstruir toda a tarefa. **A poupança líquida de tokens e de horas
ainda não foi medida numa comparação controlada.** A medição desta análise
quantifica o tamanho dos textos consultados e o custo das instruções. Os cenários
de poupança abaixo são cálculos condicionais, não resultados de um benchmark.

O benefício tende a ser maior em projetos longos, com retomadas e mudanças de
chat. Em tarefas curtas, ou quando o contexto necessário já está disponível,
manter a memória pode acrescentar mais trabalho do que evita.

## O que foi medido

Foram selecionadas duas notas de tarefas do mesmo projeto: uma longa, com
histórico de evidências, e outra mais curta. O conteúdo foi processado localmente
com [tiktoken](https://github.com/openai/tiktoken) 0.12.0, usando `o200k_base` e
`cl100k_base`. São contagens exatas para essas codificações, **não contadores de
consumo ou faturação do modelo usado pelo agente**.

O relatório público contém apenas contagens, sem textos das notas, nomes de
tarefas, caminhos privados ou identificadores de sessões. Não foram lidas
transcrições nem executados eventos de hooks para produzir a medição.

| Texto contado uma vez | `o200k_base` | `cl100k_base` |
| --- | ---: | ---: |
| Instruções principais da skill | 1.696 | 1.698 |
| Referências de comandos, formato e hooks, somadas | 3.417 | 3.406 |
| Nota longa, resposta completa de `read` | 3.129 | 3.396 |
| Nota longa, resposta de `read --section Resume` | 278 | 302 |
| Nota curta, resposta completa de `read` | 1.173 | 1.280 |
| Nota curta, resposta de `read --section Resume` | 192 | 209 |
| Pacote de `recall` da nota longa | 3.225 | 3.492 |
| Pacote de `recall` da nota curta e uma nota relacionada | 2.119 | 2.354 |

As respostas JSON incluem os campos e a formatação produzidos pelo helper;
não incluem o enquadramento de mensagens da plataforma. O pacote da nota longa
incluiu uma nota e omitiu uma relacionada por falta de espaço. O da nota curta
incluiu duas notas. Portanto, os pacotes não são uma comparação entre tarefas
equivalentes. O limite padrão é **12.000 caracteres**, não 12.000 tokens.

Ler `Resume` em vez da nota completa reduziu o tamanho da resposta em **91,1%**
na nota longa e **83,6%** na curta, usando `o200k_base`. Isso mede leitura
seletiva dentro da OBIA. Não demonstra uma redução igual no custo total da
tarefa: um resumo pode não conter todas as restrições ou evidências necessárias.

Na nota longa, a seção de fontes representa **62,9%** dos tokens do Markdown.
É um indício concreto de que selecionar também as fontes relevantes pode evitar
releituras extensas. A evidência continua necessária quando sustenta uma decisão.

## Quanto custa manter a memória

Os helpers executam operações locais de Python e não chamam um modelo de IA.
O consumo de IA aparece quando o agente lê as instruções e as respostas das
ferramentas, escolhe o que guardar, escreve um checkpoint e verifica as fontes.

No exemplo da nota longa, só a skill e o pacote de memória somam **4.921 tokens**
em `o200k_base`. Se as três referências também forem carregadas pela primeira
vez, a soma chega a **8.338 tokens**. São tamanhos de texto somados, não o custo
total de uma sessão. Não é necessário reler todas as referências em cada turno.

Ainda podem entrar na conta:

- A escrita do checkpoint, incluindo os argumentos enviados à ferramenta.
- A releitura e o `ack`, além de verificações das fontes que continuam necessárias.
- Conteúdo duplicado entre a memória reinjetada, a resposta de `bind` e leituras
  completas posteriores.
- Uma continuação adicional de `Stop` quando não há recibo válido. Num turno
  delegado cujo primeiro evento observado seja `Stop`, a versão atual exige
  reconhecer o ID durante essa continuação, mesmo que já tenha havido um `ack`
  antes de o ID ser conhecido.
- Texto que volta a entrar em pedidos posteriores ao modelo. Contar um arquivo
  uma vez não contabiliza essas repetições.

Os testes reais de delegação confirmaram a rejeição de recibos de turnos
anteriores. Esse ganho de integridade não deve ser apresentado como uma
otimização de tokens: a continuação e o reconhecimento também têm custo.

## Quando os tokens poupados compensam

Para uma tarefa retomada `n` vezes, uma forma de calcular o saldo é:

```text
poupança = custo de reconstrução sem OBIA
           − custo inicial de criar e aprender a usar a memória
           − custo das n recuperações, atualizações e verificações com OBIA
```

Os custos devem ser totais comparáveis, com a mesma qualidade de resultado.
A referência sem OBIA deve poder usar os recursos normais do host, incluindo
resumos automáticos, compactação e ferramentas de busca. Comparar sempre a
OBIA com a releitura integral de um histórico enorme superestimaria o ganho.

Como análise de sensibilidade, suponha que todo o trabalho adicional da OBIA
por retomada, já com a criação inicial amortizada, custe **6.000** ou **10.000
tokens**. Esses dois valores são hipóteses de cálculo, não médias observadas.

| Reconstrução que seria necessária sem OBIA | Saldo com custo OBIA de 6.000 | Saldo com custo OBIA de 10.000 |
| --- | ---: | ---: |
| 3.000 tokens | Gasta 3.000 a mais | Gasta 7.000 a mais |
| 10.000 tokens | Poupa 4.000 — 40% | Sem poupança |
| 30.000 tokens | Poupa 24.000 — 80% | Poupa 20.000 — 66,7% |
| 60.000 tokens | Poupa 54.000 — 90% | Poupa 50.000 — 83,3% |

O ponto de equilíbrio ocorre quando o trabalho de reconstrução evitado supera
o custo completo da memória. Se o agente já consegue continuar com o contexto
disponível, há pouco custo de reconstrução a evitar. Em várias retomadas de uma
tarefa longa, a escrita inicial pode ser amortizada.

Esses percentuais também não equivalem diretamente a euros poupados. Entrada,
saída e leituras ou escritas de cache podem ter tarifas diferentes. A
[documentação de prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
orienta a usar os campos reais de consumo e as tarifas do modelo. Esta análise
não estima faturas, limites de um plano nem velocidade de execução a partir do
tamanho dos textos.

## Quanto trabalho humano pode evitar

O efeito já observado nesta instalação é a recuperação de uma decisão e de uma
restrição em outro contexto, incluindo após compactação, sem repetir esses
valores no novo pedido. Isso permite reduzir a necessidade de reexplicar o
projeto, procurar decisões anteriores e refazer investigações cujo resultado
continua válido. Não elimina a conferência de fatos que podem ter mudado.

Não foi cronometrado o esforço humano evitado. Um exemplo puramente condicional:
se cada retomada normalmente exige **5 minutos de explicação**, e conferir a
memória leva **1 minuto**, o ganho é **4 minutos por retomada**. Em 20 retomadas
semanais, seriam **80 minutos por semana**. Esses tempos precisam ser medidos
no uso real antes de se tornarem uma estimativa pessoal.

Redução de erros e de retrabalho é outro benefício possível, mas exige contar
restrições esquecidas, fatos desatualizados e correções em tarefas comparáveis.
Passar testes de persistência não mede essa redução.

## Melhorias com maior potencial

1. **Recuperação seletiva desde o início.** Um resumo operacional curto pode
   orientar a busca das restrições e fontes necessárias. A redução de 84% a 91%
   medida no texto de `Resume` justifica avaliar esse caminho, sem assumir
   equivalência de informação com a nota inteira.
2. **Evitar duplicação de contexto.** Não repetir skill, referências e notas
   completas quando já estão disponíveis e atuais. No exemplo longo, cada
   resposta completa adicional introduz mais 3.129 tokens de texto.
3. **Checkpoints proporcionais ao progresso.** Guardar decisões e resultados
   úteis; reconhecer a nota existente quando nada mudou. Criar registros
   repetidos aumenta a escrita e encarece recuperações futuras.
4. **Medir o saldo por tipo de tarefa.** Separar tarefas curtas, retomadas após
   vários dias, compactações e delegações. Um resultado positivo num grupo não
   deve ser generalizado para os outros.

Esta análise adiciona documentação e um instrumento de medição. Não modifica
a lógica dos hooks, sua configuração, sua confiança ou a política de memória.

## Como repetir a medição

O [script de contagem](../tools/measure_context_tokens.py) aceita apenas as
tarefas explicitamente selecionadas e consulta os vínculos usados por `recall`.
Ele não altera as notas. O JSON de saída contém apenas agregados por número da
amostra; os textos continuam locais. As dependências são opcionais para esta
avaliação e não foram adicionadas ao runtime da skill.

```sh
uv run --no-project --with tiktoken==0.12.0 --with ruamel.yaml==0.18.17 \
  python tools/measure_context_tokens.py \
  --vault '/caminho/privado/do/cofre' --project meu-projeto \
  --task tarefa-longa --task tarefa-curta \
  --output contagens.json
```

O script recusa sobrescrever um arquivo existente. Os números publicados estão
em [token-measurements-2026-11-15.json](token-measurements-2026-11-15.json).
As notas privadas não acompanham esse arquivo: é possível reproduzir o método
com outras notas, mas os valores dependerão do conteúdo escolhido. A amostra de
duas notas do mesmo projeto não representa todos os projetos nem todos os modelos.

Para medir poupança líquida, o próximo experimento deve executar as mesmas
tarefas de continuação em sessões independentes, com e sem OBIA, e repetir os
ensaios. Registrar consumo real de entrada e saída, cache, chamadas de
ferramentas, tempo, qualidade e restrições preservadas; incluir a criação e
manutenção dos checkpoints. O [plano de avaliação](evaluation.md) descreve os
cenários funcionais que devem acompanhar essa comparação.
