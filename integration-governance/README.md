# GDEP - Governance Dashboard para Integrações

Dashboard análitico para monitoramento centralizado de integrações corporativas (CPI, SAP PO, Kafka, MuleSoft, etc).

## 🎯 Objetivo

Fornecer uma visão consolidada de todas as integrações de uma organização, permitindo:

- 📊 **Monitoring**: Visão centralizada de status, criticidade e performance
- 🔍 **Análise**: Métricas de volume, taxa de erro, tempo de processamento
- 📈 **Governança**: Score de críticidade, relatórios e alertas
- 🔗 **Integração**: Conecta com SAP CPI, SAP PO e outras plataformas

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────┐
│         Frontend Dashboard              │
│ (HTML/CSS/JS com Chart.js)              │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│      FastAPI Backend (Python)           │
│  ├─ REST API                            │
│  ├─ CPI Connector                       │
│  └─ SAP PO Connector (planned)          │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼──────────────┐
│    SQLite Database            │
│  (Integrações sincronizadas)  │
└───────────────────────────────┘
```

## 🚀 Quick Start

### 1. Setup

```bash
cd integration-governance

# Criar virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r backend/requirements.txt
```

### 2. Iniciar a Aplicação

```bash
# Terminal 1: Backend
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Visualizar no navegador
open http://127.0.0.1:8000
```

### 3. Configurar credenciais e sincronizar o CPI

Faça login na aplicação, abra `Configurações`, salve suas credenciais do CPI e use `Salvar e sincronizar` ou `Sincronizar CPI` no dashboard.

## 🔗 Sincronização com CPI

### Sincronizar via Script Python

```bash
# Usar variáveis de ambiente
python sync_cpi.py

# Ou com argumentos diretos
python sync_cpi.py --host l400231-tmn.hci.br1.hana.ondemand.com \
                   --user seu_usuario \
                   --passwd sua_senha \
                   --tenant l400231
```

### Sincronizar via cURL

```bash
curl -X POST http://127.0.0.1:8000/integrations/sync-cpi \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "reset": false,
    "include_mpl": true,
    "message_limit": 20
  }'
```

## 📡 API Endpoints

### GET `/`
Dashboard interativo

### GET `/health`
Health check da aplicação

### GET `/integrations`
Lista as integrações da conta logada, com filtros e paginação.

**Query Parameters:**
- `platform` - Filtrar por plataforma (CPI, MuleSoft, Kafka, API Gateway)
- `criticality` - Filtrar por criticidade (Crítica, Alta, Média, Baixa)
- `search` - Buscar por nome ou sistemas
- `min_score` - Score mínimo (0-100)
- `start_date` e `end_date` - Faixa de datas baseada em `last_synced`
- `skip` e `limit` - Paginação

**Exemplo:**
```bash
curl -b cookies.txt "http://127.0.0.1:8000/integrations?platform=CPI&criticality=Crítica&limit=25&skip=0"
```

### GET `/summary`
Estatísticas gerais

```json
{
  "total_integrations": 45,
  "average_score": 65.5,
  "total_monthly_volume": 1500000,
  "total_error_count": 245,
  "criticality_distribution": {
    "Crítica": 5,
    "Alta": 12,
    "Média": 20,
    "Baixa": 8
  }
}
```

### POST `/integrations/sync-cpi`
Sincronizar integrações do CPI usando as credenciais salvas para a conta logada.

```json
{
  "reset": false,
  "include_mpl": true,
  "message_limit": 20
}
```

## 🎨 Design

O dashboard utiliza a **paleta de cores corporativa da ArcelorMittal**:

- 🔴 **Vermelho (#C8202E)**: Cor primária, criticidade máxima
- ⚫ **Cinza (#2D2D2D)**: Textos, profissionalismo
- 🔵 **Azul (#0052CC)**: Destaques, links
- 🟠 **Laranja (#FF6B35)**: Severidade alta
- 🟡 **Amarelo (#FFC857)**: Severidade média
- 🟢 **Verde (#1CB30E)**: Severidade baixa

## 📊 Métricas de Criticidade

As integrações são classificadas em 4 níveis:

| Nível | Cor | Score | Descrição |
|-------|-----|-------|-----------|
| **Crítica** | 🔴 | 80+ | Sistema essencial, impacto alto |
| **Alta** | 🟠 | 60-79 | Importante, impacto moderado |
| **Média** | 🟡 | 30-59 | Moderado, impacto baixo |
| **Baixa** | 🟢 | 0-29 | Não crítico |

**Cálculo de Score:**
```
score = (volume × 0.0001 × 0.4) + (taxa_erro × 100 × 0.4) + (peso_negócio × 0.2)
```

## 📦 Estrutura do Projeto

```
integration-governance/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── models.py              # SQLAlchemy models
│   ├── schemas.py             # Pydantic schemas
│   ├── database.py            # DB config
│   ├── collector.py           # Data generation
│   ├── cpi_connector.py       # CPI integration
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   ├── index.html             # Dashboard HTML/CSS/JS
│   ├── css/
│   └── js/
├── docker-compose.yml
├── sync_cpi.py                # Sync utility script
├── CPI_INTEGRATION_GUIDE.md   # Detailed CPI integration docs
├── .env.example               # Environment variables template
└── README.md

```

## 🐳 Docker Compose

```bash
# Iniciar com docker-compose
docker-compose up -d

# Parar
docker-compose down
```

## 🧪 Testes

```bash
# Rodar testes unitários
pytest backend/tests/

# Com coverage
pytest --cov=backend backend/tests/
```

## 🔐 Segurança

### Credenciais CPI

✅ **Recomendado:**
- Usar variáveis de ambiente
- Arquivo `.env` (nunca versione)
- Docker Secrets (produção)
- Vault/Secret Manager

❌ **Nunca faça:**
- Hardcode credenciais no código
- Commitar `.env` com senhas
- Log de credenciais

### SSL/TLS

Por padrão, o conector verifica certificados SSL. Para desenvolvimento com certificados auto-assinados, use `verify_ssl=False`.

## 📚 Documentação Adicional

- [CPI Integration Guide](./CPI_INTEGRATION_GUIDE.md) - Guia completo de integração com SAP CPI
- [API Documentation](./OPENAPI_SPEC.md) - Especificação OpenAPI
- [Deployment Guide](./DEPLOYMENT.md) - Deploy em produção

## 🔄 Próximos Passos

- [ ] Sincronizar Message Processing Logs (MPL) do CPI
- [ ] Implementar SAP PO connector
- [ ] Real-time updates com WebSockets
- [ ] Alertas automáticos
- [ ] Multi-tenant support
- [ ] SAML/OAuth authentication
- [ ] GraphQL API

## 📝 Changelog

### v1.0.0 (2026-03-10)
- ✅ Dashboard inicial com design ArcelorMittal
- ✅ Mock data generator
- ✅ CPI Connector (metadata)
- ✅ REST API básica
- ✅ Filtros e busca

## 👥 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📞 Suporte

Para dúvidas ou problemas:
- Consulte a [CPI Integration Guide](./CPI_INTEGRATION_GUIDE.md)
- Verifique logs: `docker-compose logs -f backend`
- Teste health check: `curl http://127.0.0.1:8000/health`

## 📄 Licença

Copyright © 2026 ArcelorMittal. Todos os direitos reservados.

---

**Desenvolvido com ❤️ para ArcelorMittal Sistemas**
