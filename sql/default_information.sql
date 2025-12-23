-- ===========================================
--  DEFAULT DATA (Test Users)
-- ===========================================

-- 1. Patient User (Username: hasta1, Pass: 123456)
INSERT INTO users (username, password_hash, role)
VALUES ('hasta1', '123456', 'PATIENT')
ON CONFLICT (username) DO NOTHING;

-- 2. Caregiver User (Username: bakici1, Pass: 123456)
INSERT INTO users (username, password_hash, role)
VALUES ('bakici1', '123456', 'CAREGIVER')
ON CONFLICT (username) DO NOTHING;

-- 3. Patient Profile
INSERT INTO patients (user_id, name, birth_date, medical_info)
SELECT id, 'Ahmet Yılmaz', '1980-01-01', 'Hipertansiyon hastası'
FROM users WHERE username = 'hasta1'
ON CONFLICT (user_id) DO NOTHING;

-- 4. Caregiver Profile
INSERT INTO caregivers (user_id, name, phone_number)
SELECT id, 'Ayşe Demir', '+905551234567'
FROM users WHERE username = 'bakici1'
ON CONFLICT (user_id) DO NOTHING;

-- 5. Assign Caregiver to Patient
INSERT INTO patient_caregiver (patient_id, caregiver_id)
SELECT p.id, c.id
FROM patients p
JOIN users u_p ON p.user_id = u_p.id
CROSS JOIN caregivers c
JOIN users u_c ON c.user_id = u_c.id
WHERE u_p.username = 'hasta1' AND u_c.username = 'bakici1'
ON CONFLICT (patient_id, caregiver_id) DO NOTHING;