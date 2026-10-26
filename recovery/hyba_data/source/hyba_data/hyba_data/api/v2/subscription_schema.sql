-- ============================================================================
-- SUBSCRIPTION & BILLING SCHEMA
-- Version: 2.0.0
-- ============================================================================

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tier VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    billing_period VARCHAR(20) DEFAULT 'monthly',
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    trial_end_date TIMESTAMP,
    auto_renew BOOLEAN DEFAULT true,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    plan_name VARCHAR(100),
    plan_version INTEGER DEFAULT 1,
    custom_quota JSONB,
    custom_features JSONB,
    pricing_override JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE(tenant_id, user_id)
);

CREATE INDEX idx_subscriptions_tenant ON subscriptions(tenant_id);
CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_tier ON subscriptions(tier);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_end_date ON subscriptions(end_date);

CREATE TABLE subscription_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    used_amount BIGINT NOT NULL DEFAULT 0,
    quota_limit BIGINT NOT NULL,
    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(subscription_id, metric_name, period_start)
);

CREATE INDEX idx_usage_subscription ON subscription_usage(subscription_id);
CREATE INDEX idx_usage_metric ON subscription_usage(metric_name);
CREATE INDEX idx_usage_period ON subscription_usage(period_start, period_end);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE CASCADE,
    invoice_number VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    amount DECIMAL(20, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    tax_amount DECIMAL(20, 2) DEFAULT 0,
    tax_rate DECIMAL(5, 2),
    discount_amount DECIMAL(20, 2) DEFAULT 0,
    discount_code VARCHAR(100),
    description TEXT,
    billing_address JSONB,
    payment_method VARCHAR(50),
    stripe_invoice_id VARCHAR(255),
    stripe_payment_intent_id VARCHAR(255),
    due_date TIMESTAMP NOT NULL,
    paid_date TIMESTAMP,
    sent_date TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invoices_tenant ON invoices(tenant_id);
CREATE INDEX idx_invoices_user ON invoices(user_id);
CREATE INDEX idx_invoices_subscription ON invoices(subscription_id);
CREATE INDEX idx_invoices_number ON invoices(invoice_number);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_due_date ON invoices(due_date);

CREATE TABLE payment_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    stripe_payment_method_id VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    last4 VARCHAR(4),
    expiry_month INTEGER,
    expiry_year INTEGER,
    card_brand VARCHAR(50),
    bank_name VARCHAR(255),
    is_default BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payment_methods_user ON payment_methods(user_id);
CREATE INDEX idx_payment_methods_default ON payment_methods(is_default) WHERE is_default = true;

CREATE TABLE usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    amount INTEGER NOT NULL DEFAULT 1,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_events_subscription ON usage_events(subscription_id);
CREATE INDEX idx_usage_events_type ON usage_events(event_type);
CREATE INDEX idx_usage_events_created ON usage_events(created_at DESC);
CREATE INDEX idx_usage_events_metric ON usage_events(metric_name);

CREATE TABLE discounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(20) NOT NULL,
    value DECIMAL(20, 2) NOT NULL,
    max_uses INTEGER,
    current_uses INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    valid_tiers TEXT[],
    valid_tenants TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_discounts_code ON discounts(code);
CREATE INDEX idx_discounts_expires ON discounts(expires_at) WHERE expires_at IS NOT NULL;

CREATE MATERIALIZED VIEW usage_daily WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 day', created_at) AS bucket,
    tenant_id, user_id, subscription_id, metric_name,
    SUM(amount) AS total_usage,
    COUNT(*) AS event_count
FROM usage_events
GROUP BY bucket, tenant_id, user_id, subscription_id, metric_name
WITH NO DATA;

CREATE VIEW subscription_status AS
SELECT
    s.id, s.tenant_id, s.user_id, u.username, s.tier, s.status,
    s.start_date, s.end_date,
    s.auto_renew, s.stripe_subscription_id,
    COUNT(i.id) AS invoices_count,
    COALESCE(SUM(i.amount), 0) AS total_billed
FROM subscriptions s
LEFT JOIN users u ON s.user_id = u.id
LEFT JOIN subscription_usage us ON s.id = us.subscription_id AND us.metric_name = 'api_calls'
LEFT JOIN invoices i ON s.id = i.subscription_id AND i.status = 'paid'
WHERE s.deleted_at IS NULL
GROUP BY s.id, u.username, us.used_amount;
