"""
Patients Router

Hasta bilgileri, ölçümler ve acil durum loglarını getiren endpoint'ler.
Android uygulaması ile uyumlu API.
"""
from fastapi import APIRouter, HTTPException, Query
from shared.database import db

router = APIRouter()


@router.get("/patients/{patient_id}")
async def get_patient(patient_id: str):
    """
    Tek hasta detay bilgisini getirir.
    
    Returns:
        - id: Hasta UUID
        - name: Hasta adı
        - birth_date: Doğum tarihi
        - medical_info: Tıbbi bilgiler
        - user_id: Bağlı kullanıcı ID
    """
    query = """
        SELECT p.id, p.user_id, p.name, p.birth_date, p.medical_info, p.created_at
        FROM patients p
        WHERE p.id = $1
    """
    row = await db.fetch_one(query, patient_id)
    
    if row:
        result = dict(row)
        result['id'] = str(result['id'])
        result['user_id'] = str(result['user_id']) if result.get('user_id') else None
        result['birth_date'] = result['birth_date'].isoformat() if result.get('birth_date') else None
        result['created_at'] = result['created_at'].isoformat() if result.get('created_at') else None
        return result
    else:
        raise HTTPException(status_code=404, detail="Patient not found")


@router.get("/patients/{patient_id}/measurements")
async def get_patient_measurements(
    patient_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Hasta ölçümlerini sayfalama destekli olarak getirir.
    
    Args:
        patient_id: Hasta UUID
        limit: Sayfa başına kayıt (max 100)
        offset: Atlama miktarı
    
    Returns:
        List of measurements with:
        - id: Ölçüm ID
        - heart_rate: Nabız
        - inactivity_seconds: Hareketsizlik süresi
        - status: NORMAL/WARNING/CRITICAL
        - measured_at: Ölçüm zamanı
    """
    query = """
        SELECT id, heart_rate, inactivity_seconds, status, measured_at
        FROM measurements
        WHERE patient_id = $1
        ORDER BY measured_at DESC
        LIMIT $2 OFFSET $3
    """
    rows = await db.fetch_all(query, patient_id, limit, offset)
    
    result = []
    for row in rows:
        item = dict(row)
        item['measured_at'] = item['measured_at'].isoformat() if item.get('measured_at') else None
        result.append(item)
    
    return result


@router.get("/patients/{patient_id}/emergency-logs")
async def get_patient_emergency_logs(
    patient_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Hasta acil durum geçmişini getirir.
    
    Args:
        patient_id: Hasta UUID
        limit: Sayfa başına kayıt (max 100)
        offset: Atlama miktarı
    
    Returns:
        List of emergency logs with:
        - id: Log ID
        - message: Acil durum mesajı
        - is_resolved: Çözüldü mü
        - created_at: Oluşturulma zamanı
    """
    query = """
        SELECT id, message, is_resolved, created_at
        FROM emergency_logs
        WHERE patient_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
    """
    rows = await db.fetch_all(query, patient_id, limit, offset)
    
    result = []
    for row in rows:
        item = dict(row)
        item['created_at'] = item['created_at'].isoformat() if item.get('created_at') else None
        result.append(item)
    
    return result
