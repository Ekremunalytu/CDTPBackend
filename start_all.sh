#!/bin/bash

# Renkler
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== CDTP Akıllı Güvenlik Sistemi Başlatılıyor ===${NC}"

# 1. Backend Servislerini Başlat (Docker)
echo -e "\n${GREEN}[1/3] Backend Servisleri Başlatılıyor (Docker)...${NC}"
# Already in CDTPBackend root
if ! docker-compose up -d; then
    echo -e "${RED}Hata: Docker başlatılamadı! Docker Desktop'ın açık olduğundan emin olun.${NC}"
    exit 1
fi
echo "Backend servisleri arka planda çalışıyor."

# 2. Frontend'i Başlat (Background)
echo -e "\n${GREEN}[2/3] Frontend Başlatılıyor...${NC}"
cd CDTPFrontend
npm run dev -- --port 5173 > /dev/null 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
echo "Dashboard şurada hazır: http://localhost:5173"

# 3. Simülatörü Başlat (Foreground)
echo -e "\n${GREEN}[3/3] Simülatör Başlatılıyor...${NC}"
echo -e "${BLUE}Çıkmak için CTRL+C tuşuna basın. Tüm servisler kapatılacaktır.${NC}"

# Sanal ortamı aktif et ve simülatörü çalıştır
cd .. # Back to CDTPBackend root
source venv/bin/activate

# Cleanup trap
cleanup() {
    echo -e "\n${RED}Kapatılıyor...${NC}"
    kill $FRONTEND_PID
    docker-compose down
    exit 0
}
trap cleanup SIGINT

python3 simulate_device.py
