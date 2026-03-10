# GDEP

Projeto de governança de integrações com backend em FastAPI, persistência via SQLAlchemy e dashboard web servido pela própria API.

## O que o projeto entrega

- Dashboard acessível em `GET /`
- API para listar integrações com filtros
- Endpoint de resumo operacional
- Geração de massa mock para popular o ambiente
- Execução local com SQLite
- Execução com Docker Compose usando PostgreSQL
- Testes automatizados cobrindo API e seed

## Estrutura

```text
GDEP/
├── README.md
├── CPI DASHBOARD/
└── integration-governance/
    ├── backend/
    │   ├── collector.py
    │   ├── database.py
    │   ├── Dockerfile
    │   ├── main.py
    │   ├── models.py
    │   ├── requirements.txt
    │   └── schemas.py
    ├── frontend/
    │   └── index.html
    ├── backend/tests/
    ├── docker-compose.yml
    └── pytest.ini
```

## Endpoints principais

- `GET /health`: status simples da aplicação
- `GET /`: dashboard HTML
- `GET /integrations`: lista integrações
- `GET /summary`: resumo agregado do ambiente
- `POST /integrations/seed`: gera base mock

### Filtros suportados em `/integrations`

- `criticality`
- `platform`
- `search`
- `min_score`

## Execução local

```bash
cd integration-governance
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Abra:

- Dashboard: `http://127.0.0.1:8000`
- Healthcheck: `http://127.0.0.1:8000/health`
- Documentação OpenAPI: `http://127.0.0.1:8000/docs`

## Popular o ambiente com dados mock

Via API:

```bash
curl -X POST http://127.0.0.1:8000/integrations/seed \
  -H "Content-Type: application/json" \
  -d '{"count": 20, "reset": true}'
```

Via script:

```bash
cd integration-governance
python3 backend/collector.py
```

## Execução com Docker

```bash
cd integration-governance
docker compose up --build
```

Serviços:

- `backend`: FastAPI em `http://127.0.0.1:8000`
- `db`: PostgreSQL em `localhost:5432`

O frontend já é copiado para a imagem e servido pelo backend.

## Testes

```bash
cd integration-governance
python3 -m pytest
```

## Observações

- SQLite é o banco padrão fora do Docker.
- No Docker Compose, o backend usa PostgreSQL.
- A base mock reinicializa os dados por padrão ao executar o seed.
- Ainda não existe ingestão real de dados de SAP CPI ou outras plataformas produtivas.
