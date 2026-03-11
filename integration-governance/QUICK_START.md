# GDEP - Quick Start Guide

Guia rápido para começar a usar o GDEP e conectar ao SAP CPI.

## 1️⃣ Setup Inicial (5 minutos)

### Terminal 1: Backend FastAPI
```bash
cd integration-governance

# Ativar virtual environment
source .venv/bin/activate

# Iniciar servidor
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Esperado:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Terminal 2: Dashboard
Abra no navegador:
- **http://127.0.0.1:8000**

Você verá a tela de login.

## 2️⃣ Conectar ao CPI Real (Passo a Passo)

### Passo 1: Obter Credenciais

Você precisa de:
1. **Host CPI**
   - Acesse: https://seu-cpi-host/itspaces/
   - O host aparece na URL: `https://**l400231-tmn**.hci.br1.hana.ondemand.com/...`
   - Copie: `l400231-tmn.hci.br1.hana.ondemand.com`

2. **Username** 
   - Usuário técnico com acesso à API CPI
   - Ex: `seu_usuario@arcelormittal.com`

3. **Password**
   - Senha do usuário técnico

4. **Tenant ID**
   - Primeiro prefixo do host: `l400231`

### Passo 2: Testar Acesso ao CPI

```bash
# Teste básico com curl
curl -u "seu_usuario:sua_senha" \
  "https://seu-host-cpi/itspaces/Operations/com.sap.it.op.srv.commands.dashboard.EnvironmentCommand" \
  -H "Accept: application/json"
```

Se receber um JSON, a autenticação funcionou! ✅

### Passo 3: Salvar credenciais na aplicação

1. Crie sua conta e faça login.
2. Abra `Configurações`.
3. Preencha `Host do CPI`, `Usuário`, `Senha` e `Tenant ID`.
4. Clique em `Salvar e sincronizar`.

### Passo 4: Sincronizar via Script Python

Crie um arquivo `.env` com suas credenciais:

```bash
cat > .env << 'EOF'
CPI_HOST=seu-host-cpi
CPI_USERNAME=seu_usuario
CPI_PASSWORD=sua_senha
CPI_TENANT_ID=seu_tenant_id
EOF
```

Execute o sincronizador:

```bash
python sync_cpi.py --reset
```

Esperado:
```
🔄 Sincronizando CPI: seu-host-cpi...
   Tenant: seu_tenant_id
   Usuário: seu_usuario
   Reset: Sim

✅ Sincronização concluída com sucesso!
   Total sincronizado: 45 integrações
   Timestamp: 2026-03-10T14:30:00
```

### Passo 5: Verificar no Dashboard

Volte ao navegador e:
1. Clique em **"↻ Atualizar"**
2. Os dados do CPI devem aparecer
3. Filtre por **Platform = CPI**

## 3️⃣ Operações Comuns

### Listar todas as integrações
```bash
curl http://127.0.0.1:8000/integrations | jq
```

### Filtrar por plataforma CPI
```bash
curl "http://127.0.0.1:8000/integrations?platform=CPI" | jq
```

### Filtrar por criticidade
```bash
curl "http://127.0.0.1:8000/integrations?criticality=Crítica" | jq
```

### Obter resumo
```bash
curl http://127.0.0.1:8000/summary | jq
```

### Sincronizar novamente (API autenticada)
```bash
# 1) Login e salvar cookie
curl -c cookies.txt -X POST http://127.0.0.1:8000/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"seu_email","password":"sua_senha"}'

# 2) Atualizar credenciais CPI da sua conta
curl -b cookies.txt -X PUT http://127.0.0.1:8000/me/cpi-settings \
   -H "Content-Type: application/json" \
   -d '{
      "cpi_host": "seu-host",
      "cpi_username": "usuario",
      "cpi_password": "senha",
      "cpi_tenant_id": "tenant"
   }'

# 3) Executar sincronização
curl -X POST http://127.0.0.1:8000/integrations/sync-cpi \
   -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
      "reset": false,
      "include_mpl": true,
      "message_limit": 100
  }' | jq
```

## 5️⃣ Troubleshooting

### ❌ "Falha na autenticação CPI"
```
Solução:
1. Verifique username e password
2. Teste manualmente: 
   curl -u "user:pass" https://seu-host/itspaces/
3. Confirme que o usuário tem permissão de API
```

### ❌ "Host CPI não alcançável"
```
Solução:
1. Verifique o host (sem https://)
2. Teste conectividade: ping seu-host
3. Verifique VPN/Firewall
4. Tente: curl https://seu-host/itspaces/
```

### ❌ "Nenhuma integração encontrada"
```
Solução:
1. Confirme que há iFlows no CPI
2. Acesse o CPI dashboard: https://seu-host/itspaces/
3. Verifique se o usuário tem permissão de leitura
```

### ❌ "API URL não responde"
```
Solução:
1. Confirme que tem GDEP rodando:
   curl http://127.0.0.1:8000/health
2. Reinicie se necessário:
   Ctrl+C no terminal 1 e execute novamente
```

## 6️⃣ Documentação Completa

Para informações mais detalhadas, consulte:

- **[CPI_INTEGRATION_GUIDE.md](./CPI_INTEGRATION_GUIDE.md)** - Guia completo de integração
- **[README.md](./README.md)** - Documentação geral
- **[.env.example](./.env.example)** - Todas as variáveis de ambiente disponíveis

## 7️⃣ Próximos Passos Recomendados

1. ✅ Sincronizar os dados do CPI
2. 📊 Explorar o dashboard com filtros
3. 🔔 Configurar alertas (em desenvolvimento)
4. 📅 Agendar sincronização automática (em desenvolvimento)
5. 🔗 Integrar com SAP PO (em desenvolvimento)

## 💡 Dicas

- **Senha segura**: Nunca coloque `.env` no Git. Use `.gitignore`
- **Sincronização**: Primeira vez use `--reset` para limpar dados antigos
- **Logs**: Execute com `--debug` para mais detalhes (em desenvolvimento)
- **Performance**: Se tiver muitos iFlows, a sincronização pode levar alguns minutos

## 🆘 Precisa de ajuda?

Verifique:
1. Logs do servidor: Terminal onde o `uvicorn` está rodando
2. Health check: `curl http://127.0.0.1:8000/health`
3. Documentação: `CPI_INTEGRATION_GUIDE.md`
4. Teste local da API com Postman ou Insomnia

---

**Desenvolvido com ❤️ para ArcelorMittal**
