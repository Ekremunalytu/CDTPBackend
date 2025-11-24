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
    caregiver_id    UUID REFERENCES caregivers(id) ON DELETE CASCADE,
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