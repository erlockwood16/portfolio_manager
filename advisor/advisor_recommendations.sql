CREATE TABLE IF NOT EXISTS advisor_recommendations (
 recommendation_date TEXT NOT NULL, recommendation_type TEXT NOT NULL,
 ticker TEXT NOT NULL, current_weight_pct REAL, target_weight_pct REAL,
 weight_gap_pct REAL, recommendation_amount REAL NOT NULL DEFAULT 0,
 score REAL, priority_score REAL NOT NULL DEFAULT 0, rationale TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'PROPOSED', source TEXT NOT NULL,
 created_timestamp TEXT NOT NULL,
 PRIMARY KEY(recommendation_date,recommendation_type,ticker));
CREATE TABLE IF NOT EXISTS advisor_policy(policy_name TEXT PRIMARY KEY,policy_value REAL NOT NULL,description TEXT,updated_timestamp TEXT NOT NULL);
INSERT OR IGNORE INTO advisor_policy VALUES
('reserve_cash_pct',10,'Desired minimum cash percentage',CURRENT_TIMESTAMP),
('max_position_pct',10,'Maximum position weight',CURRENT_TIMESTAMP),
('buy_score_min',60,'Minimum buy score',CURRENT_TIMESTAMP),
('sell_score_max',35,'Sell review score',CURRENT_TIMESTAMP),
('minimum_trade_amount',100,'Minimum proposed trade',CURRENT_TIMESTAMP),
('max_new_position_pct',5,'Maximum new position weight',CURRENT_TIMESTAMP);
