
import os
import requests

KEY = os.getenv("ALPACA_API_KEY")
SECRET = os.getenv("ALPACA_API_SECRET")

if not KEY or not SECRET:
    raise SystemExit("Missing Alpaca credentials in GitHub Actions.")

HEADERS = {
    "APCA-API-KEY-ID": KEY,
    "APCA-API-SECRET-KEY": SECRET,
}

def test_connection(name, url, params=None):
    print(f"\nTesting: {name}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=20
        )

        print(f"HTTP status: {response.status_code}")

        if response.status_code == 200:
            print("SUCCESS - Endpoint accessible")
        elif response.status_code == 401:
            print("FAILED - Authentication rejected")
        elif response.status_code == 403:
            print("FAILED - Access forbidden")
        elif response.status_code == 404:
            print("NOT FOUND - Check endpoint")
        else:
            print("Endpoint returned another status")

    except requests.RequestException as exc:
        print(f"Connection error: {type(exc).__name__}")


print("KENNY SHADOW TRADER V2 - ALPACA CONNECTION TEST")
print("READ ONLY - NO REAL OR PAPER ORDERS")

test_connection(
    "Paper Trading Account",
    "https://paper-api.alpaca.markets/v2/account"
)

test_connection(
    "Stock Market Data",
    "https://data.alpaca.markets/v2/stocks/SPY/bars",
    {"timeframe": "1Day", "limit": 1}
)

test_connection(
    "Options Indicative Data",
    "https://data.alpaca.markets/v1beta1/options/snapshots/SPY",
    {"feed": "indicative", "limit": 1}
)

print("\nConnection tests complete.")
