"""Generate a high-entropy credential and its server-side hashed record offline."""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("key_id")
    parser.add_argument("--client-id", default="collector01")
    parser.add_argument("--role", choices=["collector", "admin"], default="collector")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--sources", default="usdm,noaa,usgs,nldas")
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error("days must be 1..365")
    secret = secrets.token_urlsafe(32)
    record = {
        "key_id": args.key_id,
        "secret_hash": hashlib.sha256(secret.encode()).hexdigest(),
        "client_id": args.client_id,
        "role": args.role,
        "sources": args.sources.split(",") if args.role == "collector" else [],
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=args.days)).isoformat(),
    }
    # Run only in a private terminal: this is the one-time credential output.
    print("SERVER_API_KEY=" + args.key_id + "." + secret)
    print("Server API_KEYS record: " + json.dumps(record))


if __name__ == "__main__":
    main()
