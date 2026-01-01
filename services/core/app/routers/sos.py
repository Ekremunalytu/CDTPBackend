"""
SOS (Acil Durum) Router

Mobil uygulamadan veya bileklikten gelen acil durum sinyallerini işler.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from shared.database import db
from app.socket_manager import sio
import json

router = APIRouter()


class SOSRequest(BaseModel):
    """SOS butonu isteği"""
    patient_id: str
    trigger: str = "BUTTON"  # BUTTON, VOICE, AUTO
    message: Optional[str] = None


@router.post("/sos")
@router.post("/emergency")
async def trigger_sos(request: SOSRequest):
    """
    Acil durum sinyali oluşturur ve bakıcıya bildirim gönderir.
    
    Trigger types:
    - BUTTON: Bileklikteki fiziksel SOS butonu
    - VOICE: Sesli komut ile tetikleme
    - AUTO: Sistem tarafından otomatik (düşme vs.)
    """
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    # Mesaj oluştur
    base_messages = {
        "BUTTON": "🚨 ACİL DURUM BUTONU BASILDI!",
        "VOICE": "🚨 SESLİ ACİL DURUM KOMUTU!",
        "AUTO": "🚨 OTOMATİK ACİL DURUM TESPİTİ!"
    }
    
    alert_message = base_messages.get(request.trigger, "🚨 ACİL DURUM!")
    if request.message:
        alert_message = f"{alert_message} - {request.message}"
    
    try:
        # Emergency log oluştur
        query = """
            INSERT INTO emergency_logs (patient_id, message, created_at)
            VALUES ($1, $2, NOW())
            RETURNING id, patient_id, message, is_resolved, created_at
        """
        row = await db.fetch_one(query, request.patient_id, alert_message)
        
        if row:
            alert_data = dict(row)
            alert_data['patient_id'] = str(alert_data['patient_id'])
            alert_data['created_at'] = alert_data['created_at'].isoformat()
            alert_data['trigger'] = request.trigger
            
            # PostgreSQL notify ile Core servisine bildir
            await db.execute(
                "SELECT pg_notify('alert_updates', $1)", 
                json.dumps(alert_data)
            )
            
            # Socket.IO ile direkt emit (Core servis içindeyiz)
            await sio.emit('sos_alert', alert_data)
            
            return {
                "success": True, 
                "message": "SOS sinyali gönderildi",
                "alert_id": alert_data['id']
            }
        else:
            raise HTTPException(status_code=500, detail="Alert oluşturulamadı")
            
    except Exception as e:
        print(f"SOS Error: {e}")
        raise HTTPException(status_code=500, detail=f"SOS işlenemedi: {str(e)}")


@router.put("/sos/{alert_id}/resolve")
@router.put("/emergency/{alert_id}/resolve")
async def resolve_sos(alert_id: int):
    """
    Acil durumu çözüldü olarak işaretler.
    """
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        query = """
            UPDATE emergency_logs 
            SET is_resolved = TRUE 
            WHERE id = $1
            RETURNING id
        """
        result = await db.fetch_one(query, alert_id)
        
        if result:
            # Bildirim gönder
            await sio.emit('sos_resolved', {"alert_id": alert_id})
            return {"success": True, "message": "Acil durum çözüldü olarak işaretlendi"}
        else:
            raise HTTPException(status_code=404, detail="Alert bulunamadı")
            
    except Exception as e:
        print(f"Resolve Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
