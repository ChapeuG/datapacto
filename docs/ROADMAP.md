# Roadmap do datapacto

Este documento diz o que falta fazer e em que ordem. O porquê de cada peça está na [visão do projeto](VISAO.md);
aqui fica só o trabalho. Não há datas: os marcos estão em ordem de execução, e cada um entrega algo utilizável sozinho.

## A ideia, em uma linha

A pessoa entrega uma DDL ou um arquivo. O datapacto transforma isso num data contract (`.odcs.yaml`), confere se o
contrato segue as regras de nomenclatura e tipagem da empresa, gera a pipeline e guarda as regras de qualidade e os
SLAs, que passam a ser cobrados a cada carga.

Os marcos 1 a 3 fecham essa ideia. Os marcos 4 em diante são a expansão (catálogo, monitoria, outras ferramentas).

### O que a primeira versão pública promete

A promessa central é **validar o contrato contra as regras da empresa** (`datapacto validate`, no CI). Isso serve a
qualquer empresa que use ODCS, com qualquer stack.

A geração de pipeline é o **runtime de referência**: funciona para quem tem a mesma arquitetura (origem JDBC, raw em
JSON no S3, staging em Delta, EMR e Glue). Quem tem outra arquitetura usa a validação e o registro, e não a pipeline.

## Onde estamos

| Camada | Situação | O que falta, olhando o código |
|---|---|---|
| Escrever o contrato (Studio e CLI) | Existe | O contrato gerado da DDL traz só o schema; dono, SLA e qualidade são preenchidos à mão, sem sugestão. |
| Gerar a ingestão e a transformação | Existe | A transformação é um projeto de código por tabela, com os utilitários copiados em cada um. |
| Rodar a ingestão (orquestrador) | Existe | Só origem JDBC. Uma entrada por arquivo (CSV, Parquet, Avro) gera contrato, mas não pipeline. |
| Validação | Parcial | Nomenclatura, tipagem e glossário estão fixos em `standards/` (`nomenclatura.py`, `tipagem.py`, `glossary.py`). Não existe um comando que só valide o contrato. |
| Conferir o dado contra o contrato | Não existe | `pipeline.py` não compara o schema lido com o do contrato, e `catalog.py` recria a tabela quando o schema muda. |
| Registro dos contratos e artefatos | Parcial | `publish.py` envia só o `ingestion.yml` para o S3. O contrato, a transformação e as regras de qualidade não são guardados, e não há versão. |
| Métricas de cada carga | Parcial | O orquestrador escreve o resultado no log. `TableResult` não guarda a contagem de linhas, e o resultado das regras de qualidade se perde ao fim da carga. |
| Qualidade e SLA | Parcial | Três regras executadas (`notNull`, `unique`, `rowCount`), só antes da raw. O `slaProperties` está no contrato, mas nenhum código o lê. |
| Publicar em monitoria, catálogo e BI | Plano | Nenhum código. |

As lacunas de projeto aberto (licença, exemplo que roda, nome do pacote, dependências pesadas) foram fechadas no M0.

## Ordem dos marcos

```
M0 Pronto para abrir ─▶ M1 Regras da empresa ─▶ M2 Registro e versões ─▶ M3 Eventos de carga e SLA
                                                                              │
                        M6 Outras ferramentas ◀─ M5 AWS ◀─ M4 Página de catálogo e saúde
```

A ordem segue uma regra: cada marco só depende dos anteriores. O M3 vem antes de qualquer tela ou publicador de
monitoria porque sem evento de carga gravado não há o que mostrar.

---

## M0 — Pronto para abrir ✅

Objetivo: uma pessoa de fora clona o repositório e vê o fluxo funcionar em poucos minutos.

