# OBIA

**Memória de tarefas para agentes de IA, em notas Markdown conectadas no Obsidian.**

[English](README.md) · [Skill](skills/obia/SKILL.md) · [Comandos](skills/obia/references/commands.md)

A OBIA registra o contexto que vale preservar: objetivo, restrições, decisões,
fontes, hipóteses, dúvidas e próximos passos. Em outra sessão, o agente recupera
apenas as notas relevantes, verifica o que precisa de confirmação e continua.

O agente escolhe o que registrar e quais relações fazem sentido. Um utilitário
Python valida os dados, grava Markdown, mantém versões anteriores e limita o
contexto devolvido na recuperação. O Obsidian exibe as notas, links e grafo;
não precisa estar aberto para a gravação funcionar.

## O que esta versão entrega

- Uma nota atual por tarefa, organizada por projeto.
- Ligações com justificativa entre notas existentes.
- Separação entre fatos, decisões, hipóteses e correções, com referências às fontes.
- Busca por palavras e recuperação com limite de caracteres.
- Proteção contra sobrescritas concorrentes pelo utilitário e histórico local.
- Edição parcial que preserva seções humanas, propriedades e comentários YAML.
- Instalador público com um cofre separado por projeto, incluindo worktrees.
- Python 3.10+ e ruamel.yaml, sem APIs pagas ou plugins de Obsidian.
- Formato Agent Skills e instruções de instalação para Codex e Claude Code.

**Economia de tokens e redução de alucinações são objetivos ainda não medidos.**
A skill não recupera o que nunca foi salvo, não amplia a janela do modelo e não
garante ativação automática antes de toda compactação. Ela mantém uma memória
externa que o agente precisa consultar e conferir.

## Instalar e começar

Clone o repositório fora do seu cofre privado:

```sh
git clone https://github.com/Enzoramo/OBIA.git
cd OBIA
```

Escolha uma pasta privada existente que receberá os cofres:

```sh
python3 install.py --host codex --vaults-root '/privado/Obsidian' --project '/trabalho/meu-app'
# Ou:
python3 install.py --host claude --vaults-root '/privado/Obsidian' --project '/trabalho/meu-app'
```

O instalador adiciona a skill, a dependência YAML e instruções de memória ao host.
Cada projeto novo recebe um cofre `OBIA - <projeto>`. Subpastas e worktrees reutilizam
o mesmo cofre do projeto. Abra a pasta criada como cofre no Obsidian.

Para atualizar, repita os mesmos caminhos com `--update`. A versão anterior fica
em backup; os registros de projetos, memórias e demais instruções são preservados.
Veja [instalação e migração](docs/installation.md) para configurar caminhos,
Windows e instalações existentes em `~/.codex/skills`.

No Codex você pode chamar `$obia`; no Claude Code, `/obia`. O host precisa carregar
as instruções e permitir acesso aos arquivos. Outros agentes podem ler o mesmo
`SKILL.md` e usar o utilitário com acesso ao sistema de arquivos.

## Experimentar com dados fictícios

```sh
python3 -m pip install -r skills/obia/requirements.txt
python3 examples/demo.py
python3 -m unittest discover -s tests -v
```

A demonstração cria um cofre temporário, grava duas tarefas conectadas e recupera
o contexto em outro processo. Nenhuma nota pessoal é usada. Os testes verificam
o armazenamento e a recuperação; não medem a qualidade de raciocínio de uma IA.

## Como a memória fica organizada

```text
meu-cofre/OBIA/
├── index.md
├── projects/meu-app/
│   ├── index.md
│   └── tasks/
│       ├── escolha-do-armazenamento.md
│       └── cache-offline.md
└── .history/meu-app/cache-offline/<sha-anterior>.md
```

Os índices ajudam a localizar tarefas. A nota contém o estado atual e as fontes.
O histórico guarda versões anteriores, mas fica fora da busca normal. Ao retomar,
o agente começa pelo projeto e pela tarefa relevantes, em vez de ler todo o cofre.
Notas que ultrapassem o limite de recuperação são sinalizadas como omitidas.

**O repositório da skill é público; suas memórias continuam locais.** A OBIA não
publica nem sincroniza o cofre. Quando um agente lê as notas, o conteúdo pode ser
processado pelo provedor desse agente conforme as configurações dele.

Fontes devem ser verificadas; uma memória repetida não vira evidência nova. Não
guarde segredos. O histórico também retém textos removidos de notas atuais.
Use um escritor por vez entre dispositivos sincronizados: um bloqueio local não
coordena gravações simultâneas por iCloud ou outros serviços.

Mais detalhes no [README em inglês](README.md), no
[formato das notas](skills/obia/references/memory-format.md) e nos
[cenários de avaliação](docs/evaluation.md). Licença [MIT](LICENSE).
