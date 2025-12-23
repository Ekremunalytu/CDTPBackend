from typing import Optional, Tuple, Dict, Any

def evaluate_measurement(
    heart_rate: int, 
    inactivity_seconds: int, 
    settings: Optional[Dict[str, Any]] = None,
    is_fall: bool = False
) -> Tuple[str, Optional[str]]:
    """
    Evaluates the measurement data against patient settings to determine status and alerts.
    
    Args:
        heart_rate: The calculated heart rate in BPM.
        inactivity_seconds: The duration of inactivity in seconds.
        settings: A dictionary containing patient settings (bpm_lower_limit, bpm_upper_limit, max_inactivity_seconds).
                  If None, default values are used.
        is_fall: specific flag for fall detection (usually comes from accelerometer analysis).
                  
    Returns:
        A tuple containing (status, alert_message).
        status: 'NORMAL', 'WARNING', or 'CRITICAL'
        alert_message: A descriptive message for the alert, or None if status is NORMAL.
    """
    
    # Default settings
    bpm_lower = 50
    bpm_upper = 120
    max_inactivity = 900 # 15 minutes
    
    if settings:
        bpm_lower = settings.get('bpm_lower_limit', bpm_lower)
        bpm_upper = settings.get('bpm_upper_limit', bpm_upper)
        max_inactivity = settings.get('max_inactivity_seconds', max_inactivity)
        
    status = "NORMAL"
    alert_msg = None
    
    # Fall detection has highest priority
    if is_fall:
        status = "CRITICAL"
        alert_msg = "FALL DETECTED!"
        return status, alert_msg
        
    # Check Heart Rate
    if heart_rate < bpm_lower or heart_rate > bpm_upper:
        status = "WARNING" # Using WARNING for abnormal HR as per original logic, could be CRITICAL based on severity
        # Let's align with the original logic which had CRITICAL for fall, but the code in processor/main.py 
        # actually marked bpm < 40 or > 120 as WARNING. 
        # However, Core service marked it as CRITICAL in one place?
        # Let's verify Core service logic: 
        # Core: if < bpm_lower or > bpm_upper -> CRITICAL. 
        # Processor: if < 40 or > 120 -> WARNING.
        # This is the inconsistency we are fixing. 
        # Decision: Abnormal heart rate is usually CRITICAL or at least serious.
        # Let's use CRITICAL for Heart Rate as it's more safe for health apps.
        status = "CRITICAL"
        alert_msg = f"Abnormal Heart Rate: {heart_rate} BPM (Limit: {bpm_lower}-{bpm_upper})"
    
    # Check Inactivity
    elif inactivity_seconds > max_inactivity:
        status = "WARNING"
        alert_msg = f"High Inactivity: {inactivity_seconds}s (Limit: {max_inactivity}s)"
        
    return status, alert_msg
