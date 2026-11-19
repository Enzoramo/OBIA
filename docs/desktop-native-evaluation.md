# OBIA no app Codex: integração e medição nativa — 2026-11-19

O fluxo síncrono foi implementado, instalado e usado no chat existente do app.
Neste experimento com subagentes reais, consumiu **868.395 tokens**, contra
**1.336.446 no baseline corrigido: redução numérica de 35,0%**, incluindo todo o
planejamento e os checkpoints. Em relação ao fluxo manual anterior, foram 28,7%
menos tokens.

**Economia diária com qualidade equivalente não está demonstrada.** O contrato
de avaliação deixou ambígua a obrigatoriedade de metadados do formato. Os três
braços finais tiveram o mesmo placar, mas não passaram no avaliador congelado.
Além disso, os subagentes não receberam os eventos de hooks necessários para
medir o Stop do app. O usuário escolheu manter apenas subagentes e registrar essa
limitação; nenhum chat adicional de barra lateral foi criado.

## O que mudou no produto

[`desktop.py`](../skills/obia/scripts/desktop.py) usa a ferramenta de terminal
síncrona já disponível no app. `recover` reúne vínculo explícito, roteamento do
projeto e recuperação com fontes; `checkpoint` reúne gravação/patch, recibo de
persistência e ack; `verify` lê/confirma o SHA existente sem regravar.

A skill instalada passou a preferir esse [fluxo](../skills/obia/references/desktop.md)
no Codex desktop. Ele preserva alterações humanas, detecção de conflitos por SHA
e a distinção entre gravação e confirmação do turno. Falhas após uma gravação
retornam o recibo salvo para evitar reescrever apenas para repetir o ack.

O helper não chama modelos, lê conversas ou fabrica eventos. Os bytes de
`hooks.py`, `hooks.json` e `config.toml` permaneceram iguais aos anteriores; seus
hashes estão no relatório de dados. O ack continua limitado ao último turno
realmente observado. Uma continuação delegada pode exigir nova verificação no
Stop seguinte. Não foi introduzida uma exceção para reaproveitar ack antigo.

Esta adaptação não é o modo de saída estruturada do estudo anterior. As
interfaces disponíveis no chat atual não expõem o callback necessário para
persistir aquela saída antes do Stop. Por isso, o checkpoint ainda exige uma
chamada síncrona do modelo, cujo custo entra na medição.

## Desenho e contabilidade

O [protocolo](desktop-native-protocol.md) e os
[19 critérios independentes](../tools/desktop_eval_cases.py) foram congelados
antes das implementações. Três braços receberam cópias isoladas do mesmo commit
`af879ad`: baseline sem memória de tarefa, OBIA manual de `6c7ba8e` e OBIA
síncrono. Todos os executores usaram o modelo observado `gpt-6-astra`, esforço
`xhigh`, pelo Codex Desktop, sem overrides.

O trabalho foi implementar um renderizador de relatórios reais do projeto. Cada
braço teve dois turnos de planejamento, incluindo uma correção aceita para
calcular custos a partir do ledger, e uma retomada em agente novo. O baseline
recebeu seu próprio histórico visível; os braços OBIA receberam suas próprias
notas. Os agentes puderam consultar fontes atuais e executar testes.

Cada braço OBIA criou uma nota inicial, atualizou-a após a correção e reconciliou
a conclusão: **três checkpoints por braço**. Planejamento, redação, skill,
recuperação, comandos, recibos e checkpoint final estão incluídos nos totais.
Não atribuímos um custo causal isolado ao checkpoint: as fases abaixo também
incluem trabalho útil de planejamento e implementação.

O [leitor de uso](../tools/desktop_usage.py) verifica a identidade da sessão,
fechamento dos turnos e consistência dos contadores. Usa o último total
cumulativo válido; não soma snapshots repetidos nem soma cache/raciocínio
novamente. Todos os oito executores medidos têm medição completa. Isso verifica
a contabilidade, não a qualidade ou a execução do Stop.

## Resultados inclusivos

| Fluxo | Planejamento, incluindo checkpoints | Retomada, incluindo manutenção | Total de tokens |
|---|---:|---:|---:|
| Baseline corrigido | 423.300 | 913.146 | **1.336.446** |
| OBIA manual | 654.798 | 562.867 | **1.217.665** |
| OBIA síncrono | 435.416 | 432.979 | **868.395** |
| Baseline original, input afetado | 423.300 | 1.243.121 | 1.666.421 |

O baseline corrigido reutiliza explicitamente o planejamento original. Os braços
OBIA também são os mesmos, sem novas tentativas. A diferença numérica principal
é de 468.051 tokens; ela não recebe o rótulo de sucesso com qualidade aprovada.

| Medida inclusiva | Baseline corrigido | OBIA manual | OBIA síncrono |
|---|---:|---:|---:|
| Entrada não cacheada | 114.498 | 56.709 | 50.146 |
| Entrada cacheada | 1.203.968 | 1.135.616 | 795.648 |
| Saída | 17.980 | 25.340 | 22.601 |
| Chamadas de ferramentas pelo modelo | 19 | 24 | 18 |
| Execuções de comandos | 24 | 37 | 27 |
| Soma das durações dos turnos | 442,495 s | 593,869 s | 569,980 s |

