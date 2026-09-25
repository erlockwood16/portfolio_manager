# ingestion/test_massive.py

import requests

url = "https://api.massive.com/v2/aggs/ticker/AAPL/prev?apiKey=YOUR_API_KEY"

response = requests.get(url, timeout=30)

print(response.status_code)
print(response.text[:200])
