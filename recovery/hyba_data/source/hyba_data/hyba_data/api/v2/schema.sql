-- ============================================================================
-- φ-GROVER ENTERPRISE DATABASE — ELEVATED SCHEMA
-- Version: 2.0.0
-- Compliance: GDPR, HIPAA, FedRAMP, FIPS 140-2
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "timescaledb";

CREATE SCHEMA IF NOT EXISTS tenant_1;
CREATE SCHEMA IF NOT EXISTS tenant_2;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    password_version INTEGER DEFAULT 1,
    roles TEXT[] DEFAULT '{user}',
    permissions TEXT[] DEFAULT '{}',
    region VARCHAR(50) NOT NULL,
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_secret VARCHAR(255),
    mfa_backup_codes TEXT[],
    last_login TIMESTAMP,
    login_count INTEGER DEFAULT 0,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    password_changed_at TIMESTAMP,
    email_verified BOOLEAN DEFAULT false,
    email_verification_token VARCHAR(255),
    reset_password_token VARCHAR(255),
    reset_password_expires TIMESTAMP,
    preferences JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(tenant_id, email),
    UNIQUE(tenant_id, username)
);

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    permissions TEXT[] NOT NULL DEFAULT '{"read"}',
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_hour INTEGER DEFAULT 3600,
    rate_limit_per_day INTEGER DEFAULT 86400,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE(user_id, name)
);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    device_id VARCHAR(255),
    device_name VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    location JSONB,
    expires_at TIMESTAMP NOT NULL,
    refresh_expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    event_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    actor_id UUID,
    actor_type VARCHAR(20) DEFAULT 'user',
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    request_id UUID,
    session_id UUID,
    previous_hash VARCHAR(64),
    hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    retention_until TIMESTAMP
);

CREATE TABLE workers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    pool_url VARCHAR(255) NOT NULL,
    pool_port INTEGER NOT NULL,
    pool_username VARCHAR(100),
    pool_password_encrypted VARCHAR(255),
    config JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'stopped',
    started_at TIMESTAMP,
    stopped_at TIMESTAMP,
    total_blocks_found INTEGER DEFAULT 0,
    total_shares_submitted INTEGER DEFAULT 0,
    total_hashes BIGINT DEFAULT 0,
    current_hash_rate FLOAT,
    average_hash_rate FLOAT,
    peak_hash_rate FLOAT,
    last_share_at TIMESTAMP,
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE(tenant_id, user_id, name)
);

CREATE TABLE mining_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(id) ON DELETE CASCADE,
    job_id VARCHAR(100) NOT NULL,
    prev_hash VARCHAR(64) NOT NULL,
    merkle_root VARCHAR(64) NOT NULL,
    version VARCHAR(8) NOT NULL,
    nbits VARCHAR(8) NOT NULL,
    ntime VARCHAR(10) NOT NULL,
    target BIGINT NOT NULL,
    difficulty FLOAT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    nonce_found INTEGER,
    block_hash VARCHAR(64),
    start_search_at TIMESTAMP,
    found_at TIMESTAMP,
    completed_at TIMESTAMP,
    search_time_ms INTEGER,
    quantum_walk_time_ms INTEGER,
    vqc_inference_time_ms INTEGER,
    confidence_score FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(worker_id, job_id)
);

CREATE TABLE quantum_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(id) ON DELETE CASCADE,
    job_id UUID REFERENCES mining_jobs(id) ON DELETE CASCADE,
    face_index INTEGER CHECK (face_index BETWEEN 0 AND 31),
    probability DOUBLE PRECISION,
    resonance_score DOUBLE PRECISION,
    curvature DOUBLE PRECISION,
    state_vector DOUBLE PRECISION[],
    eigenvalues DOUBLE PRECISION[],
    eigenvectors DOUBLE PRECISION[][],
    evolution_time DOUBLE PRECISION,
    manifold_type VARCHAR(50) DEFAULT 'M32',
    phi_power INTEGER DEFAULT 12,
    compression_ratio DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(worker_id, job_id, face_index)
);

CREATE TABLE vqc_parameters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    layer INTEGER NOT NULL,
    qubit INTEGER NOT NULL,
    param_index INTEGER NOT NULL,
    theta DOUBLE PRECISION NOT NULL,
    phi_scaled DOUBLE PRECISION,
    gradient DOUBLE PRECISION,
    momentum DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(worker_id, version, layer, qubit, param_index)
);

