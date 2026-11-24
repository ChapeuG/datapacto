# Como contribuir

Obrigado pelo interesse no datapacto. Este guia diz como preparar o ambiente, o que um PR precisa ter e onde fica
cada coisa. O que falta fazer, em ordem, está no [roadmap](docs/ROADMAP.md); o porquê de cada peça, na
[visão](docs/VISAO.md).

## Antes de abrir um PR

- **Mudança pequena** (correção, documentação, teste): abra o PR direto.
- **Mudança grande** (comando novo, formato novo de arquivo, mudança no contrato): abra uma issue antes, para
  combinar a ideia. Se ela estiver no roadmap, cite o marco.

## Ambiente

Python 3.10 ou mais novo. Os dois pacotes são instalados separadamente:

```bash
# Gerador: CLI e Studio. [all] traz LLM, leitura de amostras e a interface
pip install -e "packages/generator[all]" pytest

# Orquestrador: [dev] traz pytest e pyspark (os testes de Spark precisam de Java 17)
pip install -e "packages/orchestrator[dev]"
```

## Testes

```bash
cd packages/generator && python -m pytest tests
cd packages/orchestrator && python -m pytest
```

O CI roda os dois, o lint dos contratos de `examples/` e a demonstração com Docker (`examples/loja/demo`).
No Windows, os testes do orquestrador que gravam arquivos com Spark são pulados (exigem `winutils`); eles rodam
no CI.

## O que um PR precisa ter

- **Teste** para o comportamento novo ou para o defeito corrigido.
- **Template muda, exemplo muda**: se a mudança altera o que o gerador produz, gere o exemplo de novo e inclua a
  diferença no PR:

  ```bash
  datapacto generate --contract examples/loja/contracts/loja --output-dir examples/loja/saida \
      --naming-dir examples/loja/saida/naming
  ```

- **Documentação** atualizada quando muda um comando, uma opção ou um campo do contrato (`docs/MANUAL.md`, os
  READMEs dos pacotes e o `contracts/template.odcs.yaml`).
- **Nada de dados reais**: nomes de empresa, contas e buckets de nuvem, hosts, ARNs e dados pessoais não entram
  em código, exemplo, teste ou mensagem de commit. Use valores fictícios (`loja`, `exemplo.com`, `<conta>`).

## Onde fica cada coisa

| Pasta | O quê |
|---|---|
| `packages/generator/src/datapacto/` | Gerador: `cli.py`, `graph.py` (fluxo), `agents/` (uma etapa por arquivo), `templates/`, `standards/` (padrões de nomenclatura e tipagem), `ui/` (Studio) |
| `packages/orchestrator/src/ingestion/` | Orquestrador: `config.py` (formato do `ingestion.yml`), `pipeline.py`, `connectors/` (um por banco), `quality.py` |
| `contracts/` | Template do data contract |
| `examples/` | Exemplo que roda do início ao fim |
| `docs/` | Manual, visão e roadmap |

## Estilo

- Código, comentários, mensagens e documentação em português.
- Linhas de até 120 caracteres.
- Mensagem de commit no imperativo e curta (`Adiciona o conector Snowflake`), com o detalhe no corpo quando
  precisar.

## Licença

Ao contribuir, você concorda que o seu código seja distribuído sob a [licença Apache 2.0](LICENSE) do projeto.
