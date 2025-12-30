"""
Caregivers Router

Bakıcı (caregiver) bilgilerini ve atanmış hastaları getiren endpoint'ler.
Android uygulaması ile uyumlu API.
"""
from fastapi import APIRouter, HTTPException
from shared.database import db

router = APIRouter()


@router.get("/caregivers/{caregiver_id}")
async def get_caregiver(caregiver_id: str):
    """
    Bakıcı detay bilgisini getirir.
    
    Returns:
        - id: Bakıcı UUID
        - name: İsim
        - phone_number: Telefon
        - user_id: Bağlı kullanıcı ID
    """
    query = """
        SELECT c.id, c.user_id, c.name, c.phone_number, c.created_at
        FROM caregivers c
        WHERE c.id = $1
    """
    row = await db.fetch_one(query, caregiver_id)
    
    if row:
        result = dict(row)
        result['id'] = str(result['id'])
        result['user_id'] = str(result['user_id']) if result.get('user_id') else None
        result['created_at'] = result['created_at'].isoformat() if result.get('created_at') else None
        return result
    else:
        raise HTTPException(status_code=404, detail="Caregiver not found")


@router.get("/caregivers/{caregiver_id}/patients")
async def get_caregiver_patients(caregiver_id: str):
    """
    Bakıcıya atanmış tüm hastaları listeler.
    
    Returns:
        List of patients with:
        - id: Hasta UUID
        - name: Hasta adı
        - birth_date: Doğum tarihi
        - medical_info: Tıbbi bilgiler
        - assigned_at: Atanma zamanı
    """
    query = """
        SELECT p.id, p.name, p.birth_date, p.medical_info, p.created_at, pc.assigned_at
        FROM patients p
        JOIN patient_caregiver pc ON p.id = pc.patient_id
        WHERE pc.caregiver_id = $1
        ORDER BY pc.assigned_at DESC
    """
    rows = await db.fetch_all(query, caregiver_id)
    
    result = []
    for row in rows:
        item = dict(row)
        item['id'] = str(item['id'])
        item['birth_date'] = item['birth_date'].isoformat() if item.get('birth_date') else None
        item['created_at'] = item['created_at'].isoformat() if item.get('created_at') else None
        item['assigned_at'] = item['assigned_at'].isoformat() if item.get('assigned_at') else None
        result.append(item)
    
    return result
