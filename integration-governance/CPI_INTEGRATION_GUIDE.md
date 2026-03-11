# Guia de Integração CPI/SAP PO com GDEP

## Visão Geral

O GDEP pode ser sincronizado com **SAP CPI (Cloud Platform Integration)** e **SAP PO (Process Orchestration)** para trazer dados reais de integrações em seu ambiente empresarial.

## Arquitetura

```
┌────────────────────┐
│   SAP CPI/PO       │  ← Sistema fonte com iFlows/Pipes
│  l400231-tmn...    │
└─────────┬──────────┘
          │ HTTP API
          ↓
┌────────────────────┐
│   GDEP Backend     │  ← FastAPI + Python
│   (CPI Connector)  │
└─────────┬──────────┘
          │ SQLite/DB
          ↓
┌────────────────────┐
│   GDEP Dashboard   │  ← Frontend com Charts.js
│  (Navegador)       │
└────────────────────┘
```

## Configuração

### 1. Credenciais CPI

Você precisará das seguintes informações:

- **Host CPI**: `l400231-tmn.hci.br1.hana.ondemand.com` (sem https://)
- **Username**: Usuário técnico ou conta de serviço do CPI
- **Password**: Senha da conta
- **Tenant ID**: ID do tenant CPI (ex: `l400231`)

### 2. Endpoints de Configuração e Sincronização

As credenciais CPI são salvas por usuário autenticado no endpoint abaixo:

**PUT** `/me/cpi-settings`

#### Request Body

```json
{
  "cpi_host": "l400231-tmn.hci.br1.hana.ondemand.com",
  "cpi_username": "seu_usuario",
  "cpi_password": "sua_senha",
  "cpi_tenant_id": "l400231"
}
```

Após salvar as credenciais, execute a sincronização:

**POST** `/integrations/sync-cpi`

#### Request Body

```json
{
  "reset": false,
  "include_mpl": true,
  "message_limit": 100
}
```

#### Parâmetros

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `reset` | boolean | Se true, remove integrações CPI anteriores antes de sincronizar (default: false) |
| `include_mpl` | boolean | Inclui métricas de Message Processing Logs |
| `message_limit` | integer | Limite lógico de mensagens por execução (1 a 100) |

#### Response

```json
{
  "message": "Sincronização CPI concluída",
  "total_synced": 45,
  "timestamp": "2026-03-10T14:30:00"
}
```

### 3. Sincronização Manual via cURL

```bash
# Login
curl -c cookies.txt -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"seu_email","password":"sua_senha"}'

# Salvar configurações CPI
curl -b cookies.txt -X PUT http://127.0.0.1:8000/me/cpi-settings \
  -H "Content-Type: application/json" \
  -d '{
    "cpi_host": "l400231-tmn.hci.br1.hana.ondemand.com",
    "cpi_username": "seu_usuario",
    "cpi_password": "sua_senha",
    "cpi_tenant_id": "l400231"
  }'

# Sincronizar
curl -b cookies.txt -X POST http://127.0.0.1:8000/integrations/sync-cpi \
  -H "Content-Type: application/json" \
  -d '{
    "reset": false,
    "include_mpl": true,
    "message_limit": 100
  }'
```

### 4. Sincronização via Python

```python
import requests

cpi_config = {
  "reset": False,
  "include_mpl": True,
  "message_limit": 100,
}

session = requests.Session()
session.post(
  "http://127.0.0.1:8000/auth/login",
  json={"email": "seu_email", "password": "sua_senha"},
).raise_for_status()

session.put(
  "http://127.0.0.1:8000/me/cpi-settings",
  json={
    "cpi_host": "l400231-tmn.hci.br1.hana.ondemand.com",
    "cpi_username": "seu_usuario",
    "cpi_password": "sua_senha",
    "cpi_tenant_id": "l400231",
  },
).raise_for_status()

response = session.post("http://127.0.0.1:8000/integrations/sync-cpi", json=cpi_config)

print(response.json())
```

## Dados Sincronizados

Quando uma integração é sincronizada do CPI, os seguintes dados são extraídos:

### Campos Mapeados

- **name**: Nome do iFlow (ex: "Busca SFDC Parceiro Agrupador envia para BW")
- **platform**: Sempre "CPI"
- **source_system**: "SAP CPI"
- **target_system**: Protocols dos endpoints (ex: "HTTP, SOAP")
- **external_id**: ID único do artifact no CPI
- **external_source**: "CPI"
- **last_synced**: Timestamp da última sincronização

### Campos Herdados

- **monthly_volume**: Extraído de Message Processing Logs (em desenvolvimento)
- **error_count**: Contagem de erros processados (em desenvolvimento)
- **error_rate**: Taxa de erro calculada
- **avg_processing_time**: Tempo médio de processamento (em desenvolvimento)
- **business_weight**: Valor padrão 5 (Médio)
- **score**: Calculado com base nos parâmetros acima
- **criticality**: "Crítica", "Alta", "Média" ou "Baixa"

## Operações Disponíveis

### GET `/integrations?platform=CPI`

Retorna todas as integrações sincronizadas do CPI.

```bash
curl http://127.0.0.1:8000/integrations?platform=CPI
```

### GET `/integrations?external_source=CPI`

Filtra por integrações que vieram do CPI especificamente.

## Tratamento de Erros

### Erro: "Falha na autenticação CPI"

- Verifique o username e password
- Confirme que o usuário tem permissão de acesso à API do CPI
- Tente acessar manualmente: `https://l400231-tmn.hci.br1.hana.ondemand.com/itspaces/`

### Erro: "Host CPI não alcançável"

- Verifique o host
- Confirme conectividade de rede
- Verifique firewall/VPN

### Erro: "Tenant ID inválido"

- O tenant ID é geralmente o mesmo nome que aparece na URL do CPI
- Exemplo: `https://l400231-tmn.hci.br1.hana.ondemand.com` → tenant ID é `l400231`

## SAP PO (Integration/Process Orchestration)

Para SAP PO, o processo é similar mas com endpoints diferentes:

1. Criar classe `POConnector` similar a `CPIConnector`
2. Usar API REST do PO (Transaction: `/sap/bc/soap/wsdl`)
3. Mapear Integration Scenarios para o modelo GDEP

*Implementação em andamento.*

## Cronograma Recomendado

- **Sincronização inicial**: Manual com `reset=true`
- **Sincronizações diárias**: Via cronjob ou scheduler (ex: 02:00 AM)
- **Sincronizações sob demanda**: Via botão no dashboard

### Exemplo com Cron (Linux/Mac)

```bash
# Sincronizar diariamente às 2 AM
0 2 * * * curl -b /opt/gdep/cookies.txt -X POST http://localhost:8000/integrations/sync-cpi \
  -H "Content-Type: application/json" \
  -d '{"reset": false, "include_mpl": true, "message_limit": 100}'
```

## Segurança

### Credenciais

⚠️ **IMPORTANTE**: Nunca armazene credenciais em código ou versionamento.

Opções recomendadas:

1. **Variáveis de Ambiente**

```bash
export CPI_HOST="l400231-tmn.hci.br1.hana.ondemand.com"
export CPI_USERNAME="seu_usuario"
export CPI_PASSWORD="sua_senha"
export CPI_TENANT_ID="l400231"
```

2. **Arquivo .env** (com .gitignore)

```
CPI_HOST=l400231-tmn.hci.br1.hana.ondemand.com
CPI_USERNAME=seu_usuario
CPI_PASSWORD=sua_senha
CPI_TENANT_ID=l400231
```

3. **Docker Secrets** (em produção)

4. **Vault/Secret Manager** (Recomendado)

### SSL/TLS

O conector por padrão verifica certificados SSL. Para ambientes de desenvolvimento com certificados auto-assinados:

```python
connector = CPIConnector(
    host="...",
    username="...",
    password="...",
    tenant_id="...",
    verify_ssl=False  # ⚠️ Apenas desenvolvimento!
)
```

## Próximos Passos

1. ✅ Sincronizar metadata de iFlows
2. 🔄 Extrair Message Processing Logs (MPL)
3. 🔄 Calcular métricas em tempo real
4. 🔄 Implementar SAP PO connector
5. 🔄 Dashboard em tempo real com WebSockets
6. 🔄 Alertas automáticos baseados em criticidade

## Referências

- [SAP CPI REST API](https://help.sap.com/docs/INTEGRATION-SUITE)
- [Projeto CPI Dashboard Original](../cpi-dashboard-master)
- [SAP ProcessOrchestration](https://help.sap.com/docs/SAP_PROCESS_ORCHESTRATION)
