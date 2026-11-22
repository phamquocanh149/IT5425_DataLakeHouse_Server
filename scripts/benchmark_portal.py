"""Opt-in loopback benchmark; creates then removes ten temporary read-only users."""

import argparse
import json
import platform
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from climate_platform.api.portal.releases import Release
from climate_platform.api.portal.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data_lake/portal"))
    parser.add_argument("--origin", default="http://127.0.0.1:8010")
    args = parser.parse_args()
    if urlparse(args.origin).hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Only loopback benchmarks are allowed")
    store = Store(args.root.resolve())
    with store.db() as db:
        rid = db.execute("SELECT value FROM config WHERE key='active_release'").fetchone()[0]
    rel = Release(args.root.resolve(), rid)
    did = next(iter(rel.catalog["datasets"]))
    week = max(o["source_date"] for o in rel.observations(did))
    users = []
    clients = []
    try:
        for _ in range(10):
            token, user = store.user_login(
                "local-benchmark", uuid.uuid4().hex, "Temporary benchmark", ""
            )
            users.append(user["user_id"])
            with store.db() as db:
                db.execute(
                    "INSERT INTO grants VALUES (?,?,?,?,1)",
                    (user["user_id"], did, "gold", '["read"]'),
                )
            client = httpx.Client(
                base_url=args.origin + "/api/portal/v1",
                cookies={"portal_session": token},
                timeout=20,
                trust_env=False,
            )
            clients.append(client)
            session = client.get("/session").json()
            client.headers.update({"Origin": args.origin, "X-CSRF-Token": session["csrf_token"]})
            selected = client.post(
                "/selections", json={"dataset_id": did, "week": week, "release_id": rid}
            )
            selected.raise_for_status()
            user["selection"] = selected.json()["selection_id"]
            user["client"] = client
            users[-1] = user

        def measure(user, route):
            start = time.perf_counter()
            response = user["client"].get(route.format(sid=user["selection"]))
            response.raise_for_status()
            return (time.perf_counter() - start) * 1000

        report = {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "users": 10,
            "release_id": rid,
            "results": {},
        }
        with ThreadPoolExecutor(max_workers=10) as pool:
            for name, route in [
                ("catalog", "/datasets"),
                ("preview", "/selections/{sid}/layers/gold/preview"),
                ("map", "/selections/{sid}/layers/gold/map"),
            ]:
                samples = list(pool.map(lambda user: measure(user, route), users))
                report["results"][name] = {
                    "requests": len(samples),
                    "p95_ms": round(sorted(samples)[-1], 1),
                    "errors": 0,
                }
        print(json.dumps(report, indent=2))
    finally:
        for client in clients:
            client.close()
        with store.db() as db:
            for user in users:
                uid = user["user_id"] if isinstance(user, dict) else user
                for table in ("sessions", "transient", "leases", "usage", "grants"):
                    db.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))
                db.execute("DELETE FROM users WHERE user_id=?", (uid,))


if __name__ == "__main__":
    main()
