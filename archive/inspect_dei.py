import requests
import json
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

cik = "0000320193"  # AAPL

headers = {
    "User-Agent":
        "Eric Lockwood erlockwood16@gmail.com"
}

url = (
    f"https://data.sec.gov/api/"
    f"xbrl/companyfacts/"
    f"CIK{cik}.json"
)

response = requests.get(
    url,
    headers=headers,
    verify=False
)

data = response.json()

print("\nDEI TAGS\n")

for key in data["facts"]["dei"].keys():

    if "Share" in key:

        print(key)

        print(
            json.dumps(
                data["facts"]["dei"][key],
                indent=2
            )[:2000]
        )

        print("\n" + "=" * 60 + "\n")
