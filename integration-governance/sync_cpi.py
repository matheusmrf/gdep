#!/usr/bin/env python3
"""
Utilitário de Sincronização CPI → GDEP

Script para sincronizar integrações do SAP CPI com o GDEP de forma manual.
Suporta variáveis de ambiente para credenciais.

Uso:
    python sync_cpi.py [--host HOST] [--user USER] [--passwd PASSWD] [--tenant TENANT] [--reset]

Variáveis de Ambiente (opcional):
    CPI_HOST        - Host do CPI (ex: l400231-tmn.hci.br1.hana.ondemand.com)
    CPI_USERNAME    - Usuário
    CPI_PASSWORD    - Senha
    CPI_TENANT_ID   - ID do Tenant
    GDEP_API_URL    - URL base do GDEP (padrão: http://127.0.0.1:8000)
"""

import os
import sys
import json
import argparse
import requests
from typing import Optional
from pathlib import Path


def load_env_file(env_file: str = ".env") -> dict:
    """Carrega variáveis de um arquivo .env simples"""
    env_vars = {}
    env_path = Path(env_file)
    
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                # Ignorar linhas vazias e comentários
                if not line or line.startswith("#"):
                    continue
                
                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Remover quotes se existirem
                    value = value.strip('"\'')
                    env_vars[key.strip()] = value
    
    return env_vars


def load_config_from_env() -> dict:
    """Carrega configuração de variáveis de ambiente e arquivo .env"""
    # Primeira carrega o arquivo .env
    env_vars = load_env_file(".env")
    
    # Depois sobrescreve com variável de ambiente do sistema (se existirem)
    return {
        "cpi_host": os.getenv("CPI_HOST", env_vars.get("CPI_HOST", "")),
        "cpi_username": os.getenv("CPI_USERNAME", env_vars.get("CPI_USERNAME", "")),
        "cpi_password": os.getenv("CPI_PASSWORD", env_vars.get("CPI_PASSWORD", "")),
        "cpi_tenant_id": os.getenv("CPI_TENANT_ID", env_vars.get("CPI_TENANT_ID", "")),
        "gdep_api_url": os.getenv("GDEP_API_URL", env_vars.get("GDEP_API_URL", "http://127.0.0.1:8000")),
    }


def sync_cpi(
    cpi_host: str,
    cpi_username: str,
    cpi_password: str,
    cpi_tenant_id: str,
    gdep_api_url: str = "http://127.0.0.1:8000",
    reset: bool = False,
) -> dict:
    """
    Sincroniza dados do CPI com o GDEP.

    Args:
        cpi_host: Host do CPI (sem https://)
        cpi_username: Usuário para autenticação
        cpi_password: Senha
        cpi_tenant_id: ID do tenant
        gdep_api_url: URL base da API GDEP
        reset: Se True, remove integrações CPI existentes

    Returns:
        Resposta da API GDEP
    """
    payload = {
        "cpi_host": cpi_host,
        "cpi_username": cpi_username,
        "cpi_password": cpi_password,
        "cpi_tenant_id": cpi_tenant_id,
        "reset": reset,
    }

    try:
        print(f"🔄 Sincronizando CPI: {cpi_host}...")
        print(f"   Tenant: {cpi_tenant_id}")
        print(f"   Usuário: {cpi_username}")
        print(f"   Reset: {'Sim' if reset else 'Não'}")
        print()

        response = requests.post(
            f"{gdep_api_url}/integrations/sync-cpi",
            json=payload,
            timeout=120,
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Sincronização concluída com sucesso!")
            print(f"   Total sincronizado: {result.get('total_synced', 0)} integrações")
            print(f"   Timestamp: {result.get('timestamp')}")
            return result
        else:
            print(f"❌ Erro na sincronização:")
            print(f"   Status: {response.status_code}")
            print(f"   Resposta: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print(f"❌ Erro: Não foi possível conectar ao GDEP em {gdep_api_url}")
        print(f"   Certifique-se de que o GDEP está rodando.")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ Erro: Timeout na comunicação com CPI ou GDEP")
        return None
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Sincronizar integrações do CPI com GDEP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:

  # Usando variáveis de ambiente
  CPI_HOST=l400231-tmn.hci.br1.hana.ondemand.com python sync_cpi.py

  # Com argumentos de linha de comando
  python sync_cpi.py --host l400231-tmn.hci.br1.hana.ondemand.com \\
                     --user seu_usuario \\
                     --passwd sua_senha \\
                     --tenant l400231

  # Com reset (remove integrações CPI existentes)
  python sync_cpi.py --reset

  # URL customizada do GDEP
  python sync_cpi.py --gdep-url http://seu-servidor:8000
        """,
    )

    parser.add_argument(
        "--host",
        help="Host do CPI (sem https://)",
        default=None,
    )
    parser.add_argument(
        "--user",
        help="Usuário CPI",
        default=None,
    )
    parser.add_argument(
        "--passwd",
        help="Senha CPI",
        default=None,
    )
    parser.add_argument(
        "--tenant",
        help="Tenant ID do CPI",
        default=None,
    )
    parser.add_argument(
        "--gdep-url",
        help="URL base do GDEP (padrão: http://127.0.0.1:8000)",
        default=None,
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remover integrações CPI existentes antes de sincronizar",
    )

    args = parser.parse_args()

    # Carregar configuração de variáveis de ambiente
    env_config = load_config_from_env()

    # Sobrescrever com argumentos de linha de comando
    cpi_host = args.host or env_config["cpi_host"]
    cpi_username = args.user or env_config["cpi_username"]
    cpi_password = args.passwd or env_config["cpi_password"]
    cpi_tenant_id = args.tenant or env_config["cpi_tenant_id"]
    gdep_api_url = args.gdep_url or env_config["gdep_api_url"]

    # Validar campos obrigatórios
    if not all([cpi_host, cpi_username, cpi_password, cpi_tenant_id]):
        print("❌ Erro: Faltam credenciais do CPI")
        print()
        print("Defina via:")
        print("  1. Variáveis de ambiente: CPI_HOST, CPI_USERNAME, CPI_PASSWORD, CPI_TENANT_ID")
        print("  2. Argumentos de linha de comando: --host, --user, --passwd, --tenant")
        print()
        parser.print_help()
        sys.exit(1)

    # Executar sincronização
    result = sync_cpi(
        cpi_host=cpi_host,
        cpi_username=cpi_username,
        cpi_password=cpi_password,
        cpi_tenant_id=cpi_tenant_id,
        gdep_api_url=gdep_api_url,
        reset=args.reset,
    )

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
