"""Test client upload script for Climate Data Lake Server.

Simulates Client 01 or Client 02 uploading climate datasets to the Bronze Ingestion API.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_SERVER_URL = "http://127.0.0.1:8000"
DEFAULT_COLLECTOR_KEY = os.getenv("COLLECTOR_API_KEY", "")


def compute_local_sha256(filepath: Path) -> str:
    """Compute SHA-256 of local file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_sample_dataset(file_path: Path) -> None:
    """Create a sample US Drought Monitor CSV dataset."""
    sample_content = (
        "date,fips,county_name,state,none,d0,d1,d2,d3,d4\n"
        "2021-06-22,01001,Autauga County,AL,100.0,0.0,0.0,0.0,0.0,0.0\n"
        "2021-06-22,01003,Baldwin County,AL,85.2,14.8,0.0,0.0,0.0,0.0\n"
        "2021-06-22,04013,Maricopa County,AZ,0.0,100.0,92.5,75.1,45.0,12.3\n"
        "2021-06-22,06037,Los Angeles County,CA,0.0,100.0,100.0,88.4,52.1,0.0\n"
    )
    file_path.write_text(sample_content, encoding="utf-8")
    print(f"[*] Created synthetic sample file: {file_path}")


def main():
    parser = argparse.ArgumentParser(description="Climate Data Lake Upload Test Client")
    parser.add_argument("--url", default=DEFAULT_SERVER_URL, help=f"Server base URL (default: {DEFAULT_SERVER_URL})")
    parser.add_argument("--file", type=str, default=None, help="Path to file to upload (creates demo file if omitted)")
    parser.add_argument(
        "--source",
        choices=["usdm", "noaa", "usgs", "nldas"],
        default="usdm",
        help="Climate data source category (default: usdm)",
    )
    parser.add_argument(
        "--source-date",
        default="2021-06-22",
        help="Observation date in YYYY-MM-DD (default: 2021-06-22)",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_COLLECTOR_KEY,
        help="Client API Key for X-API-Key header",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Query GET /uploads to list already ingested files",
    )

    args = parser.parse_args()
    if not args.api_key:
        parser.error("Set COLLECTOR_API_KEY in .env or the environment, or supply --api-key")
    headers = {"X-API-Key": args.api_key}

    # If --list flag is provided, fetch list of uploaded files
    if args.list:
        print(f"\n[+] Querying {args.url}/uploads (Filter: source={args.source})...")
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{args.url}/uploads", headers=headers, params={"source": args.source})
                print(f"[+] HTTP Status: {res.status_code}")
                if res.status_code == 200:
                    records = res.json()
                    print(f"[+] Total records found: {len(records)}")
                    print(json.dumps(records, indent=2))
                else:
                    print(f"[-] Error: {res.text}")
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            sys.exit(1)
        return

    # Prepare file for upload
    target_file: Path
    created_temp_sample = False
    if args.file:
        target_file = Path(args.file)
        if not target_file.exists():
            print(f"[-] Error: Specified file does not exist: {target_file}")
            sys.exit(1)
    else:
        target_file = Path("sample_usdm_drought.csv")
        create_sample_dataset(target_file)
        created_temp_sample = True

    local_sha = compute_local_sha256(target_file)
    file_size = target_file.stat().st_size

    print("\n" + "=" * 60)
    print(" CLIMATE DATA LAKE - CLIENT UPLOAD TEST")
    print("=" * 60)
    print(f" Target Server : {args.url}/upload")
    print(f" Source Type   : {args.source}")
    print(f" Source Date   : {args.source_date}")
    print(f" Local File    : {target_file.name} ({file_size} bytes)")
    print(f" Local SHA-256 : {local_sha}")
    print(" X-API-Key     : [REDACTED]")
    print("=" * 60)

    try:
        with open(target_file, "rb") as f:
            files = {"file": (target_file.name, f, "text/csv")}
            data = {"source": args.source, "source_date": args.source_date}

            with httpx.Client(timeout=30.0) as client:
                print("\n[*] Sending multipart/form-data POST request...")
                response = client.post(
                    f"{args.url}/upload",
                    headers=headers,
                    data=data,
                    files=files,
                )

        print(f"\n[+] HTTP Response Status: {response.status_code}")
        try:
            res_data = response.json()
            print("[+] Server Response Body:")
            print(json.dumps(res_data, indent=2))

            if response.status_code == 200:
                server_status = res_data.get("status")
                meta = res_data.get("metadata", {})
                server_sha = meta.get("sha256")

                if server_sha == local_sha:
                    print("\n[SUCCESS] SHA-256 Verification: MATCH!")
                else:
                    print(f"\n[WARNING] SHA-256 Mismatch: Local={local_sha} vs Server={server_sha}")

                if server_status == "VERIFIED":
                    print("[SUCCESS] Dataset ingested successfully into Bronze Data Lake.")
                    print(f"          Storage Path : {meta.get('stored_path')}")
                    print(f"          File ID      : {meta.get('file_id')}")
                elif server_status == "DUPLICATE":
                    print("[INFO] Server recognized duplicate file checksum. No redundant copy saved.")
            else:
                print(f"[-] Server returned error code {response.status_code}")

        except Exception:
            print(f"[*] Raw Response: {response.text}")

    except httpx.ConnectError:
        print(f"\n[-] Could not connect to server at {args.url}.")
        print("    Make sure the server is running with:")
        print("    uvicorn server.main:app --host 127.0.0.1 --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"\n[-] Unexpected error during upload: {e}")
        sys.exit(1)
    finally:
        # Clean up synthetic demo file if created
        if created_temp_sample and target_file.exists():
            try:
                target_file.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
