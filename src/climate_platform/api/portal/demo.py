"""Loopback-only demo accounts. Never mount this module in a production deployment."""

import json
from urllib.parse import urlparse

from fastapi import FastAPI

from .app import install_portal
from .config import PortalConfig


DEMO_USERS = {
    "viewer": {
        "display_name": "Minh Anh · Viewer",
        "role": "Viewer",
        "password": "viewer-demo",
    },
    "operator": {
        "display_name": "Hoàng Nam · Operator",
        "role": "Operator",
        "password": "operator-demo",
    },
    "admin": {
        "display_name": "Quản trị · Admin",
        "role": "Admin",
        "password": "admin-demo",
    },
    "restricted": {
        "display_name": "Khách · Chỉ xem Gold",
        "role": "Viewer",
        "password": "restricted-demo",
    },
}


def create_demo_app(config=None):
    config = config or PortalConfig(
        enabled=True,
        demo=True,
        origin="http://127.0.0.1:8010",
        demo_accounts=DEMO_USERS,
    )
    parsed = urlparse(config.origin)
    if (
        not config.demo
        or parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
    ):
        raise ValueError("Demo requires explicit loopback config")
    app = FastAPI(title="Climate Atlas · Local demo")
    store = install_portal(app, config)
    seed_demo(store, config)
    return app


def seed_demo(store, config):
    with store.db() as db:
        active = db.execute("SELECT value FROM config WHERE key='active_release'").fetchone()
        seeded = db.execute("SELECT value FROM config WHERE key='demo_seeded'").fetchone()
    if seeded:
        return
    if not active:
        raise ValueError("Prepare a Portal release before starting demo")
    from .releases import Release

    rel = Release(config.storage_root, active[0])
    for username, account in DEMO_USERS.items():
        user = store.ensure_user(
            username, account["password"], account["display_name"], account["role"]
        )
        with store.db() as db:
            for did in rel.catalog["datasets"]:
                for layer in ["gold"] if username == "restricted" else ["bronze", "silver", "gold"]:
                    actions = ["read"] if username == "restricted" else ["read", "download"]
                    db.execute(
                        "INSERT OR IGNORE INTO grants VALUES (?,?,?,?,1)",
                        (user["user_id"], did, layer, json.dumps(actions)),
                    )
    with store.db() as db:
        db.execute("INSERT INTO config VALUES ('demo_seeded','1')")
        store.audit(db, "demo-bootstrap", "seed_demo_accounts", None)
