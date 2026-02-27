CREATE TABLE IF NOT EXISTS semantic_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(32),
    agent_id VARCHAR(64),
    timestamp BIGINT,
    correlation_id VARCHAR(64),
    payload JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS causal_edges (
    from_event_id UUID NOT NULL,
    to_event_id UUID NOT NULL,
    reason VARCHAR(128),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (from_event_id, to_event_id),
    FOREIGN KEY (from_event_id) REFERENCES semantic_events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (to_event_id) REFERENCES semantic_events(event_id) ON DELETE CASCADE
);

CREATE INDEX idx_events_agent ON semantic_events(agent_id);
CREATE INDEX idx_events_correlation ON semantic_events(correlation_id);
CREATE INDEX idx_events_type ON semantic_events(event_type);