Cache é subconjunto da entrada; raciocínio é subconjunto da saída. Duração é a
soma dos turnos desses executores, não o tempo total de desenvolvimento. O fluxo
síncrono gerou mais saída e demorou mais que o baseline corrigido. Não há
conclusão de ganho de velocidade ou economia financeira. Chamadas de ferramenta
e execuções de comandos são medidas distintas: uma chamada pode conter vários
comandos.

## Qualidade: placar original preservado

| Implementação | Avaliador congelado | Diagnóstico com formato explícito | Testes executados pelo agente |
|---|---:|---:|---|
| Baseline original | 19/19 | 19/19 | 17 testes |
| Baseline corrigido | 8/19 | 19/19 | 21 testes |
| OBIA manual | 8/19 | 19/19 | 18 testes |
| OBIA síncrono | 8/19 | 19/19 | 15 testes do renderizador + 5 do exportador |

Os onze casos divergentes usam fixtures mínimas sem `schema` e `workflow`.
Ambos os relatórios reais contêm esses campos, mas o pedido congelado não dizia
se eram obrigatórios. O baseline original aceita sua ausência; o baseline
corrigido e ambos os braços OBIA a rejeitam. Todos passam nas verificações com
os dois relatórios reais.

O diagnóstico acrescentou somente `schema: 1` e
`workflow: "integrated_handoff"` às fixtures, sem nova chamada de modelo ou
alteração das implementações. Os quatro passam 19/19 nessa análise. Ela ajuda a
localizar a diferença, mas **não substitui o placar congelado**. A condição
primária de qualidade permanece não satisfeita/inconclusiva, e
`primary_success` permanece `false`.

A auditoria independente conferiu os sete agentes comparativos: fontes,
correção aceita, incertezas, testes realmente executados, escopo dos arquivos e
reconciliação das notas. Os seis checkpoints batem com seus SHAs e mantêm o
estado pertinente. Todos os arquivos protegidos permaneceram intactos; cada
retomada adicionou somente os dois arquivos permitidos. Essa auditoria semântica
não substitui a aceitação funcional. A mesma escolha de formato na retomada sem
OBIA tampouco permite atribuir a divergência a uma perda causada pela memória.

## Correção do baseline e custos preservados

A primeira exportação do histórico reteve dois blocos opacos
`encrypted_content`, somando 2.524 caracteres. Não eram evidência técnica legível.
Não os deciframos nem afirmamos conhecer seu efeito causal no consumo.

O [exportador corrigido](../tools/export_desktop_history.py) preserva mensagens e
saídas de ferramentas em texto, incluindo o truncamento originalmente visível,
e exclui bootstrap, raciocínio e blocos opacos. O histórico limpo tem 152.437
bytes. O protocolo da correção foi comitado em `a2aba1c` antes de **uma única**
nova retomada baseline. Não houve repetição para perseguir um resultado melhor.
O código de trabalho anterior não foi entregue ao novo agente.

O baseline antigo continua no ledger, com input, custo, hash e placar próprios.
Somando os seis executores originais, o replay de 913.146 tokens e a calibração
de 46.640, houve **4.712.267 tokens nos oito executores medidos**. O planejamento
reutilizado conta uma vez nessa soma. Desenvolvimento, orquestração, revisão e
publicação pelo agente principal/revisor estão fora dela; esse valor não é o
custo total do projeto.

## Limites para o uso diário

- É um único cenário, sem repetições independentes suficientes para estimar
  variabilidade ou generalizar o percentual.
- O baseline recebe um histórico exportado em uma retomada nova. Isso não mede
  a continuação normal de um chat cujo prefixo já esteja em cache.
- Nenhum subagente recebeu diretamente SessionStart. Os acks dos braços OBIA
  têm turno `0` e identidade `null`; isso não comprova Stop. Não houve eventos
  simulados ou alteração de configuração/confiança para preencher a lacuna.
- A integração foi usada no chat principal e os 15 arquivos instalados foram
  conferidos. Esse uso real comprova disponibilidade e persistência local,
  não fornece um controle pareado de custo diário.
- O contrato de formato precisa ser explicitado antes de uma nova avaliação
  prospectiva. Não modificamos retrospectivamente o gate para declarar sucesso.

## Evidências e reprodução

O [JSON de medições](desktop-native-measurements-2026-11-19.json) contém os oito
totais, contadores separados, hashes das traces, fases reutilizadas, todos os
placares, auditoria e hashes dos checkpoints. Não publica conversas privadas,
bootstrap ou raciocínio. As evidências locais saneadas incluem os inputs em
texto, métricas, implementações isoladas e snapshots pertinentes das notas.

As contas podem ser refeitas diretamente do ledger público:

```python
import json
from pathlib import Path
r = json.loads(Path('docs/desktop-native-measurements-2026-11-19.json').read_text())
stages = {x['stage']: x['usage']['total_tokens'] for x in r['execution_ledger']}
baseline = stages['baseline/planning'] + stages['baseline-replay/resume']
obia = stages['obia/planning'] + stages['obia/resume']
assert sum(stages.values()) == 4_712_267
print(baseline, obia, 100 * (baseline - obia) / baseline)
assert r['primary_success'] is False
```

Validação do produto e das ferramentas: **151 testes locais passaram**, mais o
demo local. A matriz de CI executa Python 3.10/3.12 em Linux, macOS e Windows.
Os resultados do trabalho dos agentes acima são separados desses testes do
repositório.
