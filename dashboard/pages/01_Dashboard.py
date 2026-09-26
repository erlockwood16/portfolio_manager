import sqlite3
import streamlit as st

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# -------------------------------------
# Buy Candidates
# -------------------------------------

cursor.execute("""
SELECT COUNT(*)
FROM buy_candidates
""")

candidate_count = cursor.fetchone()[0]

# -------------------------------------
# Queue
# -------------------------------------

cursor.execute("""
SELECT COUNT(*)
FROM research_queue
WHERE status='PENDING'
""")

pending = cursor.fetchone()[0]

# -------------------------------------
# Allocations
# -------------------------------------

cursor.execute("""
SELECT COUNT(*)
FROM recommended_allocations
""")

allocations = cursor.fetchone()[0]

# -------------------------------------
# Metrics
# -------------------------------------

col1, col2, col3 = st.columns(3)

col1.metric(
    "Buy Candidates",
    candidate_count
)

col2.metric(
    "Research Queue",
    pending
)

col3.metric(
    "Allocations",
    allocations
)

conn.close()