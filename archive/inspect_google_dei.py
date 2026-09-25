# fundamentals/inspect_google_dei.py

import requests
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

url = (
    "https://data.sec.gov/api/"
    "xbrl/companyfacts/"
    "CIK0001652044.json"
)

headers = {
    "User-Agent":
        "Eric Lockwood erlockwood16@gmail.com"
}

response = requests.get(
    url,
    headers=headers,
    verify=False
)

data = response.json()

print("\nDEI TAGS\n")

for key in data["facts"]["dei"].keys():

    print(key)
