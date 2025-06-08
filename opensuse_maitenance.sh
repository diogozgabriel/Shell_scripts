#!/bin/bash

# === CONFIGURATION ===
LOG_FILE=~/logs/opensuse-maintenance-$(date +%F).log  # Log file path with date
mkdir -p ~/logs                                       # Ensure log directory exists
exec > >(tee -a "$LOG_FILE") 2>&1                     # Redirect output to log file

# === COLORS ===
GREEN='\033[0;32m'     # Green text
YELLOW='\033[1;33m'    # Yellow text
NC='\033[0m'           # No color (reset)

# === ROOT CHECK ===
if [ "$EUID" -ne 0 ]; then                            # Check if user is not root
  echo -e "${YELLOW}⚠️  Please run as root.${NC}"   # Warn user to run as root
  exit 1
fi

# === START ===
echo -e "${GREEN}▶️ Starting openSUSE maintenance...${NC}"
echo "Log file: $LOG_FILE"
echo "Date: $(date)"
echo "------------------------"

# === UPDATE SYSTEM ===
echo -e "${GREEN}🔄 Refreshing repositories...${NC}"
zypper refresh

echo -e "${GREEN}⬆️  Updating packages...${NC}"
zypper update -y

# === CHECK FOR ORPHANS ===
echo -e "${GREEN}🔍 Checking for orphaned packages...${NC}"
orphans=$(zypper packages --orphaned | awk '/^[0-9]/ {print $5}')  # Extract orphan package names

if [ -n "$orphans" ]; then
  echo -e "${YELLOW}⚠️  Orphaned packages found:${NC}"
  echo "$orphans"
  read -p "Do you want to remove orphaned packages? [y/N] " resp
  if [[ "$resp" =~ ^[Yy]$ ]]; then
    zypper rm -u $orphans
  else
    echo "👉 Removal skipped by user."
  fi
else
  echo "✅ No orphaned packages found."
fi

# === CLEAN CACHE ===
echo -e "${GREEN}🧹 Cleaning package cache...${NC}"
zypper clean --all

# === FLATPAK UPDATE ===
echo -e "${GREEN}📦 Updating Flatpak packages...${NC}"
flatpak update -y

# === END ===
echo -e "${GREEN}✅ Maintenance completed!${NC}"
