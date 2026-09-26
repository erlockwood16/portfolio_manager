import sqlite3

from datetime import datetime

# ==========================================
# Database Connection
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Load Research Queue
# ==========================================

cursor.execute("""
SELECT
    ticker,
    overall_score,
    recommendation
FROM research_queue
WHERE status = 'PENDING'
ORDER BY overall_score DESC
""")

research_items = cursor.fetchall()

if not research_items:

    print("No pending research items")

    conn.close()

    exit()

# ==========================================
# Process Research Queue
# ==========================================

for item in research_items:

    ticker = item[0]

    recommendation = item[2]

    # ==========================================
    # Load Analytics Data
    # ==========================================

    cursor.execute("""
    SELECT
        current_price,
        sma20,
        sma50,
        sma200,
        momentum_score,
        volatility,
        overall_score,
        value_score,
        quality_score,
        growth_score
    FROM analytics_scores
    WHERE ticker = ?
    """,
    (ticker,)
    )

    analytics = cursor.fetchone()

    if not analytics:

        print(
            f"No analytics found for {ticker}"
        )

        continue

    current_price = analytics[0]
    sma20 = analytics[1]
    sma50 = analytics[2]
    sma200 = analytics[3]
    momentum = analytics[4]
    volatility = analytics[5]
    score = analytics[6]

    value_score = analytics[7]
    quality_score = analytics[8]
    growth_score = analytics[9]

    # ==========================================
    # Load Fundamentals
    # ==========================================

    cursor.execute("""
    SELECT
        pe_ratio,
        revenue_growth,
        earnings_growth,
        debt_to_equity,
        roe
    FROM fundamentals
    WHERE ticker = ?
    """,
    (ticker,)
    )

    fundamentals = cursor.fetchone()

    if fundamentals:

        pe_ratio = fundamentals[0]
        revenue_growth = fundamentals[1]
        earnings_growth = fundamentals[2]
        debt_to_equity = fundamentals[3]
        roe = fundamentals[4]

    else:

        pe_ratio = "N/A"
        revenue_growth = "N/A"
        earnings_growth = "N/A"
        debt_to_equity = "N/A"
        roe = "N/A"

    # ==========================================
    # Trend Analysis
    # ==========================================

    trend_signals = []

    if current_price > sma20:
        trend_signals.append(
            "Price Above SMA20"
        )

    if current_price > sma50:
        trend_signals.append(
            "Price Above SMA50"
        )

    if current_price > sma200:
        trend_signals.append(
            "Price Above SMA200"
        )

    trend_text = (
        ", ".join(trend_signals)
        if trend_signals
        else "No bullish trend signals"
    )

    # ==========================================
    # Risk Assessment
    # ==========================================

    if volatility < 25:

        risk_level = "LOW"

    elif volatility < 40:

        risk_level = "MEDIUM"

    else:

        risk_level = "HIGH"

    # ==========================================
    # Fundamental Assessment
    # ==========================================

    observations = []

    if isinstance(pe_ratio, (int, float)):

        if pe_ratio < 20:

            observations.append(
                "Attractive valuation"
            )

        elif pe_ratio < 35:

            observations.append(
                "Reasonable valuation"
            )

        else:

            observations.append(
                "Elevated valuation"
            )

    if isinstance(revenue_growth, (int, float)):

        if revenue_growth > 15:

            observations.append(
                "Strong revenue growth"
            )

        elif revenue_growth > 5:

            observations.append(
                "Moderate revenue growth"
            )

        else:

            observations.append(
                "Limited revenue growth"
            )

    if isinstance(debt_to_equity, (int, float)):

        if debt_to_equity < 0.5:

            observations.append(
                "Conservative balance sheet"
            )

        else:

            observations.append(
                "Higher financial leverage"
            )

    fundamental_summary = "\n".join(
        observations
    )

    # ==========================================
    # Recommendation Narrative
    # ==========================================

    if score >= 85:

        recommendation_text = (
            "Candidate demonstrates strong "
            "fundamental and technical characteristics."
        )

    elif score >= 70:

        recommendation_text = (
            "Candidate demonstrates positive "
            "investment characteristics."
        )

    else:

        recommendation_text = (
            "Candidate requires further review."
        )

    # ==========================================
    # Memo
    # ==========================================

    memo = f"""
==================================================
INVESTMENT RESEARCH MEMO
==================================================

Ticker:
{ticker}

Date:
{datetime.today().strftime('%Y-%m-%d')}

==================================================
TECHNICAL ANALYSIS
==================================================

Current Price:
${current_price:.2f}

Momentum Score:
{momentum:.2f}

Volatility:
{volatility:.2f}%

Overall Score:
{score:.2f}

Trend Signals:
{trend_text}

==================================================
FUNDAMENTAL ANALYSIS
==================================================

PE Ratio:
{pe_ratio}

Revenue Growth:
{revenue_growth}

Earnings Growth:
{earnings_growth}

Debt To Equity:
{debt_to_equity}

ROE:
{roe}

--------------------------------------------------

Value Score:
{value_score}

Quality Score:
{quality_score}

Growth Score:
{growth_score}

--------------------------------------------------

Assessment:

{fundamental_summary}

==================================================
RISK ASSESSMENT
==================================================

Risk Level:
{risk_level}

==================================================
RECOMMENDATION
==================================================

{recommendation_text}

Recommended Next Actions:

1. Review latest earnings call
2. Review valuation assumptions
3. Study competitive advantages
4. Determine position size
5. Compare with existing portfolio holdings

==================================================
"""

    # ==========================================
    # Save Memo
    # ==========================================

    cursor.execute("""
    INSERT OR REPLACE INTO research_memos
    (
        ticker,
        memo_date,
        recommendation,
        overall_score,
        memo_text
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        ticker,
        datetime.today().strftime(
            "%Y-%m-%d"
        ),
        recommendation,
        score,
        memo
    ))

    print(
        f"Memo created for {ticker}"
    )

# ==========================================
# Commit Changes
# ==========================================

conn.commit()

conn.close()

print(
    "\nResearch memos generated."
)
