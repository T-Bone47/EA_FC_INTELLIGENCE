-- 003: Authentication sessions (additive).
-- JWT access tokens carry a jti that maps to a session row; logout revokes it.
-- This makes sessions server-revocable without sacrificing stateless verification.

CREATE TABLE IF NOT EXISTS user_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jti             TEXT NOT NULL UNIQUE,
    user_profile_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    user_agent      TEXT,
    ip_hash         TEXT      -- store a hash, never raw IPs
);
CREATE INDEX IF NOT EXISTS ix_session_user ON user_session (user_profile_id) WHERE revoked_at IS NULL;

-- rate-limit accounting (abuse protection)
CREATE TABLE IF NOT EXISTS api_rate_bucket (
    bucket_key      TEXT PRIMARY KEY,          -- e.g. 'login:ip:abc123'
    window_start    TIMESTAMPTZ NOT NULL,
    hits            INT NOT NULL DEFAULT 0
);
