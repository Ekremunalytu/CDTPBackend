#!/bin/bash

# Renkler
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== CDTP Akıllı Güvenlik Sistemi Başlatılıyor ===${NC}"

# 1. Backend Servislerini Başlat (Docker)
echo -e "\n${GREEN}[1/3] Backend Servisleri Başlatılıyor (Docker)...${NC}"
if ! docker-compose up -d --build; then
    echo -e "${RED}Hata: Docker başlatılamadı! Docker Desktop'ın açık olduğundan emin olun.${NC}"
    exit 1
fi

# 2. Servislerin hazır olmasını bekle
echo -e "\n${GREEN}[2/3] Servisler başlatılıyor, lütfen bekleyin...${NC}"

# Ingestion servisinin sağlıklı olmasını bekle
MAX_RETRIES=30
RETRY_COUNT=0

echo -ne "${YELLOW}Ingestion servisi bekleniyor...${NC}"
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e " ${GREEN}Hazır!${NC}"
        break
    fi
    echo -n "."
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "\n${RED}Hata: Ingestion servisi başlatılamadı!${NC}"
    echo -e "${YELLOW}Logları kontrol edin: docker-compose logs ingestion${NC}"
    exit 1
fi

echo "Backend servisleri arka planda çalışıyor."
echo "API: http://localhost:8000"
echo "Ingestion: http://localhost:8001"

# 3. Simülatörü Başlat (Foreground)
echo -e "\n${GREEN}[3/3] Simülatör Başlatılıyor...${NC}"
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
