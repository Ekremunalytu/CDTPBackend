import math
from typing import List, Dict, Optional

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
    return max(20, int(bpm))

def check_inactivity(
    accelerometer: Dict[str, float], 
    last_movement_timestamp: float, # from message
    current_timestamp: float,       # from message
    last_known_movement_at_db: Optional[float] = None # from state DB
) -> int:
    """
    Calculates inactivity duration in seconds.
    
    Logic:
    1. Calculate SMV.
    2. If SMV indicates movement (> 1.1g or < 0.9g), reset inactivity.
    3. If SMV indicates stillness, calculate time delta since last known movement.
    """
    smv = calculate_smv(accelerometer)
    
    # Threshold for "stillness" (approx 1g)
    # If moving
    if not (0.9 < smv < 1.1):
        return 0 # User moved, so inactivity is 0
        
    # User is still.
    # If we have a DB state telling us when they last moved, use it.
    if last_known_movement_at_db:
        # inactivity = current time - last movement time
        # Ensure timestamps are compatible (both unix epoch seconds)
        delta = current_timestamp - last_known_movement_at_db
        return int(max(0, delta))
    
    # Fallback if no history (first packet)
    return 0

