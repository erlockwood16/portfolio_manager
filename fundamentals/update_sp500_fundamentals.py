import sqlite3
import requests
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

# ==========================================
# Config
# ==========================================

BATCH_SIZE = 90

HEADERS = {
    "User-Agent":
        "InvestmentAdvisor/1.0 "
        "(erlockwood16@gmail.com)"
}

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Find Missing Companies
# ==========================================

cursor.execute("""
SELECT

    ticker,

    cik

FROM sec_company_map

WHERE ticker NOT IN (

    SELECT DISTINCT ticker

    FROM sec_financials

)

ORDER BY ticker

LIMIT ?
""",
(BATCH_SIZE,)
)

companies = cursor.fetchall()

if not companies:

    print(
        "\nAll SEC financials loaded."
    )

    conn.close()

    raise SystemExit

print("\n" + "=" * 70)

print(
    f"Processing {len(companies)} companies"
)

print("=" * 70)

# ==========================================
# Helper
# ==========================================

def extract_annual_series(item):

    results = []

    try:

        for unit_name in item["units"]:

            for record in item["units"][unit_name]:

                if (
                    record.get("form") == "10-K"
                    and record.get("fp") == "FY"
                    and record.get("fy")
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

REVENUE_TAGS = [

    "RevenueFromContractWithCustomerExcludingAssessedTax",

    "RevenueFromContractWithCustomerIncludingAssessedTax",

    "SalesRevenueNet",

    "Revenues"

]

# ==========================================
# Process Batch
# ==========================================

loaded_companies = 0

for ticker, cik in companies:

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
        assets_data = {}
        liabilities_data = {}

        # Revenue
        for tag in REVENUE_TAGS:

            if tag in facts:

                for fy, value in extract_annual_series(
                    facts[tag]
                ):

                    revenue_data[fy] = value

                break

        # Net Income

        if "NetIncomeLoss" in facts:

            for fy, value in extract_annual_series(
                facts["NetIncomeLoss"]
            ):

                income_data[fy] = value

        # Assets

        if "Assets" in facts:

            for fy, value in extract_annual_series(
                facts["Assets"]
            ):

                assets_data[fy] = value

        # Liabilities

        if "Liabilities" in facts:

            for fy, value in extract_annual_series(
                facts["Liabilities"]
            ):

                liabilities_data[fy] = value

        years = sorted(

            set(

                revenue_data.keys()

            )

            |

            set(

                income_data.keys()

            )

            |

            set(

                assets_data.keys()

            )

            |

            set(

                liabilities_data.keys()

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
            VALUES
            (
                ?, ?, ?, ?, ?, ?
            )
            """,
            (

                ticker,

                year,

                revenue_data.get(year),

                income_data.get(year),

                assets_data.get(year),

                liabilities_data.get(year)

            ))

            rows_loaded += 1

        conn.commit()

        loaded_companies += 1

        print(
            f"{ticker}: "
            f"{rows_loaded} years"
        )

    except Exception as e:

        print(
            f"ERROR: {ticker}"
        )

        print(e)

# ==========================================
# Summary
# ==========================================

cursor.execute("""
SELECT COUNT(DISTINCT ticker)
FROM sec_financials
""")

coverage = cursor.fetchone()[0]

conn.close()

print("\n" + "=" * 70)

print(
    f"Companies Loaded This Run: "
    f"{loaded_companies}"
)

print(
    f"SEC Coverage Total: "
    f"{coverage}"
)

print("=" * 70)
