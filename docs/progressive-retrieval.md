# Recuperação progressiva — 18 de novembro de 2026

OBIA agora recupera primeiro o núcleo operacional das notas longas e permite
buscar seções ou fontes específicas depois. No exemplo sintético longo, o pacote
mais as fontes necessárias caiu de **1.377 para 545 tokens de texto (60,4%)**.
Isso mede o texto devolvido pelas ferramentas, não o consumo total de uma IA.

## Comportamento

`recall --view brief` conserva, sem truncar, Resume, Constraints, Decisions,
Corrections e o preâmbulo. Inclui SHA da nota completa, seções omitidas e IDs das
fontes mencionadas. Links da tarefa conhecida viram localizadores; é necessário
ler a nota vinculada antes de usar sua evidência. Não há expansão automática para
outro projeto ou para notas pessoais.

A seleção é adaptativa: quando o pacote integral cabe sem omissões e ocupa menos
ou os mesmos caracteres, ele é devolvido com `view: full`. Isso evita criar uma
projeção e depois buscar fontes de uma nota já pequena. A decisão compara JSON
serializado em caracteres, sem adicionar um tokenizador ao runtime; não garante
o menor número de tokens para toda nota ou todo modelo.

Notas sem Resume ou com propriedades YAML adicionais preservam o conteúdo por
fallback integral. Se o núcleo não cabe no orçamento, aparece como `deferred`,
com `read_required: full`, ou como omitido se nem o localizador couber. A tarefa
principal deve ser lida integralmente antes de agir nesse caso. Seções humanas
adicionais aparecem na lista de omissões. O modo `full` continua sendo o padrão
da CLI/API para compatibilidade; SessionStart e bind pedem o modo adaptativo.

Exemplos a partir da pasta da skill instalada:

```sh
python3 scripts/obia.py recall --vault '/cofre' --project app --task fila --view brief
python3 scripts/obia.py read --vault '/cofre' --project app --task fila --section Facts --section Artifacts --expect-sha SHA
python3 scripts/obia.py read --vault '/cofre' --project app --task fila --source S1 --source S2 --expect-sha SHA
python3 scripts/obia.py read --vault '/cofre' --project app --task fila --if-changed SHA
```

`--expect-sha` impede misturar evidência de versões diferentes. `--if-changed`
retorna somente metadados quando o SHA coincide; serve para contexto que já está
presente, nunca para obter uma seção ainda não lida. `bind --known-sha SHA` permite
a mesma reutilização explícita. Nenhum deles produz um ack. SessionStart sempre
restaura a memória, inclusive após compactação; um recibo antigo não prova que o
modelo reteve o contexto. A validação de checkpoints por SHA, contador e turn_id
do Codex continua igual. Configuração e confiança dos hooks não precisam mudar.

## Medição reproduzível

O [benchmark](../tools/benchmark_progressive_recall.py) cria duas notas sintéticas
em um cofre temporário. Ambas têm o mesmo objetivo, duas restrições, uma decisão,
uma correção e a próxima ação. A longa acrescenta 16 registros históricos com
fontes próprias. Nenhum histórico privado, evento real de hook ou modelo é usado.

O baseline e a implementação consultam a mesma nota, sem links, com `limit=1` e
12.000 caracteres. O baseline integral cabe nos dois casos. O fluxo progressivo
inclui uma expansão das fontes referenciadas pelo núcleo quando a projeção é
breve. Verificações exigem seções essenciais completas, fontes recuperáveis e o
mesmo SHA; isso demonstra cobertura determinística, não qualidade de retomada
por um agente. As fontes são definições/locadores; verificar o conteúdo dos
artefatos citados continua sendo trabalho adicional.

Contagens com `o200k_base`, incluindo JSON e a quebra de linha final:

| Caso | Integral | Adaptativo + fontes do núcleo | Variação |
| --- | ---: | ---: | ---: |
| Nota curta: completa selecionada | 395 | 402 | +1,8% |
| Nota longa: projeção + fontes | 1.377 | 414 + 131 = 545 | −60,4% |
| Nota longa: projeção + leitura integral posterior | 1.377 | 414 + 1.317 = 1.731 | +25,7% |

Com `cl100k_base`, o fluxo longo custa 546 tokens, redução de 60,3%; o caso curto
continua em 402. A comparação inclui todo o JSON devolvido e a expansão, mas não
os argumentos das chamadas nem mensagens adicionais do protocolo.

As quatro instruções da skill/referências também foram reduzidas: **5.113 para
4.500 tokens (−12,0%)** em `o200k_base`; 5.104 para 4.490 em `cl100k_base`.
O baseline está no [relatório de 15 de novembro](token-measurements-2026-11-15.json).
As referências são carregadas conforme a operação; não é necessário ler todas
em cada retomada. Como comparação de primeira carga com uma cópia de todos esses
arquivos, instruções + fluxo longo passam de 6.490 para 5.045 tokens (−22,3%).
Essa soma não modela a repetição do contexto em várias requisições de uma IA.

Uma verificação condicional da nota longa custa 68 tokens, contra 1.317 de uma
nova leitura integral. Isso só evita repetição quando o conteúdo necessário já
está disponível; não substitui recuperação após perda de contexto.

O protótipo revelou dois custos: projeção + fontes encarecia a nota curta em
36,5%, e o crescimento das instruções anulava o ganho longo na primeira carga.
Isso motivou a seleção adaptativa e a revisão das instruções. O pequeno acréscimo
atual da nota curta vem do marcador `view: full`. Se muitos detalhes históricos
forem necessários, pedir o modo completo desde o início pode ser mais barato,
como mostra o caso negativo acima.

```sh
uv run --no-project --with tiktoken==0.12.0 --with ruamel.yaml==0.18.17 \
  python tools/benchmark_progressive_recall.py --output resultado.json
```

Execute da raiz do repositório e escolha um arquivo de saída inexistente. O
[relatório agregado](progressive-retrieval-measurements-2026-11-18.json) usa um
horário sintético fixo para tornar SHA e contagens reproduzíveis. Não é preciso
configurar um cofre pessoal ou credencial. As dependências de medição são opcionais.

O [piloto posterior com agentes reais](real-agent-evaluation.md) incluiu entrada,
saída, cache, chamadas e checkpoints: nesse fluxo de uma única retomada via CLI,
o consumo total aumentou, mantendo os critérios funcionais e de retenção. Não
avaliou a injeção automática dos hooks. Os números desta página continuam sendo
contagens do pacote, não economia total. Tokens de texto, tokens faturados e
trabalho humano são medidas distintas. O [plano de avaliação](evaluation.md)
descreve os cenários seguintes.