- [x] Adicionar o `LICENSE` (Apache 2.0) e tirar o "a definir" do README.
- [x] Renomear o pacote `framework` para `datapacto` (imports, `pyproject.toml`, testes).
- [x] Trocar os padrões herdados do CLI por valores neutros ou obrigatórios.
- [x] Mover `langchain`, `langgraph`, `openai`, `pandas` e `pyarrow` para extras (`[llm]`, `[amostra]`); a instalação básica fica só com o caminho sem LLM.
- [x] Rever o laço Validator → Fixer: se a geração é por template, erro de compilação é defeito do template e deve falhar no teste, não ser corrigido em tempo de execução.
- [x] Criar um exemplo completo em `examples/`: uma DDL, o contrato gerado, o `ingestion.yml` e a transformação.
- [x] Criar um ambiente de demonstração com Docker (Postgres com dados + Spark local) para rodar a ingestão do exemplo.
- [x] Escrever o `CONTRIBUTING.md` e os modelos de issue e de PR.
- [x] Incluir o exemplo no job `contracts` do CI (hoje o lint não roda em nenhum arquivo, porque só existe o template).
- [x] Dizer no README o que funciona com qualquer stack (validação) e o que exige a arquitetura de referência (pipeline).

Pronto quando: `git clone`, três comandos do README e a tabela de exemplo está na raw local.

Como ficou:

- `--github-org` e `--codecommit-transformation` não têm mais default: sem eles, o projeto sai sem remote e sem o
  pipeline de espelho. O pipeline de espelho virou um workflow neutro (OIDC, `ubuntu-latest`).
- O LangGraph saiu: o fluxo é uma sequência fixa de etapas (`graph.py`), sem o Fixer e sem `--max-iterations`.
  Projeto que não compila sai com status de erro e código de saída 1.
- O orquestrador roda sem AWS: secrets `env:` e `file:`, raw em `file:///` e `--skip-catalog`.
- O CI gera o exemplo com a instalação básica e falha se `examples/loja/saida` estiver desatualizado; o job `demo`
  roda a ingestão com Docker e confere a raw.
- O gerador não roda `git init` quando a pasta de saída já está dentro de um repositório.

## M1 — Regras da empresa (rulebook)

Objetivo: cada empresa usa o próprio padrão sem alterar o código, e o dado real é conferido contra o contrato.
Fecha a camada **Validação**.

