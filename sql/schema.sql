-- ===========================================
--  FULL DDL SCHEMASI (V3 - Final)
-- ===========================================

-- 1. Eklentiler ve Tipler
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('PATIENT', 'CAREGIVER', 'ADMIN');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'measurement_status') THEN
        CREATE TYPE measurement_status AS ENUM ('NORMAL', 'WARNING', 'CRITICAL');
    END IF;
END$$;

-- 2. Users (Login)
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    role            user_role NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Patients (Hastalar)
CREATE TABLE IF NOT EXISTS patients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    birth_date      DATE,
    medical_info    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Caregivers (Bakıcılar)
CREATE TABLE IF NOT EXISTS caregivers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    phone_number    VARCHAR(30),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Patient-Caregiver İlişkisi
CREATE TABLE IF NOT EXISTS patient_caregiver (
    patient_id      UUID REFERENCES patients(id) ON DELETE CASCADE,
    caregiver_id    UUID UNIQUE REFERENCES caregivers(id) ON DELETE CASCADE,
    assigned_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (patient_id, caregiver_id)
);

-- 6. Patient Settings (Ayarlar - Yeni)
CREATE TABLE IF NOT EXISTS patient_settings (
    patient_id              UUID PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
    bpm_lower_limit         INT DEFAULT 50 CHECK (bpm_lower_limit > 0),
    bpm_upper_limit         INT DEFAULT 120 CHECK (bpm_upper_limit > bpm_lower_limit),
    max_inactivity_seconds  INT DEFAULT 900 CHECK (max_inactivity_seconds > 0),
    last_updated_by         UUID REFERENCES users(id),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Otomatik Ayar Oluşturma Trigger'ı
CREATE OR REPLACE FUNCTION create_default_settings()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO patient_settings (patient_id) VALUES (NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_create_settings_after_patient ON patients;
CREATE TRIGGER trg_create_settings_after_patient
AFTER INSERT ON patients
FOR EACH ROW EXECUTE FUNCTION create_default_settings();

-- 7. Measurements (Ölçümler)
CREATE TABLE IF NOT EXISTS measurements (
    id                  BIGSERIAL PRIMARY KEY,
    patient_id          UUID REFERENCES patients(id) ON DELETE CASCADE,
    heart_rate          INT NOT NULL CHECK (heart_rate BETWEEN 20 AND 300),
    inactivity_seconds  INT NOT NULL CHECK (inactivity_seconds >= 0),
    status              measurement_status NOT NULL,
    measured_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_measurements_patient_time ON measurements (patient_id, measured_at DESC);

-- 8. Emergency Logs (Acil Durum)
CREATE TABLE IF NOT EXISTS emergency_logs (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      UUID REFERENCES patients(id) ON DELETE CASCADE,
    message         TEXT NOT NULL,
    is_resolved     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_emergency_patient_time ON emergency_logs (patient_id, created_at DESC);

-- 9. ECG Segments (EKG - Array Yapısı)
CREATE TABLE IF NOT EXISTS ecg_segments (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      UUID REFERENCES patients(id) ON DELETE CASCADE,
    sample_rate     INT NOT NULL DEFAULT 250,
    started_at      TIMESTAMPTZ NOT NULL,
    duration_ms     INT NOT NULL,
    samples         SMALLINT[] NOT NULL, -- Binary Array (Optimize edildi)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ecg_patient_time ON ecg_segments (patient_id, started_at DESC);

-- 10. Sensor Data Queue (Redis yerine PostgreSQL Queue)
CREATE TABLE IF NOT EXISTS sensor_data_queue (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(50) NOT NULL,
    accelerometer   JSONB NOT NULL,
    gyroscope       JSONB NOT NULL,
    ppg_raw         INTEGER[] NOT NULL,
    timestamp       DOUBLE PRECISION NOT NULL,
    processed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_queue_unprocessed ON sensor_data_queue (processed, created_at) WHERE processed = FALSE;

-- 11. Patient States (Real-time Durum Takibi)
CREATE TABLE IF NOT EXISTS patient_states (
    patient_id      UUID PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
    last_movement_at TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 12. Seed Data (Demo için)
DO $$
DECLARE
    v_user_id UUID;
    v_patient_id UUID := 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
BEGIN
    -- Check if patient exists
    IF NOT EXISTS (SELECT 1 FROM patients WHERE id = v_patient_id) THEN
        -- Create User
        INSERT INTO users (username, password_hash, role)
        VALUES ('demo_patient', 'hash_placeholder', 'PATIENT')
        RETURNING id INTO v_user_id;

        -- Create Patient
        INSERT INTO patients (id, user_id, name, birth_date, medical_info)
        VALUES (v_patient_id, v_user_id, 'Ali Yılmaz', '1960-01-01', 'Hypertension')
        ON CONFLICT (id) DO NOTHING;
        
        -- Create Settings (Trigger handles it, but just in case or for custom values)
        -- UPDATE patient_settings SET bpm_lower_limit = 45 WHERE patient_id = v_patient_id;
    END IF;

    -- Check if caregiver exists
    IF NOT EXISTS (SELECT 1 FROM users WHERE username = 'demo_caregiver') THEN
        -- Create User (Caregiver)
        INSERT INTO users (username, password_hash, role)
        VALUES ('demo_caregiver', 'hash_placeholder', 'CAREGIVER')
        RETURNING id INTO v_user_id;

        -- Create Caregiver Profile
        INSERT INTO caregivers (user_id, name, phone_number)
        VALUES (v_user_id, 'Ayşe Hemşire', '+905551234567');

        -- Link to Demo Patient
        INSERT INTO patient_caregiver (patient_id, caregiver_id)
        SELECT v_patient_id, id FROM caregivers WHERE user_id = v_user_id;
    END IF;
END $$;

-- 13. Reporting Views
CREATE OR REPLACE VIEW v_live_heart_rates AS
SELECT 
    m.id,
    p.name AS patient_name,
    m.heart_rate,
    m.status,
    m.measured_at
FROM measurements m
JOIN patients p ON m.patient_id = p.id
ORDER BY m.measured_at DESC;