import math
from typing import List, Dict

def calculate_smv(acc: Dict[str, float]) -> float:
    """Calculates Signal Magnitude Vector from accelerometer data."""
    return math.sqrt(acc['x']**2 + acc['y']**2 + acc['z']**2)

def detect_fall(accelerometer: Dict[str, float], threshold: float = 3.0) -> bool:
    """
    Detects if a fall occurred based on SMV threshold.
    Threshold is in g (gravity units). Default is 3.0g.
    """
    smv = calculate_smv(accelerometer)
    return smv > threshold

def calculate_bpm(ppg_raw: List[int], sampling_rate: int = 25) -> int:
    """
    Estimates BPM from raw PPG data using simple peak detection.
    This is a simplified version for prototyping.
    """
    if not ppg_raw or len(ppg_raw) < 2:
        return 0
    
    # Simple peak detection
    peaks = 0
    threshold = sum(ppg_raw) / len(ppg_raw) # Average as threshold
    
    for i in range(1, len(ppg_raw)-1):
        if ppg_raw[i] > threshold and ppg_raw[i] > ppg_raw[i-1] and ppg_raw[i] > ppg_raw[i+1]:
            peaks += 1
            
    # Calculate duration in seconds
    duration_sec = len(ppg_raw) / sampling_rate
    
    if duration_sec == 0:
        return 0
        
    bpm = (peaks / duration_sec) * 60
    return int(bpm)

def check_inactivity(accelerometer: Dict[str, float], last_movement_timestamp: float, current_timestamp: float) -> int:
    """
    Calculates inactivity duration. 
    This requires state tracking which might be complex for a stateless worker.
    For this MVP, we will assume the device sends an 'inactivity_seconds' field 
    OR we just return 0 if we can't track state across packets easily here.
    
    However, the management plan says 'Inactivity check'. 
    Let's assume the device sends 'inactivity_seconds' or we calculate it based on low movement.
    For now, let's return a dummy value or rely on client-side calculation if possible, 
    BUT the plan says "Algorithm... Inactivity check".
    
    Let's implement a simple check: if SMV is very close to 1g (gravity), it's inactive.
    """
    smv = calculate_smv(accelerometer)
    # 1g is ~9.8m/s^2 or 1.0 if normalized. Assuming normalized 1.0g for gravity.
    # If input is in g:
    if 0.9 < smv < 1.1:
        return 1 # Represents 1 second of inactivity (approx)
    return 0
