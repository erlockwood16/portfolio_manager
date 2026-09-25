import requests
import sqlite3
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
# DATABASE
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# LOAD COMPANIES
# ==========================================

cursor.execute("""
SELECT
    ticker,
    cik
FROM sec_company_map
ORDER BY ticker
""")

companies = cursor.fetchall()

# ==========================================
# HELPER
# ==========================================

def print_tag_data(
        ticker,
        label,
        facts,
        tag_list):

    print("\n" + "=" * 80)
    print(f"{ticker} - {label}")
    print("=" * 80)

    tag_found = None

    for tag in tag_list:

        if tag in facts:

            tag_found = tag
            break

    if not tag_found:

        print("Tag Not Found")

        return

    print(
        f"\nUsing Tag: {tag_found}\n"
    )

    item = facts[tag_found]

    try:

        for unit_name in item["units"]:

            print(
                f"\nUnit: {unit_name}\n"
            )

            records = item["units"][unit_name]

            records = sorted(
                records,
                key=lambda x:
                (
                    x.get("fy", 0),
                    x.get("filed", "")
                ),
                reverse=True
            )

            for record in records[:20]:

                print(
                    f"FY={record.get('fy')} | "
                    f"FP={record.get('fp')} | "
                    f"Form={record.get('form')} | "
                    f"Filed={record.get('filed')} | "
                    f"Value={record.get('val')}"
                )

    except Exception as e:

        print(
            f"Error reading tag: {e}"
        )


# ==========================================
# PROCESS COMPANIES
# ==========================================

for company in companies:

    ticker = company[0]
    cik = company[1]

    print(
        "\n\n" + "#" * 100
    )

    print(
        f"CHECKING {ticker}"
    )

    print(
        "#" * 100
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
            verify=False,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        facts = data["facts"]["us-gaap"]

        # Revenue

        print_tag_data(
            ticker,
            "REVENUE",
            facts,
            REVENUE_TAGS
        )

        # Net Income

        print_tag_data(
            ticker,
            "NET INCOME",
            facts,
            NET_INCOME_TAGS
        )

        # Assets

        print_tag_data(
            ticker,
            "ASSETS",
            facts,
            ASSET_TAGS
        )

        # Liabilities

        print_tag_data(
            ticker,
            "LIABILITIES",
            facts,
            LIABILITY_TAGS
        )

    except Exception as e:

        print(
            f"Error checking {ticker}"
        )

        print(e)

conn.close()

print(
    "\nQuality Check Complete"
)
