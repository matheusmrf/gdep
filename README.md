# GDEP

Projeto de governança e criticidade de integrações, composto por um backend em FastAPI, persistência com SQLAlchemy e um frontend HTML simples para visualização das integrações e sua distribuição por criticidade.

## Objetivo

Fornecer uma base para avaliação operacional de integrações, atribuindo score e criticidade a fluxos com base em volume, taxa de erro, tempo médio e peso de negócio.

## Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite por padrão
- PostgreSQL via Docker Compose
- HTML + Chart.js no frontend estático

## Estrutura

```text
GDEP/
├── README.md
├── CPI DASHBOARD/
│   └── Solucao CPI DASHBOARD.docx
└── integration-governance/
    ├── backend/
    │   ├── main.py
    │   ├── collector.py
    │   ├── database.py
    │   ├── models.py
    │   ├── requirements.txt
    │   └── Dockerfile
    ├── frontend/
    │   └── index.html
    ├── docker-compose.yml
    └── integration_governance.db
```

## Componentes

### Backend

O backend expõe atualmente um endpoint principal:

- `GET /integrations`: retorna todas as integrações cadastradas

A aplicação cria as tabelas na inicialização com base nos models SQLAlchemy.

### Coletor de dados mock

O arquivo `backend/collector.py` gera dados sintéticos para povoar a base. Ele calcula:

- volume mensal
- quantidade de erros
- taxa de erro
- score
- criticidade (`Crítica`, `Alta`, `Média`, `Baixa`)

### Frontend

O arquivo `frontend/index.html` consome a API em `http://127.0.0.1:8000/integrations` e exibe:

- tabela com integrações
- gráfico de barras com distribuição por criticidade

## Modelo de dados

A entidade `Integration` contém:

- `name`
- `platform`
- `source_system`
- `target_system`
- `monthly_volume`
- `error_count`
- `error_rate`
- `avg_processing_time`
- `business_weight`
- `score`
- `criticality`

## Execução local

### Ambiente Python direto

```bash
cd integration-governance
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

API disponível em:

```text
http://127.0.0.1:8000
```

### Gerar dados mock

```bash
cd integration-governance
python3 backend/collector.py
```

### Abrir frontend

Abra o arquivo abaixo no navegador, ou sirva a pasta com um servidor simples:

```text
integration-governance/frontend/index.html
```

## Execução com Docker

```bash
cd integration-governance
docker compose up --build
```

O `docker-compose.yml` sobe:

- `db`: PostgreSQL
- `backend`: FastAPI em `8000`

## Observações técnicas importantes

- o backend usa SQLite por padrão via `DATABASE_URL`, apesar do `docker-compose` subir PostgreSQL
- o `database.py` aplica `check_same_thread=False`, típico para SQLite
- não há, no estado atual, integração real com SAP CPI ou fontes produtivas
- o frontend assume a API em `127.0.0.1:8000`, sem configuração por ambiente

## Casos de uso esperados

- prova de conceito de governança de integrações
- dashboard interno para priorização operacional
- base inicial para enriquecer com dados reais de monitoramento

## Melhorias recomendadas

- alinhar definitivamente SQLite versus PostgreSQL
- criar endpoint para carga real de dados
- adicionar paginação e filtros na API
- separar frontend em projeto próprio
- incluir autenticação e autorização
- cobrir regras de score com testes automatizados
