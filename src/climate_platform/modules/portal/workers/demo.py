"""Loopback-only demo accounts. Never mount this module in a production deployment."""

import json
from urllib.parse import urlparse

from fastapi import FastAPI
from sqlalchemy import insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from climate_platform.entity.control import Config, Grant
from climate_platform.modules.portal.config import PortalConfig
from climate_platform.modules.portal.module import install_portal


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
        active = (
            db.execute(select(Config.value).where(Config.key == "active_release"))
            .mappings()
            .first()
        )
        seeded = (
            db.execute(select(Config.value).where(Config.key == "demo_seeded")).mappings().first()
        )
    if seeded:
        return
    if not active:
        raise ValueError("Prepare a Portal release before starting demo")
    from climate_platform.repositories.releases import Release

    rel = Release(config.storage_root, active["value"])
    for username, account in DEMO_USERS.items():
        user = store.ensure_user(
            username, account["password"], account["display_name"], account["role"]
        )
        with store.db() as db:
            for did in rel.catalog["datasets"]:
                for layer in ["gold"] if username == "restricted" else ["bronze", "silver", "gold"]:
                    actions = ["read"] if username == "restricted" else ["read", "download"]
                    db.execute(
                        sqlite_insert(Grant)
                        .values(
                            user_id=user["user_id"],
                            dataset_id=did,
                            layer=layer,
                            actions=json.dumps(actions),
                            version=1,
                        )
                        .on_conflict_do_nothing()
                    )
    with store.db() as db:
        db.execute(insert(Config).values(key="demo_seeded", value="1"))
        store.audit(db, "demo-bootstrap", "seed_demo_accounts", None)
