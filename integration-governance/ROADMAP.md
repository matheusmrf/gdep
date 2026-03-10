# Próximos Passos - Roadmap GDEP

Sugestões de melhorias e funcionalidades para aprimorar o GDEP.

## 🔄 Fase 2: Message Processing Logs (MPL)

### Objetivo
Extrair logs de processamento de mensagens do CPI para calcular métricas reais:
- Volume mensal de mensagens
- Taxa de erro
- Tempo médio de processamento

### Arquitetura
```python
# Em backend/cpi_connector.py adicionar:

def get_message_logs(artifact_id: str, time_range_hours: int = 24) -> List[Dict]:
    """Extrai logs de mensagens processadas"""
    # Endpoint: /itspaces/Operations/com.sap.it.op.srv.commands.dashboard.MessageProcessingLogCommand
    # Query: maximumResultSize, fromTimestamp, toTimestamp, artifactId
    # Parse: messages com status (COMPLETED, FAILED, RETRY)

def calculate_metrics(messages: List[Dict]) -> Dict:
    """Calcula volume, erro_rate, tempo_processamento"""
    # total_messages = len(messages)
    # failed = sum(1 for m if m['status'] == 'FAILED')
    # error_rate = failed / total_messages
    # avg_time = sum(m['processingTime']) / len(messages)
```

### Alterações no Endpoint
```python
@app.post("/integrations/sync-cpi")
def sync_cpi_integrations(...):
    # Antes: apenas metadata dos iFlows
    # Depois: + logs de mensagens para calcular métricas reais
    
    for artifact in artifacts:
        messages = connector.get_message_logs(artifact['id'])
        metrics = connector.calculate_metrics(messages)
        
        # Atualizar integração com métricas
        integration.monthly_volume = metrics['total_messages']
        integration.error_count = metrics['failed']
        integration.error_rate = metrics['error_rate']
        integration.avg_processing_time = metrics['avg_time']
        integration.score = recalculate_score(...)
```

## 🔌 Fase 3: SAP PO Connector

### Objetivo
Integrar com SAP Process Orchestration (SAP PO) para sincronizar:
- Integration Scenarios
- Interface Mappings
- Message Queues
- Performance metrics

### Estrutura
```python
# novo arquivo: backend/sap_po_connector.py

class SAPPOConnector:
    def __init__(self, host: str, client: str, username: str, password: str):
        # Usar RFC ou REST API do PO
        # Endpoints: /sap/bc/soap/wsdl (WSDL/SOAP)
        
    def get_scenarios(self) -> List[Dict]:
        # Retorna Integration Scenarios
        
    def get_interfaces(self) -> List[Dict]:
        # Retorna Interface Mappings
        
    def get_queue_status(self) -> List[Dict]:
        # Status das filas de mensagens
```

## 📡 Fase 4: Real-time Updates com WebSockets

### Objetivo
Atualizações em tempo real do dashboard sem necessidade de F5 (refresh).

### Tecnologia
```javascript
// frontend/js/websocket.js
const ws = new WebSocket('ws://127.0.0.1:8000/ws/updates');

ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    // Atualizar gráficos e tabelas em tempo real
    updateDashboard(update);
};
```

### Backend
```python
# backend/main.py - usar fastapi-starlette

from fastapi import WebSocket

@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        # Enviar updates periodicamente
        await websocket.send_json({
            "integrations": get_critical_only(),
            "timestamp": datetime.now()
        })
        await asyncio.sleep(30)  # A cada 30 segundos
```

## 🔔 Fase 5: Sistema de Alertas

### Objetivo
Notificações automáticas quando eventos críticos ocorrem.

### Funcionalidades

1. **Alertas por Email**
```python
# backend/alerting.py

class AlertManager:
    def send_alert(self, integration_id: int, severity: str, message: str):
        # SMTP para enviar emails
        # Template HTML
        # Recipients baseado em criticidade
```

2. **Alertas por Integração**
- Quando crítica fica indisponível
- Taxa de erro excede threshold
- Timeout em processamento
- Cotas de volume ultrapassadas

3. **Escalação**
- Level 1: Email automático
- Level 2: SMS (Twilio)
- Level 3: Slack/Teams webhook

