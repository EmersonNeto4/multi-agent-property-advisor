# Sistema Multi-Agente de Recomendação de Imóveis

Sistema Multi-Agente (SMA) em Python + AutoGen que recomenda imóveis a partir
de um pedido em linguagem natural. Cinco agentes especializados (Planner,
Location, Property, Data Analyst, Evaluator) colaboram em Round-Robin,
usando **CSP**, **A\*** e **KNN**, com o LLM `llama-3.3-70b-versatile` via
Groq API e dados reais da API do Idealista.

A aplicação é composta por uma **API REST (FastAPI)** que expõe o sistema
multi-agente, e um **frontend próprio (HTML/CSS/JS puro)** que a consome.


## 1. Requisitos

- Python 3.10+
- Uma API key da Groq (grátis em [console.groq.com/keys](https://console.groq.com/keys))
- Credenciais da API do Idealista (key + secret)

Instalar dependências:

```bash
pip install -r requirements.txt
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


## 5. Notas rápidas

- Chamadas ao Groq podem ocasionalmente dar rate-limit — a API devolve
  `503` nesse caso, com uma mensagem a pedir para tentar novamente.
- Nunca commitar o `.env` (já está no `.gitignore`) — as chaves de API são
  segredos, não valores por defeito no código.


## 6. Estrutura do projeto

```
api/            # FastAPI: endpoints, schemas Pydantic, lifespan do model_client
frontend/       # HTML/CSS/JS puro, servido pela própria API
agents/         # Definição dos 5 agentes AutoGen
tools/          # CSP, A*, KNN, cliente Idealista, dados de localização
models/         # UserPreferences (Pydantic)
utils/          # Configuração e criação do model client
main.py         # Orquestração do team (run_property_recommendation_system)
docs/           # Registo de decisões técnicas por fase
```


## 7. Roadmap

Este projeto segue um roadmap em 4 fases, focado em demonstrar competências
de engenharia/deployment além do algoritmo de recomendação em si:

- **Fase 1 (concluída)** — desacoplar front-end e back-end com FastAPI +
  frontend próprio. Ver [docs/FASE1_DECISOES.txt](docs/FASE1_DECISOES.txt)
  para as decisões técnicas tomadas.
- **Fase 2** — substituir o mapeamento por keywords no Location Agent por
  RAG com embeddings semânticos (sentence-transformers + Chroma).
- **Fase 3** — Dockerização com docker-compose + CI/CD via GitHub Actions.
  A estrutura atual (API e frontend como componentes separados, config via
  `.env`) já está preparada para isto sem alterações estruturais.
- **Fase 4** — Deploy em Render/Railway com demo live.
