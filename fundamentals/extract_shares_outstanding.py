import sqlite3
import requests
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

# ==========================================
# CONFIG
# ==========================================

HEADERS = {
    "User-Agent":
        "Eric Lockwood erlockwood16@gmail.com"
}

# ==========================================
# DATABASE
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# TAGS
# ==========================================

DEI_SHARE_TAGS = [

    "EntityCommonStockSharesOutstanding",

    "CommonStockSharesOutstanding"

]

USGAAP_SHARE_TAGS = [

    "CommonStockSharesIssued",

    "CommonStockSharesOutstanding"

]

# ==========================================
# HELPER
# ==========================================

def extract_share_series(item):

    results = []

    try:

        for unit_name in item["units"]:

            records = item["units"][unit_name]

            for record in records:

                if record.get("fy"):

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
# COMPANIES
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
# PROCESS
# ==========================================

for company in companies:

    ticker = company[0]
    cik = company[1]

    print(
        f"\nProcessing {ticker}"
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

        shares_data = {}

        # ==================================
        # DEI FIRST
        # ==================================

        if "dei" in data["facts"]:

            dei_facts = data["facts"]["dei"]

            for tag in DEI_SHARE_TAGS:

                if tag in dei_facts:

                    print(
                        f"Using DEI tag: {tag}"
                    )

                    for fy, shares in extract_share_series(
                        dei_facts[tag]
                    ):

                        shares_data[fy] = shares

                    break

        # ==================================
        # FALLBACK TO US-GAAP
        # ==================================

        if not shares_data:

            if "us-gaap" in data["facts"]:

                us_gaap = data["facts"]["us-gaap"]

                for tag in USGAAP_SHARE_TAGS:

                    if tag in us_gaap:

                        print(
                            f"Using US-GAAP tag: {tag}"
                        )

                        for fy, shares in extract_share_series(
                            us_gaap[tag]
                        ):

                            shares_data[fy] = shares

                        break

        # ==================================
        # NO SHARES FOUND
        # ==================================

        if not shares_data:

            print(
                f"No share data found "
                f"for {ticker}"
            )

            continue

        # ==================================
        # UPDATE DATABASE
        # ==================================

        rows_updated = 0

        for fy, shares in shares_data.items():

            cursor.execute("""
            UPDATE sec_financials
            SET shares_outstanding = ?
            WHERE ticker = ?
              AND fiscal_year = ?
            """,
            (
                shares,
                ticker,
                fy
            ))

            rows_updated += cursor.rowcount

        conn.commit()

        print(
            f"{rows_updated} rows updated"
        )

    except Exception as e:

        print(
            f"Error processing {ticker}"
        )

        print(e)

conn.close()

print(
    "\nShare Extraction Complete"
)