## 📊 Fase 6: Multi-Tenant Support

### Objetivo
Suportar múltiplos tenants/ambientes CPI.

### Arquitetura
```python
# models.py adicionar:

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String)  # "CPI Produção", "CPI Teste"
    cpi_host = Column(String)
    cpi_tenant_id = Column(String)
    # Credenciais encriptadas do Vault

class Integration(Base):
    tenant_id = Column(Integer, ForeignKey('tenants.id'))
    # ... resto dos campos
```

### API
```python
# GET /tenants/{tenant_id}/integrations
@app.get("/tenants/{tenant_id}/integrations")
def get_integrations(tenant_id: int, db: Session):
    # Filter by tenant_id
```

## 🔐 Fase 7: Autenticação e Autorização

### Objetivo
Proteger a API e dashboard com autenticação.

### Implementação
```python
# backend/auth.py

from fastapi.security import HTTPBearer, HTTPAuthCredentialDetails

@app.post("/auth/login")
def login(username: str, password: str):
    # LDAP/SAML contra AD corporativo
    # Ou OIDC/OAuth2 com Azure AD
    # Retorna JWT token

@app.get("/integrations", dependencies=[Depends(verify_token)])
def get_integrations(current_user: dict = Depends(get_current_user)):
    # Acesso apenas a integrações que o usuário é autorizado
```

## 📈 Fase 8: Relatórios e Exportação

### Funcionalidades

1. **Exportar para Excel**
```python
@app.get("/integrations/export/xlsx")
def export_integrations(format: str = "xlsx"):
    # Usar openpyxl
    # Template com estilos
```

2. **Relatórios Customizados**
- Por período de tempo
- Por plataforma
- Por departamento
- Com gráficos

3. **Agendamento**
- Gerar relatório automaticamente
- Enviar por email

## 🚀 Fase 9: Performance e Otimização

### Melhorias

1. **Cache**
```python
from functools import lru_cache
import redis

# Cache dos dados em Redis
# TTL de 5 minutos
```

2. **Paginação**
```python
@app.get("/integrations")
def get_integrations(skip: int = 0, limit: int = 100):
    # Retornar em chunks
```

3. **Índices no DB**
```python
# models.py
external_source_idx = Index('idx_external_source', Integration.external_source)
platform_idx = Index('idx_platform', Integration.platform)
```

## 📱 Fase 10: Mobile App

### Opções

1. **Web Responsivo** (mais fácil)
   - Dashboard já é responsivo
   - Melhorar interface mobile

2. **React Native / Flutter**
   - App nativa para iOS/Android
   - Sincronização offline
   - Push notifications

## 🎓 Documentação Adicional Necessária

- [ ] OpenAPI/Swagger spec
- [ ] Architecture Decision Records (ADRs)
- [ ] API Versioning strategy
- [ ] Database migration scripts
- [ ] Disaster recovery plan
- [ ] Performance benchmarks

## 🧪 Testes Faltando

- [ ] Integration tests com CPI mock
- [ ] Load tests
- [ ] Security tests (OWASP)
- [ ] End-to-end tests

## 📋 Checklist de Produção

- [ ] HTTPS/TLS configurado
- [ ] CORS restrito
- [ ] Rate limiting
- [ ] Audit logging
- [ ] Backup automático
- [ ] Monitoramento (Prometheus/Grafana)
- [ ] Alertas operacionais
- [ ] Runbooks de troubleshooting

---

## Estimativa de Esforço

| Fase | Complexidade | Tempo Estimado |
|------|-------------|----------------|
| MPL Integration | Média | 2 semanas |
| SAP PO | Alta | 3 semanas |
| WebSockets | Média | 1 semana |
| Alertas | Média | 2 semanas |
| Multi-tenant | Alta | 3 semanas |
| Auth | Alta | 2 semanas |
| Relatórios | Média | 2 semanas |
| Performance | Média | 1 semana |
| Mobile | Muito Alta | 4-6 semanas |

**Total**: ~20-25 semanas de desenvolvimento

---

**Próximas reuniões recomendadas:**
1. Priorizar fases baseado em necessidade do negócio
2. Definir sprints de 2 semanas
3. Setup de CI/CD
4. Definir SLA de uptime
