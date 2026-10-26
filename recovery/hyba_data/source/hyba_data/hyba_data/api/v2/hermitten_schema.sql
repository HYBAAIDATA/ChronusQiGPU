-- ============================================================================
-- HERMITTEN BILLING SCHEMA
-- Savings-based pricing: 25% of GPU memory/workload savings
-- ============================================================================

CREATE TABLE gpu_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    baseline_name VARCHAR(255) NOT NULL,
    gpu_model VARCHAR(50) NOT NULL,
    gpu_count INTEGER NOT NULL,
    memory_gb FLOAT NOT NULL,
    memory_bandwidth_gbps FLOAT,
    compute_tflops FLOAT,
    power_watts FLOAT,
    cost_per_hour FLOAT,
    cost_per_month FLOAT,
    workload_type VARCHAR(50),
    workload_description TEXT,
    measurement_period_days INTEGER DEFAULT 30,
    baseline_start TIMESTAMP NOT NULL,
    baseline_end TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, baseline_name)
);

CREATE INDEX idx_baselines_tenant ON gpu_baselines(tenant_id);
CREATE INDEX idx_baselines_user ON gpu_baselines(user_id);
CREATE INDEX idx_baselines_active ON gpu_baselines(is_active);

CREATE TABLE compressed_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    baseline_id UUID REFERENCES gpu_baselines(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id),
    gpu_model VARCHAR(50) NOT NULL,
    gpu_count INTEGER NOT NULL,
    memory_gb FLOAT NOT NULL,
    memory_saved_gb FLOAT,
    memory_saved_percent FLOAT,
    compute_time_saved_hours FLOAT,
    compute_time_saved_percent FLOAT,
    cost_saved FLOAT,
    cost_saved_percent FLOAT,
    phi_power_used INTEGER,
    fold_depth INTEGER,
    compression_ratio FLOAT,
    reconstruction_error FLOAT,
    workload_type VARCHAR(50),
    measurement_start TIMESTAMP NOT NULL,
    measurement_end TIMESTAMP NOT NULL,
    is_billable BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_compressed_usage_tenant ON compressed_usage(tenant_id);
CREATE INDEX idx_compressed_usage_user ON compressed_usage(user_id);
CREATE INDEX idx_compressed_usage_baseline ON compressed_usage(baseline_id);
CREATE INDEX idx_compressed_usage_period ON compressed_usage(measurement_start, measurement_end);

CREATE TABLE hermitten_bills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    invoice_id UUID REFERENCES invoices(id),
    subscription_id UUID REFERENCES subscriptions(id),
    billing_period_start TIMESTAMP NOT NULL,
    billing_period_end TIMESTAMP NOT NULL,
    baseline_gpu_count INTEGER,
    baseline_memory_gb FLOAT,
    baseline_cost FLOAT,
    compressed_gpu_count INTEGER,
    compressed_memory_gb FLOAT,
    compressed_cost FLOAT,
    gpu_savings_count INTEGER,
    gpu_savings_percent FLOAT,
    memory_savings_gb FLOAT,
    memory_savings_percent FLOAT,
    cost_savings FLOAT,
    cost_savings_percent FLOAT,
    hermitten_fee_percent FLOAT DEFAULT 25.0,
    hermitten_fee_amount FLOAT,
    customer_net_savings FLOAT,
    customer_net_percent FLOAT,
    total_original_cost FLOAT,
    total_compressed_cost FLOAT,
    total_savings FLOAT,
    total_hermitten_fee FLOAT,
    total_customer_benefit FLOAT,
    status VARCHAR(20) DEFAULT 'draft',
    payment_status VARCHAR(20) DEFAULT 'pending',
    breakdown JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP
);

CREATE INDEX idx_hermitten_bills_tenant ON hermitten_bills(tenant_id);
CREATE INDEX idx_hermitten_bills_user ON hermitten_bills(user_id);
CREATE INDEX idx_hermitten_bills_period ON hermitten_bills(billing_period_start, billing_period_end);
CREATE INDEX idx_hermitten_bills_status ON hermitten_bills(status);

CREATE TABLE workload_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    hermitten_fee_percent FLOAT DEFAULT 25.0,
    min_gpu_count INTEGER,
    max_gpu_count INTEGER,
    category_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO workload_categories (name, description, hermitten_fee_percent) VALUES
    ('training', 'AI/ML training workloads', 25.0),
    ('inference', 'AI/ML inference workloads', 20.0),
    ('simulation', 'Scientific simulation workloads', 30.0),
    ('mining', 'Cryptocurrency mining workloads', 15.0),
    ('quantum', 'Quantum computing workloads', 35.0),
    ('general', 'General GPU compute workloads', 25.0);

CREATE TABLE savings_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    billing_id UUID REFERENCES hermitten_bills(id),
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    baseline_cost FLOAT,
    compressed_cost FLOAT,
    savings_amount FLOAT,
    savings_percent FLOAT,
    hermitten_fee FLOAT,
    customer_savings FLOAT,
    compression_ratio_avg FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_savings_tenant ON savings_history(tenant_id);
CREATE INDEX idx_savings_user ON savings_history(user_id);
CREATE INDEX idx_savings_period ON savings_history(period_start, period_end);
