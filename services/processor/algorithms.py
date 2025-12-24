"""
Düşme Algılama ve Sağlık Algoritmaları

Bu modül ESP32 sensör verilerinden (mobil uygulama üzerinden işlenmiş)
düşme, kalp atışı ve hareketsizlik tespiti yapar.
"""
import math
from typing import List, Dict, Optional, Tuple


def calculate_smv(x: float, y: float, z: float) -> float:
    """Calculates Signal Magnitude Vector from accelerometer data."""
    return math.sqrt(x**2 + y**2 + z**2)


def calculate_smv_array(acc: Dict[str, List[float]]) -> List[float]:
    """Accelerometer array'inden SMV array'i hesaplar."""
    x_vals = acc.get('x', [])
    y_vals = acc.get('y', [])
    z_vals = acc.get('z', [])
    
    # Tüm array'ler aynı uzunlukta olmalı
    length = min(len(x_vals), len(y_vals), len(z_vals))
    
    return [calculate_smv(x_vals[i], y_vals[i], z_vals[i]) for i in range(length)]


def detect_fall(accelerometer: Dict[str, List[float]], 
                impact_threshold: float = 3.0,
                freefall_threshold: float = 0.5,
                stillness_threshold: float = 1.15,
                stillness_samples: int = 5) -> Tuple[bool, str]:
    """
    Gelişmiş düşme algılama algoritması.
    
    Düşme 3 aşamada tespit edilir:
    1. Free-fall (serbest düşüş): SMV < 0.5g 
    2. Impact (çarpma): SMV > 3.0g
    3. Stillness (hareketsizlik): Çarpmadan sonra SMV ≈ 1g
    
    Args:
        accelerometer: {"x": [...], "y": [...], "z": [...]} array formatında
        impact_threshold: Çarpma eşiği (g cinsinden), default 3.0g
        freefall_threshold: Serbest düşüş eşiği, default 0.5g
        stillness_threshold: Hareketsizlik eşiği (~1g), default 1.15g
        stillness_samples: Hareketsizlik için gereken sample sayısı
        
    Returns:
        (is_fall: bool, fall_type: str)
        fall_type: "NONE", "IMPACT_ONLY", "FREEFALL_IMPACT", "FULL_PATTERN"
    """
    smv_values = calculate_smv_array(accelerometer)
    
    if len(smv_values) < 3:
        return False, "INSUFFICIENT_DATA"
    
    # Aşama tespiti
    freefall_detected = False
    impact_detected = False
    impact_index = -1
    
    for i, smv in enumerate(smv_values):
        # Free-fall detection
        if smv < freefall_threshold:
            freefall_detected = True
            
        # Impact detection
        if smv > impact_threshold:
            impact_detected = True
            impact_index = i
            
    # Impact yoksa düşme yok
    if not impact_detected:
        return False, "NONE"
    
    # Impact sonrası stillness kontrolü
    stillness_detected = False
    if impact_index >= 0 and impact_index + stillness_samples < len(smv_values):
        post_impact = smv_values[impact_index + 1:impact_index + 1 + stillness_samples]
        avg_post_impact = sum(post_impact) / len(post_impact) if post_impact else 0
        
        # Stillness: SMV yaklaşık 1g (0.85 - 1.15 arası)
        if 0.85 < avg_post_impact < stillness_threshold:
            stillness_detected = True
    
    # Sonuç değerlendirmesi
    if freefall_detected and impact_detected and stillness_detected:
        return True, "FULL_PATTERN"  # En güvenilir düşme
    elif freefall_detected and impact_detected:
        return True, "FREEFALL_IMPACT"  # Yüksek olasılıklı düşme
    elif impact_detected and stillness_detected:
        return True, "IMPACT_STILLNESS"  # Olası düşme
    elif impact_detected:
        # Sadece impact - muhtemelen sert bir hareket, düşme değil
        # Güvenlik için yine de True dönelim ama tipi belirtelim
        max_smv = max(smv_values)
        if max_smv > 4.0:  # Çok şiddetli impact
            return True, "SEVERE_IMPACT"
        return False, "IMPACT_ONLY"
    
    return False, "NONE"


def calculate_bpm(ppg_raw: List[int], sampling_rate: int = 25) -> int:
    """
    Estimates BPM from raw PPG data using simple peak detection.
    This is a simplified version for prototyping.
    """
    if not ppg_raw or len(ppg_raw) < 2:
        return 0
    
    # Simple peak detection
    peaks = 0
    threshold = sum(ppg_raw) / len(ppg_raw)  # Average as threshold
    
    for i in range(1, len(ppg_raw) - 1):
        if ppg_raw[i] > threshold and ppg_raw[i] > ppg_raw[i-1] and ppg_raw[i] > ppg_raw[i+1]:
            peaks += 1
            
    # Calculate duration in seconds
    duration_sec = len(ppg_raw) / sampling_rate
    
    if duration_sec == 0:
        return 0
        
    bpm = (peaks / duration_sec) * 60
    return max(20, min(int(bpm), 250))  # Clamp between 20-250


def check_inactivity(
    accelerometer: Dict[str, List[float]], 
    current_timestamp: float,
    last_known_movement_at_db: Optional[float] = None,
    stillness_threshold: float = 1.1
) -> Tuple[int, bool]:
    """
    Hareketsizlik süresini hesaplar.
    
    Args:
        accelerometer: Array formatında ivmeölçer verisi
        current_timestamp: Şu anki zaman damgası (unix epoch)
        last_known_movement_at_db: DB'deki son hareket zamanı
        stillness_threshold: Hareketsizlik eşiği (1g civarı)
        
    Returns:
        (inactivity_seconds: int, is_moving: bool)
    """
    smv_values = calculate_smv_array(accelerometer)
    
    if not smv_values:
        return 0, False
    
    # Hareket tespiti: SMV değerleri ~1g'den ne kadar sapıyor?
    # Hareket varsa standart sapma yüksek olur
    avg_smv = sum(smv_values) / len(smv_values)
    variance = sum((s - avg_smv)**2 for s in smv_values) / len(smv_values)
    std_dev = math.sqrt(variance)
    
    # Hareket tespiti: std_dev > 0.1 veya avg 1g'den çok farklı
    is_moving = std_dev > 0.1 or not (0.9 < avg_smv < stillness_threshold)
    
    if is_moving:
        return 0, True  # Hareket var, inactivity = 0
        
    # Kullanıcı hareketsiz
    if last_known_movement_at_db:
        delta = current_timestamp - last_known_movement_at_db
        return int(max(0, delta)), False
    
    # İlk paket, geçmiş yok
    return 0, False
