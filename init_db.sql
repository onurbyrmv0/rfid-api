-- Create students table
CREATE TABLE IF NOT EXISTS students (
    card_uid VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create attendance_logs table
CREATE TABLE IF NOT EXISTS attendance_logs (
    id SERIAL PRIMARY KEY,
    card_uid VARCHAR(50) REFERENCES students(card_uid) ON DELETE CASCADE,
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
