import sqlite3
import requests
import certifi
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

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

def extract_annual_series(item):

    results = []

    try:

        for unit_name in item["units"]:

            records = item["units"][unit_name]

            for record in records:

                # Only Annual Filings

                if (
                    record.get("form") == "10-K"
                    and
                    record.get("fp") == "FY"
                    and
                    record.get("fy")
                ):

                    results.append(
                        (
                            record["fy"],
                            record["val"]
                        )
                    )

    except Exception:

        pass

    return results

# ==========================================
# SEC Tag Maps
# ==========================================

REVENUE_TAGS = [

    "RevenueFromContractWithCustomerExcludingAssessedTax",

    "RevenueFromContractWithCustomerIncludingAssessedTax",

    "SalesRevenueNet",

    "Revenues"

]

NET_INCOME_TAGS = [

    "NetIncomeLoss"

]

ASSET_TAGS = [

    "Assets"

]

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
    f"\nProcessing "
    f"{len(companies)} companies\n"
)

# ==========================================
# Process Companies
# ==========================================

for company in companies:

    ticker = company[0]
    cik = company[1]

    print(
        f"\nLoading {ticker}"
    )

    try:

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

        revenue_data = {}
        income_data = {}
        asset_data = {}
        liability_data = {}

        # -------------------------
        # Revenue
        # -------------------------

        for tag in REVENUE_TAGS:

            if tag in facts:

                for fy, value in extract_annual_series(
                    facts[tag]
                ):

                    revenue_data[fy] = value

                break

        # -------------------------
        # Net Income
        # -------------------------

        for tag in NET_INCOME_TAGS:

            if tag in facts:

                for fy, value in extract_annual_series(
                    facts[tag]
                ):

                    income_data[fy] = value

        # -------------------------
        # Assets
        # -------------------------

        for tag in ASSET_TAGS:

            if tag in facts:

                for fy, value in extract_annual_series(
                    facts[tag]
                ):

                    asset_data[fy] = value

        # -------------------------
        # Liabilities
        # -------------------------

        for tag in LIABILITY_TAGS:

            if tag in facts:

                for fy, value in extract_annual_series(
                    facts[tag]
                ):

                    liability_data[fy] = value

        # -------------------------
        # Merge Years
        # -------------------------

        years = sorted(

            set(
                list(revenue_data.keys())
                + list(income_data.keys())
                + list(asset_data.keys())
                + list(liability_data.keys())
            ),

            reverse=True

        )

        rows_loaded = 0

        for year in years:

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
                year,

                revenue_data.get(year),

                income_data.get(year),

                asset_data.get(year),

                liability_data.get(year)
            ))

            rows_loaded += 1

        conn.commit()

        print(
            f"{ticker}: "
            f"{rows_loaded} years loaded"
        )

    except Exception as e:

        print(
            f"Error loading {ticker}: {e}"
        )

conn.close()

print(
    "\nMulti-Year SEC Load Complete"
)
