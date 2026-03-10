# Sincronizando CPI - Troubleshooting

Seu arquivo `.env` foi criado corretamente com as credenciais. Agora temos algumas formas de testar a sincronização:

## ✅ O que já testamos

- ✅ Arquivo `.env` criado com credenciais
- ✅ Script `sync_cpi.py` consegue ler o arquivo
- ✅ Autenticação contra CPI funciona (HTTP 200)

## 🔄 Próximo Passo: Teste via cURL

Sistema operacional tem um problema de exibição de output no terminal. Vou criar um command curl direto para você executar:

### 1. Certificar que Backend está rodando

Abra um terminal NOVO e execute:

```bash
cd /Users/matheusfigueiredo/Documents/Arcelormittal/Desenvolvimentos/GDEP/integration-governance
/Users/matheusfigueiredo/Documents/Arcelormittal/Desenvolvimentos/GDEP/integration-governance/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Esperado:** Deve ver `Application startup complete`

### 2. Em outro terminal: Sincronizar via cURL

```bash
curl -X POST http://127.0.0.1:8000/integrations/sync-cpi \
  -H "Content-Type: application/json" \
  -d '{
    "cpi_host": "l400231-tmn.hci.br1.hana.ondemand.com",
    "cpi_username": "S0025012682",
    "cpi_password": "etm*wpk.UKG6pxj@dty",
    "cpi_tenant_id": "l400231",
    "reset": true
  }'
```

### 3. Verificar Resultado

Acesse no navegador:
- **Dashboard**: http://127.0.0.1:8000
- **API Integrations**: http://127.0.0.1:8000/integrations?platform=CPI
- **Summary**: http://127.0.0.1:8000/summary

## 🐛 Se receber erro 401

O erro significa que as credenciais CPI estão sendo rejeitadas. Possíveis causas:

1. **Username/Password incorretos**
   - Verifique a senha (tem caracteres especiais `*`, `@`)
   - Tente fazer login manualmente no CPI

2. **Usuário sem permissão de API**
   - Contate admin do CPI
   - Confirme que o usuário tem acesso a `/itspaces/Operations`

3. **Tenant ID incorreto**
   - Deve ser parte do host: `l400231-tmn...` → `l400231`

## ✨ Solução Alternativa: Via Postman

Se tiver Postman instalado:

1. Importe `GDEP.postman_collection.json`
2. Configure variáveis:
   ```
   cpi_host = l400231-tmn.hci.br1.hana.ondemand.com
   cpi_username = S0025012682
   cpi_password = etm*wpk.UKG6pxj@dty
   cpi_tenant_id = l400231
   ```
3. Use a requisição "Sync CPI"

## 📧 Precisa executar o sync_cpi.py?

O script agora lê automaticamente do `.env`. Execute assim:

```bash
cd /Users/matheusfigueiredo/Documents/Arcelormittal/Desenvolvimentos/GDEP/integration-governance

# Ativar venv
source .venv/bin/activate

# Rodar sincronização
python sync_cpi.py --reset
```

## 📝 Próximos Passos

1. Escolha um dos métodos acima (cURL, Postman ou sync_cpi.py)
2. Execute a sincronização
3. Verifique no dashboard se as integrações apareceram
4. Filtre por `platform=CPI`

---

**Desenvolvido para ArcelorMittal** 🔧
