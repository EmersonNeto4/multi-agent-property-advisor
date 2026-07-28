# Sistema Multi-Agente de Recomendação de Imóveis

Sistema Multi-Agente (SMA) em Python + AutoGen que recomenda imóveis a partir
de um pedido em linguagem natural. Cinco agentes especializados (Planner,
Location, Property, Data Analyst, Evaluator) colaboram em Round-Robin,
usando **CSP**, **A\*** e **KNN**, com o LLM `llama-3.3-70b-versatile` via
Groq API e dados reais da API do Idealista.

A aplicação é composta por uma **API REST (FastAPI)** que expõe o sistema
multi-agente, e um **frontend próprio (HTML/CSS/JS puro)** que a consome.
O Location Agent usa **RAG com embeddings semânticos** para interpretar
descrições de ambiente em linguagem natural (ver secção 6).


## 1. Requisitos

- Python 3.10+
- Uma API key da Groq (grátis em [console.groq.com/keys](https://console.groq.com/keys))
- Credenciais da API do Idealista (key + secret)

Instalar dependências:

```bash
pip install -r requirements.txt
```

Para correr os testes automatizados, instala também as dependências de
desenvolvimento (`requirements-dev.txt` inclui `requirements.txt` + `pytest`):

```bash
pip install -r requirements-dev.txt
```

Criar um ficheiro `.env` na raiz do projeto (usa `.env.example` como
template):

```
GROQ_API_KEY=a_tua_chave
IDEALISTA_API_KEY=a_tua_chave
IDEALISTA_API_SECRET=o_teu_secret
```


## 2. Executar a aplicação

```bash
uvicorn api.main:app --reload
```

A interface fica acessível em **http://localhost:8000** — a mesma porta
serve o frontend estático e a API (`/api/...`).

> **Primeiro arranque:** na primeira query que descreva um ambiente
> (ex: "zona sossegada"), o modelo de embeddings do RAG (~420 MB) é
> descarregado do Hugging Face e fica em cache local
> (`~/.cache/huggingface`). Só acontece uma vez por máquina; nos
> arranques seguintes é carregado a partir da cache. O arranque do
> `uvicorn` em si não é afetado — o modelo é carregado à primeira
> utilização, não no startup (ver secção 6).


## 3. Como usar

Escreve o pedido em linguagem natural, por exemplo:

> "Quero um T2 em Lisboa com orçamento até 400k, perto do Hospital Santa Maria"

Os resultados aparecem em separadores: Recomendações Finais, Análise KNN,
Imóveis Encontrados, Localizações e Preferências Extraídas. Cada separador
mostra a resposta final do respetivo agente, com o histórico completo de
mensagens disponível numa secção expansível.

Se o Planner não conseguir extrair um orçamento, o sistema pára e pede-o
explicitamente antes de continuar.


## 4. Endpoints da API

| Método | Rota              | Descrição                                             |
|--------|-------------------|--------------------------------------------------------|
| POST   | `/api/recommend`  | Executa o sistema multi-agente para uma query          |
| GET    | `/api/health`     | Health check (app + model client)                      |
| GET    | `/api/locations`  | Lista de localizações disponíveis (autocomplete)        |

Documentação interativa (Swagger) em `/docs`.


## 5. Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Nenhum teste faz chamadas reais à Groq, ao Idealista ou ao Hugging Face, e
todos correm sem `.env` nem chaves de API (é o que o GitHub Actions da
Fase 3 vai executar):

- `tests/test_api.py` — endpoints, via `fastapi.testclient.TestClient`. O
  sistema multi-agente é mocked e o `model_client` do lifespan é
  substituído via `app.dependency_overrides`.
- `tests/test_semantic_search.py` — módulo de retrieval, com o modelo de
  embeddings mocked (sem download).
- `tests/test_location_search.py` — integração do retrieval em
  `find_best_locations`.

Há ainda um teste de integração com o **modelo de embeddings real**,
marcado `slow` e excluído da execução por omissão (`pytest` sozinho já não
o corre). Para o executar explicitamente — descarrega o modelo se ainda
não estiver em cache:

```bash
pytest -m slow
```


## 6. RAG — retrieval semântico no Location Agent

O Location Agent traduz descrições de ambiente em linguagem natural
("zona sossegada", "perto do oceano") para localizações concretas. Até à
Fase 1 isso era feito por um dicionário de ~18 palavras-chave
hardcoded: qualquer sinónimo fora da lista falhava em silêncio — "pacato"
não encontrava "tranquilo", "perto do oceano" não encontrava "costeiro".

A Fase 2 substituiu esse mapeamento por **retrieval semântico**:

- Cada uma das 42 localizações tem uma descrição textual em português
  (`data/portugal_locations_descriptions.json`), gerada por template
  determinístico a partir do dataset — regenerável com
  `python scripts/generate_descriptions.py`.
- Essas descrições são embutidas com o modelo multilingue
  **`paraphrase-multilingual-MiniLM-L12-v2`** (`sentence-transformers`),
  escolhido após benchmark contra `multilingual-e5-small` e
  `mpnet-base-v2`, e ficam numa matriz **numpy** em memória. Com 42
  vetores, a pesquisa é uma multiplicação matriz-vetor (a Fase 2 usava
  ChromaDB aqui — ver
  [docs/FASE2.5_DECISOES.txt](docs/FASE2.5_DECISOES.txt)).
- A descrição de ambiente do utilizador é comparada por similaridade de
  cosseno com as 42 descrições, e o resultado alimenta o
  `characteristics_score` de cada localização.

O que **não** mudou: a resolução de nomes de sítios. Se o utilizador diz
"Algarve" ou "Lisboa", isso continua a ser um filtro geográfico
exato/fuzzy — o RAG só interpreta o *ambiente*, não a geografia.

Se o modelo não estiver disponível (sem rede e sem cache), o sistema
degrada para ignorar a descrição de ambiente em vez de falhar.

O efeito, com duas queries iguais em tudo menos no ambiente pedido:

| Query (Algarve, T2, 300k) | Top 3 |
|---|---|
| ...zona **sossegada e autêntica** | Olhão, **Tavira**, Albufeira |
| ...zona **vibrante com vida noturna** | **Albufeira**, Olhão, Faro |

Nenhuma destas palavras existia no mapeamento antigo — com ele, as duas
queries devolveriam a mesma ordenação. As decisões, o benchmark completo
e os problemas encontrados estão em
[docs/FASE2_DECISOES.txt](docs/FASE2_DECISOES.txt).


## 7. Notas rápidas

- Chamadas ao Groq podem ocasionalmente dar rate-limit — a API devolve
  `503` nesse caso, com uma mensagem a pedir para tentar novamente.
- Nunca commitar o `.env` (já está no `.gitignore`) — as chaves de API são
  segredos, não valores por defeito no código.
- O modelo de embeddings ocupa memória assinalável quando carregado
  (~800 MB de RSS, sobretudo por causa do runtime do PyTorch). Não é
  problema em desenvolvimento local, mas é um constrangimento conhecido
  para o deploy da Fase 4 em free tiers — as opções de mitigação estão
  analisadas na secção 5 de
  [docs/FASE2_DECISOES.txt](docs/FASE2_DECISOES.txt).
- A API do Idealista devolve `406` de forma consistente (bloqueio externo,
  diagnosticado na secção 10 de
  [docs/FASE1_DECISOES.txt](docs/FASE1_DECISOES.txt)). O sistema trata a
  falha e devolve 0 imóveis; o pipeline de agentes e o RAG funcionam
  normalmente.


## 8. Estrutura do projeto

```
api/            # FastAPI: endpoints, schemas Pydantic, lifespan do model_client
frontend/       # HTML/CSS/JS puro, servido pela própria API
agents/         # Definição dos 5 agentes AutoGen
tools/          # CSP, A*, KNN, cliente Idealista, retrieval semântico, dados
models/         # UserPreferences (Pydantic)
utils/          # Configuração e criação do model client
scripts/        # Geração das descrições das localizações (dados do RAG)
tests/          # Testes automatizados (pytest)
main.py         # Orquestração do team (run_property_recommendation_system)
docs/           # Registo de decisões técnicas por fase + relatório académico (PDF)
```


## 9. Roadmap

Este projeto segue um roadmap em 4 fases, focado em demonstrar competências
de engenharia/deployment além do algoritmo de recomendação em si:

- **Fase 1 (concluída)** — desacoplar front-end e back-end com FastAPI +
  frontend próprio. Ver [docs/FASE1_DECISOES.txt](docs/FASE1_DECISOES.txt)
  para as decisões técnicas tomadas (secção 11 regista as correções de
  dívida técnica feitas depois da Fase 1, antes de arrancar a Fase 3).
- **Fase 2 (concluída)** — substituído o mapeamento por keywords no
  Location Agent por RAG com embeddings semânticos — ver secção 6 e
  [docs/FASE2_DECISOES.txt](docs/FASE2_DECISOES.txt), que inclui o
  benchmark de modelos e o consumo de memória medido (relevante para a
  Fase 4).
- **Fase 3** — Dockerização com docker-compose + CI/CD via GitHub Actions.
  A estrutura atual (API e frontend como componentes separados, config via
  `.env`, testes em `tests/` com os lentos já excluídos por omissão) já
  está preparada para isto sem alterações estruturais.
- **Fase 4** — Deploy em Render/Railway com demo live.


## 10. Atribuição

Projeto desenvolvido originalmente em coautoria com **Gonçalo Bento**, no
âmbito da unidade curricular de IARP (2025/2026), FCTUC. Este repositório
é a evolução individual do trabalho conduzida por **Emerson Neto** a partir
do fim da Fase 1 (migração Streamlit → FastAPI), incluindo as fases
seguintes do roadmap.

O relatório académico original está em
[docs/Relatorio_SMA_Recomendacao_de_Imoveis.pdf](docs/Relatorio_SMA_Recomendacao_de_Imoveis.pdf)
(dados pessoais do Gonçalo — número de estudante e email — redigidos antes
de o repositório se tornar público; a autoria de ambos mantém-se visível).
