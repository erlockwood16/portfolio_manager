import pandas as pd
import requests
from io import StringIO

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"

headers = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    )
}

response = requests.get(
    URL,
    headers=headers,
    timeout=30
)

response.raise_for_status()

tables = pd.read_html(
    StringIO(response.text)
)

sp400 = tables[0]

sp400.to_csv(
    "data/sp400.csv",
    index=False
)

print(
    f"Created data/sp400.csv "
    f"with {len(sp400)} rows"
)
