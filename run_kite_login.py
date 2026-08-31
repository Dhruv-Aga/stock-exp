#!/usr/bin/env python3
"""
Generate Zerodha Kite access token (run once daily before market open).

Setup:
1. Create app at https://developers.kite.trade/
2. Add API key + secret to .env
3. Run: python run_kite_login.py
4. Open the login URL, authorize, copy request_token from redirect URL
5. Paste request_token when prompted
6. Copy printed KITE_ACCESS_TOKEN into .env

Docs: https://kite.trade/docs/connect/v3/
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import settings  # noqa: E402
from src.broker.kite_client import KiteClient  # noqa: E402


def main():
    settings.load_settings()
    if not settings.kite_api_key() or not settings.kite_api_secret():
        print(
            "Missing KITE_API_KEY or KITE_API_SECRET in .env\n\n"
            "Steps:\n"
            "1. Go to https://developers.kite.trade/ and create a Kite Connect app\n"
            "2. Subscribe to Kite Connect (~Rs 2000/month) on Zerodha\n"
            "3. Set redirect URL in app settings (e.g. http://127.0.0.1:8000/)\n"
            "4. Add to .env:\n"
            "   KITE_API_KEY=your_api_key\n"
            "   KITE_API_SECRET=your_api_secret\n"
            "5. Re-run this script\n"
        )
        sys.exit(1)

    client = KiteClient(dry_run=False)
    print("\n=== Zerodha Kite Login ===\n")
    print("Open this URL in your browser and log in:\n")
    print(client.login_url())
    print("\nAfter login, copy the request_token from the redirect URL.")
    print("Example: http://127.0.0.1:8000/?request_token=XXXX&action=login\n")

    request_token = input("Paste request_token here: ").strip()
    if not request_token:
        print("No request_token provided.")
        sys.exit(1)

    session = client.generate_session(request_token)
    access_token = session["access_token"]
    print("\nSuccess! Add this to your .env file:\n")
    print(f"KITE_ACCESS_TOKEN={access_token}")
    print("\nAccess token expires daily. Re-run this script each trading day.")
    print("Keep LIVE_TRADING=false until you finish paper-trading review.")


if __name__ == "__main__":
    main()
