import sqlite3
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

import requests

# ==========================================
# SEC Configuration
# ==========================================

HEADERS = {
    "User-Agent":
        "Eric Lockwood erlockwood16@gmail.com"
}

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Helper Function
# ==========================================

def get_latest_annual(us_gaap_item):

    try:

        units = us_gaap_item["units"]["USD"]

        annual_data = [
            item
            for item in units
            if item.get("fy")
        ]

        annual_data.sort(
            key=lambda x: x.get("fy", 0),
            reverse=True
        )

        if annual_data:

            latest = annual_data[0]

            return (
                latest["fy"],
                latest["val"]
            )

    except:

        return None, None

    return None, None


# ==========================================
# Revenue Mapping
# ==========================================

REVENUE_TAGS = [

    "RevenueFromContractWithCustomerExcludingAssessedTax",

    "SalesRevenueNet",

    "Revenues"

]

# ==========================================
# Net Income Mapping
# ==========================================

NET_INCOME_TAGS = [

    "NetIncomeLoss"

]

# ==========================================
# Assets Mapping
# ==========================================

ASSET_TAGS = [

    "Assets"

]

# ==========================================
# Liability Mapping
# ==========================================

LIABILITY_TAGS = [

    "Liabilities"

]

# ==========================================
# Load Companies
# ==========================================

cursor.execute("""
SELECT
    ticker,
    cik
FROM sec_company_map
ORDER BY ticker
""")

companies = cursor.fetchall()

print(
    f"\nLoading SEC data "
    f"for {len(companies)} companies\n"
)

# ==========================================
# Process Companies
# ==========================================

for company in companies:

    ticker = company[0]

    cik = company[1]

    print(
        f"Processing {ticker}"
    )

    try:
        import certifi

        url = (
            f"https://data.sec.gov/api/"
            f"xbrl/companyfacts/"
            f"CIK{cik}.json"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
            verify=False
        )

        response.raise_for_status()

        data = response.json()

        facts = data["facts"]["us-gaap"]

        # -------------------------
        # Revenue
        # -------------------------

        revenue = None
        fiscal_year = None

        for tag in REVENUE_TAGS:

            if tag in facts:

                fiscal_year, revenue = (
                    get_latest_annual(
                        facts[tag]
                    )
                )

                break

        # -------------------------
        # Net Income
        # -------------------------

        net_income = None

        for tag in NET_INCOME_TAGS:

            if tag in facts:

                _, net_income = (
                    get_latest_annual(
                        facts[tag]
                    )
                )

                break

        # -------------------------
        # Assets
        # -------------------------

        assets = None

        for tag in ASSET_TAGS:

            if tag in facts:

                _, assets = (
                    get_latest_annual(
                        facts[tag]
                    )
                )

                break

        # -------------------------
        # Liabilities
        # -------------------------

        liabilities = None

        for tag in LIABILITY_TAGS:

            if tag in facts:

                _, liabilities = (
                    get_latest_annual(
                        facts[tag]
                    )
                )

                break

        if not fiscal_year:

            print(
                f"No annual data found "
                f"for {ticker}"
            )

            continue

        cursor.execute("""
        INSERT OR REPLACE INTO sec_financials
        (
            ticker,
            fiscal_year,
            revenue,
            net_income,
            assets,
            liabilities
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ticker,
            fiscal_year,
            revenue,
            net_income,
            assets,
            liabilities
        ))

        conn.commit()

        print(
            f"Loaded {ticker} "
            f"FY{fiscal_year}"
        )

    except Exception as e:

        print(
            f"Error loading "
            f"{ticker}: {e}"
        )

# ==========================================
# Complete
# ==========================================

conn.close()

print(
    "\nSEC Financial Load Complete"
)
