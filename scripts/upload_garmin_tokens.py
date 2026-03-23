"""
Generate Garmin tokens locally and upload to the production server.

Run this from a residential IP (not a cloud server) to bypass Garmin's
rate limiting on cloud provider IP ranges.

Usage:
    pip install garminconnect   # if not already installed
    python scripts/upload_garmin_tokens.py

    # Or just dump tokens to paste in the Settings UI:
    python scripts/upload_garmin_tokens.py --dump
"""
import argparse
import getpass
import hashlib
import json
import sys
import urllib.request
import urllib.error

from garminconnect import Garmin


def login_garmin(email: str, password: str) -> Garmin:
    """Login to Garmin Connect from local machine."""
    print(f"Logging in as {email}...")
    client = Garmin(email, password)
    client.login()
    print(f"Login successful! Display name: {client.display_name}")
    return client


def get_token_data(client: Garmin) -> str:
    """Extract serialized token data from authenticated client."""
    return client.garth.dumps()


def upload_tokens(server_url: str, auth_password: str, token_data: str):
    """Upload tokens to the server."""
    # Generate auth cookie
    token_hash = hashlib.sha256(f"thecoach:{auth_password}".encode()).hexdigest()

    url = f"{server_url}/api/sync/garmin-tokens"
    body = json.dumps({"token_data": token_data}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Cookie": f"tc_auth={token_hash}",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        print(f"Upload successful! Server says: display_name={result.get('display_name')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Upload failed: HTTP {e.code} - {body}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate and upload Garmin tokens")
    parser.add_argument("--dump", action="store_true",
                        help="Just print token JSON (for pasting in Settings UI)")
    parser.add_argument("--email", help="Garmin email (or will prompt)")
    parser.add_argument("--server", help="Server URL (e.g. https://tc.validalpha.ai)")
    args = parser.parse_args()

    # Get credentials
    email = args.email or input("Garmin email: ")
    password = getpass.getpass("Garmin password: ")

    # Login locally
    client = login_garmin(email, password)
    token_data = get_token_data(client)

    if args.dump:
        print("\n--- Token data (copy everything below) ---")
        print(token_data)
        print("--- End token data ---")
        return

    # Upload to server
    server = args.server or input("Server URL [https://tc.validalpha.ai]: ").strip()
    if not server:
        server = "https://tc.validalpha.ai"
    server = server.rstrip("/")

    auth_password = getpass.getpass("Server auth password: ")
    upload_tokens(server, auth_password, token_data)

    # Verify by triggering a sync
    print("\nTriggering a test sync...")
    token_hash = hashlib.sha256(f"thecoach:{auth_password}".encode()).hexdigest()
    req = urllib.request.Request(
        f"{server}/api/sync/garmin",
        data=b"",
        headers={
            "Content-Type": "application/json",
            "Cookie": f"tc_auth={token_hash}",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read().decode())
        print(f"Sync result: {result['activities_synced']} activities, "
              f"{result['health_days_synced']} health days")
        if result.get("errors"):
            print(f"Errors: {result['errors']}")
    except Exception as e:
        print(f"Sync request failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
