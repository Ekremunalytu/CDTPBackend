#!/bin/bash

# Renkler
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== CDTP Akıllı Güvenlik Sistemi Başlatılıyor ===${NC}"

# 1. Backend Servislerini Başlat (Docker)
echo -e "\n${GREEN}[1/2] Backend Servisleri Başlatılıyor (Docker)...${NC}"
if ! docker-compose up -d; then
    echo -e "${RED}Hata: Docker başlatılamadı! Docker Desktop'ın açık olduğundan emin olun.${NC}"
    exit 1
fi
echo "Backend servisleri arka planda çalışıyor."
echo "API: http://localhost:8000"
echo "Ingestion: http://localhost:8001"

# 2. Simülatörü Başlat (Foreground)
echo -e "\n${GREEN}[2/2] Simülatör Başlatılıyor...${NC}"
echo -e "${BLUE}Çıkmak için CTRL+C tuşuna basın. Tüm servisler kapatılacaktır.${NC}"

# Sanal ortamı aktif et ve simülatörü çalıştır
source venv/bin/activate 2>/dev/null || true

# Cleanup trap
cleanup() {
    echo -e "\n${RED}Kapatılıyor...${NC}"
    docker-compose down
    exit 0
}
trap cleanup SIGINT

python3 simulate_device.py