CREATE TABLE training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    dataset_id UUID,
    model_type VARCHAR(50) NOT NULL,
    model_config JSONB NOT NULL,
    training_config JSONB NOT NULL,
    compression_config JSONB,
    status VARCHAR(20) DEFAULT 'queued',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    failed_at TIMESTAMP,
    error_message TEXT,
    epochs_completed INTEGER DEFAULT 0,
    total_epochs INTEGER,
    best_accuracy DOUBLE PRECISION,
    best_loss DOUBLE PRECISION,
    final_accuracy DOUBLE PRECISION,
    final_loss DOUBLE PRECISION,
    training_time_seconds INTEGER,
    compression_ratio_used DOUBLE PRECISION,
    phi_power_used INTEGER,
    geodesic_used BOOLEAN,
    quantum_used BOOLEAN,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE compressed_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    original_size BIGINT NOT NULL,
    compressed_size BIGINT NOT NULL,
    compression_ratio DOUBLE PRECISION NOT NULL,
    phi_power INTEGER NOT NULL,
    fold_depth INTEGER NOT NULL,
    reconstruction_error DOUBLE PRECISION,
    manifold_type VARCHAR(50),
    coefficients DOUBLE PRECISION[],
    metadata JSONB DEFAULT '{}',
    encrypted BOOLEAN DEFAULT false,
    encryption_key_id VARCHAR(255),
    region VARCHAR(50) NOT NULL,
    retention_days INTEGER DEFAULT 90,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE found_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    worker_id UUID REFERENCES workers(id) ON DELETE CASCADE,
    job_id UUID REFERENCES mining_jobs(id) ON DELETE CASCADE,
    block_hash VARCHAR(64) NOT NULL,
    nonce INTEGER NOT NULL,
    block_height INTEGER,
    reward_amount DECIMAL(20, 8),
    transaction_fees DECIMAL(20, 8),
    total_reward DECIMAL(20, 8),
    status VARCHAR(20) DEFAULT 'pending',
    found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed BOOLEAN DEFAULT false,
    confirmed_at TIMESTAMP,
    payout_txid VARCHAR(64),
    payout_status VARCHAR(20) DEFAULT 'pending',
    payout_amount DECIMAL(20, 8),
    payout_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE performance_metrics (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    user_id UUID,
    worker_id UUID,
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    tags JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

SELECT create_hypertable('performance_metrics', 'time',
                         chunk_time_interval => INTERVAL '1 day');

CREATE MATERIALIZED VIEW metrics_hourly WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', time) AS bucket,
    tenant_id, user_id, worker_id, metric_name,
    AVG(value) AS avg_value, MAX(value) AS max_value, MIN(value) AS min_value,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) AS p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) AS p99,
    COUNT(*) AS sample_count
FROM performance_metrics
GROUP BY bucket, tenant_id, user_id, worker_id, metric_name
WITH NO DATA;

CREATE MATERIALIZED VIEW metrics_daily WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 day', time) AS bucket,
    tenant_id, user_id, worker_id, metric_name,
    AVG(value) AS avg_value, MAX(value) AS max_value, MIN(value) AS min_value,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) AS p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) AS p99,
    COUNT(*) AS sample_count
FROM performance_metrics
GROUP BY bucket, tenant_id, user_id, worker_id, metric_name
WITH NO DATA;

CREATE VIEW active_workers AS
SELECT
    w.id, w.user_id, w.name, w.status, w.current_hash_rate,
    w.average_hash_rate, w.total_blocks_found, w.total_shares_submitted,
    EXTRACT(EPOCH FROM (NOW() - w.started_at)) AS uptime_seconds,
    COUNT(mj.id) AS pending_jobs,
    AVG(pm.value) AS avg_hash_rate_1h
FROM workers w
LEFT JOIN mining_jobs mj ON w.id = mj.worker_id AND mj.status = 'pending'
LEFT JOIN performance_metrics pm ON w.id = pm.worker_id
    AND pm.metric_name = 'hash_rate' AND pm.time > NOW() - INTERVAL '1 hour'
WHERE w.status = 'running'
GROUP BY w.id;

CREATE VIEW user_dashboard AS
SELECT
    u.id AS user_id, u.username,
    COUNT(DISTINCT w.id) AS worker_count,
    COALESCE(SUM(w.total_blocks_found), 0) AS total_blocks,
    COALESCE(SUM(w.total_shares_submitted), 0) AS total_shares,
    COALESCE(AVG(w.current_hash_rate), 0) AS avg_hash_rate,
    COALESCE(SUM(w.total_hashes), 0) AS total_hashes,
    COUNT(DISTINCT t.id) AS training_jobs,
    COUNT(DISTINCT c.id) AS compressed_datasets
FROM users u
LEFT JOIN workers w ON u.id = w.user_id AND w.deleted_at IS NULL
LEFT JOIN training_jobs t ON u.id = t.user_id AND t.deleted_at IS NULL
LEFT JOIN compressed_data c ON u.id = c.user_id AND c.deleted_at IS NULL
GROUP BY u.id, u.username;