Antes de começar: decidir o que o contrato governa (ver [decisões](#decisões-que-travam-o-trabalho)).

- [ ] Definir o esquema do `rules/rulebook.yaml` (seção 7 da visão) e validá-lo ao carregar.
- [ ] Testar o esquema com dois padrões diferentes antes de fixá-lo: o atual (prefixo de natureza, em português) e um em inglês sem prefixo. Hoje o esquema está moldado pelo primeiro.
- [ ] Migrar `standards/nomenclatura.py`, `tipagem.py` e `glossary.py` para um rulebook de exemplo; o código passa a ler o arquivo.
- [ ] Adicionar as regras que hoje não existem: campos obrigatórios do contrato e da coluna, níveis de classificação, coluna `restricted` exige criptografia, convenção de partição.
- [ ] Criar o comando `datapacto validate --contract ... --rulebook ...`, com saída legível e em JSON, e código de saída diferente de zero quando há erro. Serve para o CI de quem usa.
- [ ] Fazer cada erro dizer a regra quebrada e como corrigir.
- [ ] Avisar quando uma regra de qualidade do contrato não é executada: hoje `nullValues` no nível da tabela (com
  `arguments.properties`) é ignorado sem aviso; só vale dentro da coluna.
- [ ] Gravar no resultado a versão do rulebook usada.
- [ ] Trocar a etapa Validação do Studio para usar o rulebook.
- [ ] Sugerir regras de qualidade a partir da amostra (nulos, unicidade, faixas), usando o perfilador que já existe; a pessoa aceita ou descarta.
- [ ] Conferir o schema real contra o contrato a cada carga: levar colunas e tipos esperados no `ingestion.yml`, comparar com o que foi lido e falhar (ou avisar, conforme a severidade) quando uma coluna some, aparece ou muda de tipo.

Pronto quando: trocar o rulebook muda o resultado da validação sem tocar em nenhum arquivo `.py`, e uma coluna removida na origem faz a carga falhar com uma mensagem que cita o contrato.

## M2 — Registro e versões

Objetivo: um lugar só com tudo de cada contrato, por versão. Fecha a camada **Registro** e a parte "guarda as regras
de qualidade e os SLAs" da ideia.

- [ ] Decidir onde fica o registro (decisão em aberto 3 da visão). Recomendação: Git para escrever e revisar, S3 para o orquestrador ler.
- [ ] Criar o pacote `core/` com o modelo do contrato e do bundle, usado pelo gerador e pelo orquestrador.
- [ ] Gerar o bundle completo: `contract.odcs.yaml`, `validation.json`, `ingestion.yml`, `transformation/`, `quality.yml` e `sla.yml`.
- [ ] Normalizar em `quality.yml` todas as regras do contrato, inclusive as que o orquestrador ainda não executa.
- [ ] Trocar o `--publish-s3` por `datapacto publish`, que grava o bundle inteiro em `<dataset>/<tabela>/<versão>/`. Aceitar pasta local como destino, para testar sem AWS.
- [ ] Separar o registro por ambiente e definir como um contrato é promovido de dev para produção.
- [ ] Comparar com a versão ativa e detectar quebra de compatibilidade (coluna removida, tipo alterado, chave alterada); bloquear se a versão MAJOR não subir.
- [ ] Criar `datapacto diff` para mostrar o que mudou entre duas versões.
- [ ] Registrar os consumidores de cada contrato (quem usa e como avisar), para a quebra de compatibilidade ter destinatário.
- [ ] Fazer o orquestrador ler o `ingestion.yml` a partir do registro.

Pronto quando: publicar duas versões de um contrato deixa as duas no registro, e remover uma coluna sem subir a MAJOR é recusado.

## M3 — Eventos de carga e SLA

Objetivo: cada carga deixa um registro padronizado, e qualidade e SLA passam a ser cobrados. Fecha a camada
**Métricas de cada carga**.

Antes de começar: decidir se a transformação continua como código gerado ou vira configuração (ver
[decisões](#decisões-que-travam-o-trabalho)). A resposta define onde as regras de qualidade da staging rodam.

- [ ] Guardar em `TableResult` as linhas lidas por partição e o resultado de cada regra de qualidade.
- [ ] Definir o esquema do evento de carga (contrato, tabela, ambiente, partição, linhas, duração, status, regras).
- [ ] Gravar o evento como JSON no registro ao fim de cada tabela, inclusive quando a carga falha.
- [ ] Ler o `slaProperties` e calcular o atraso (freshness) em relação à frequência combinada.
- [ ] Ampliar as regras de qualidade executadas (hoje: `notNull`, `unique`, `rowCount`): valores aceitos, faixa numérica, expressão regular.
- [ ] Rodar as regras de qualidade na staging, que é o que o consumidor lê, e não só antes da raw.
- [ ] Criar uma interface de emissor de métricas, com a gravação em arquivo como primeira implementação.

Pronto quando: depois de uma carga, existe um arquivo que responde "quantas linhas, quanto tempo, quais regras passaram e se o SLA foi cumprido".

## M4 — Página de catálogo e saúde

Objetivo: ver os contratos e o estado das cargas sem nenhuma ferramenta externa. É a demonstração do projeto.

- [ ] Criar `datapacto docs`, que gera um site estático a partir do registro (como o `dbt docs`): pode ser publicado num bucket ou no GitHub Pages, sem servidor.
- [ ] Página de catálogo: busca por contrato, tabela, coluna, dono e classificação; página de cada data product.
- [ ] Página de saúde: últimas cargas, resultado das regras e atraso em relação ao SLA, lidos dos eventos do M3.
- [ ] Página de mudanças: histórico de versões com as quebras de compatibilidade destacadas (usa o `diff` do M2).
- [ ] Ciclo de vida do contrato: `draft`, `active`, `deprecated`, `retired`.
- [ ] Depois, se houver demanda: as mesmas telas dentro do Studio.

Pronto quando: um comando gera um site que mostra todos os contratos do registro e o estado da última carga de cada um.

## M5 — AWS

Objetivo: o mesmo catálogo e a mesma monitoria dentro da AWS. Primeiro código da camada **Publicar**.

- [ ] Definir a interface `Publisher` (`plan` e `apply`) e o registro de plugins por *entry points*.
- [ ] Ler o `platform.yaml` por ambiente.
- [ ] Gerar os artefatos neutros `catalog.json` e `monitors.yml` no bundle.
- [ ] Publicador Glue Data Catalog: descrição da tabela e das colunas, parâmetros do contrato.
- [ ] Emissor e publicador CloudWatch: métricas da carga, alarmes de atraso, volume e falha, dashboard por data product.
- [ ] Comandos `datapacto publish --plan` e `--apply`; só alterar recursos marcados com o `contract.id`.
- [ ] Depois: Lake Formation (LF-tags por classificação) e SageMaker Catalog.

Pronto quando: `plan` mostra o que vai mudar, `apply` aplica, e aplicar duas vezes não duplica nada.

## M6 — Outras ferramentas e comunidade

Objetivo: funcionar com o que a empresa já usa, e permitir que terceiros criem publicadores.

- [ ] Publicadores Datadog, Grafana e Quick Suite.
- [ ] Publicador OpenMetadata ou DataHub, para quem já tem catálogo.
- [ ] Notificações (Slack, Teams, e-mail) para publicação, quebra de compatibilidade e falha de qualidade, enviadas aos consumidores registrados no M2.
- [ ] Entrega por Terraform, além da chamada direta à API.
- [ ] Guia "como escrever um publicador", com um plugin de exemplo.
- [ ] Publicar os pacotes no PyPI e criar o site de documentação.
- [ ] Mais tarde: provedores GCP e Azure, linhagem.

---

## Decisões que travam o trabalho

| Decisão | Trava | Recomendação |
|---|---|---|
| Licença | M0 | Apache 2.0, a mesma do ODCS. |
| O que o contrato governa: a tabela de origem, a raw ou a staging | M1 | A staging, que é o que o consumidor lê. A origem entra como mapeamento (`physicalName`), e as regras de qualidade valem para a saída. |
| Uma instalação atende vários times com rulebooks diferentes | M1 (esquema) | Um rulebook por instalação agora; deixar o campo `dominio` previsto no esquema. |
| Onde fica o registro (S3, Git ou os dois) | M2 | Git para escrever e revisar; S3 para o orquestrador ler. |
| Transformação como código gerado ou como configuração lida por um motor | M3 | Configuração, como já é a ingestão: um `transformation.yml` e um motor instalado no cluster. Corrigir um utilitário deixa de exigir regerar todos os projetos. O código gerado fica como opção de exportação. |
| Visão própria no Studio ou em site estático | M4 | Site estático primeiro; o Studio em Streamlit não é um catálogo para vários usuários. |
| Publicadores por API direta ou Terraform | M5 | API direta no M5; Terraform no M6. |

## Fora do escopo por enquanto

- Competir com o `datacontract-cli` em `lint`, `import` e `export`: o contrato continua ODCS puro e compatível com ele.
- Catálogo com vários usuários, login e controle de acesso: quem precisa disso usa OpenMetadata, DataHub ou o catálogo da nuvem, alimentados pelos publicadores.
- Extração de regras de PDF, XLSX ou DOCX por LLM: o rulebook é escrito em YAML a partir de um modelo. Volta à fila se aparecer demanda.
- Recursos novos nos templates Scala: o que existe continua funcionando, e o trabalho novo vai para o PySpark.
- Agendamento (Airflow, Step Functions): o orquestrador roda uma carga; quem agenda é a empresa.
- Fontes que não são JDBC (arquivos, APIs, streaming) no orquestrador.
