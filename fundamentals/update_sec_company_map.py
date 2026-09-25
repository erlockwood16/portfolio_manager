import sqlite3
import requests
import urllib3

# ==========================================
# SSL Configuration
# ==========================================

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

# ==========================================
# SEC Configuration
# ==========================================

HEADERS = {
    "User-Agent":
        "InvestmentAdvisor/1.0 "
        "(erlockwood16@gmail.com)"
}

SEC_TICKER_URL = (
    "https://www.sec.gov/files/company_tickers.json"
)

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Rebuild Table
# ==========================================

print(
    "\nRebuilding sec_company_map..."
)

cursor.execute("""
DROP TABLE IF EXISTS sec_company_map
""")

cursor.execute("""
CREATE TABLE sec_company_map (

    ticker TEXT PRIMARY KEY,

    cik TEXT,

    company_name TEXT

)
""")

conn.commit()

# ==========================================
# Load Watchlist
# ==========================================

cursor.execute("""
SELECT ticker
FROM watchlist
""")

watchlist = {

    row[0].upper()

    for row in cursor.fetchall()

}

print(
    f"\nWatchlist Size: "
    f"{len(watchlist)}"
)

# ==========================================
# Download SEC Company List
# ==========================================

print(
    "\nDownloading SEC company list..."
)

response = requests.get(

    SEC_TICKER_URL,

    headers=HEADERS,

    timeout=60,

    verify=False

)

print(
    f"HTTP Status: "
    f"{response.status_code}"
)

response.raise_for_status()

data = response.json()

print(
    f"SEC Companies Available: "
    f"{len(data)}"
)

# ==========================================
# Match Watchlist Tickers
# ==========================================

inserted = 0

for record in data.values():

    ticker = str(
        record["ticker"]
    ).upper()

    if ticker not in watchlist:

        continue

    cik = str(
        record["cik_str"]
    ).zfill(10)

    company_name = str(
        record["title"]
    ).strip()

    cursor.execute("""
    INSERT OR REPLACE
    INTO sec_company_map
    (
        ticker,

        cik,

        company_name
    )
    VALUES
    (
        ?, ?, ?
    )
    """,
    (
        ticker,
        cik,
        company_name
    ))

    inserted += 1

# ==========================================
# Save
# ==========================================

conn.commit()

# ==========================================
# Verification
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM sec_company_map
""")

total = cursor.fetchone()[0]

conn.close()

# ==========================================
# Summary
# ==========================================

print("\n" + "=" * 70)

print(
    "SEC COMPANY MAP UPDATE COMPLETE"
)

print("=" * 70)

print(
    f"\nCompanies Added : "
    f"{inserted}"
)

print(
    f"Total Mapping Rows : "
    f"{total}"
)

print("=" * 70)
