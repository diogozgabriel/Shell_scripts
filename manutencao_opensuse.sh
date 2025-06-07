#!/bin/bash

# === CONFIGURAÇÕES ===
LOG_FILE=~/logs/manutencao-opensuse-$(date +%F).log
mkdir -p ~/logs
exec > >(tee -a "$LOG_FILE") 2>&1

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# === CHECAR ROOT ===
if [ "$EUID" -ne 0 ]; then
  echo -e "${YELLOW}⚠️  Por favor, execute como root.${NC}"
  exit 1
fi

# === INÍCIO ===
echo -e "${GREEN}▶️ Iniciando manutenção do openSUSE...${NC}"
echo "Log: $LOG_FILE"
echo "Data: $(date)"
echo "------------------------"

# === ATUALIZAÇÃO ===
echo -e "${GREEN}🔄 Atualizando repositórios...${NC}"
zypper refresh

echo -e "${GREEN}⬆️  Atualizando pacotes...${NC}"
zypper update -y

# === ÓRFÃOS ===
echo -e "${GREEN}🔍 Verificando pacotes órfãos...${NC}"
orphans=$(zypper packages --orphaned | awk '/^[0-9]/ {print $5}')

if [ -n "$orphans" ]; then
  echo -e "${YELLOW}⚠️  Pacotes órfãos encontrados:${NC}"
  echo "$orphans"
  read -p "Deseja remover os pacotes órfãos? [s/N] " resp
  if [[ "$resp" =~ ^[Ss]$ ]]; then
    zypper rm -u $orphans
  else
    echo "👉 Remoção ignorada pelo usuário."
  fi
else
  echo "✅ Nenhum pacote órfão encontrado."
fi

# === LIMPEZA ===
echo -e "${GREEN}🧹 Limpando cache...${NC}"
zypper clean --all

# === FIM ===
echo -e "${GREEN}✅ Manutenção concluída!${NC}"
