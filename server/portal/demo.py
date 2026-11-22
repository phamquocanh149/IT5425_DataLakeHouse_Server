"""Loopback-only demo IdP. Never mount this module in a production deployment."""

import base64
import hashlib
import html
import json
import secrets
import time
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from starlette.responses import HTMLResponse, RedirectResponse

from .app import install_portal
from .config import PortalConfig
from .store import PortalError


DEMO_USERS = {
    "viewer": ("Minh Anh · Viewer", "Viewer"),
    "operator": ("Hoàng Nam · Operator", "Operator"),
    "admin": ("Quản trị · Admin", "Admin"),
    "restricted": ("Khách · Chỉ xem Gold", "Viewer"),
}


def create_demo_app(config=None):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    config = config or PortalConfig(
        enabled=True,
        demo=True,
        origin="http://127.0.0.1:8010",
        oidc_issuer="http://127.0.0.1:8010/demo-idp",
        bootstrap_subject="admin",
    )
    if not config.demo or not config.oidc_issuer.startswith(
        config.origin.rstrip("/") + "/demo-idp"
    ):
        raise ValueError("Demo IdP requires explicit loopback config")
    app = FastAPI(title="Climate Atlas · Local OIDC demo")
    store = install_portal(app, config)
    seed_demo(store, config)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public.update(kid="local-demo", use="sig", alg="RS256")

    @app.get("/demo-idp/.well-known/openid-configuration")
    def discovery():
        return {
            "issuer": config.oidc_issuer,
            "authorization_endpoint": config.oidc_issuer + "/authorize",
            "token_endpoint": config.oidc_issuer + "/token",
            "jwks_uri": config.oidc_issuer + "/jwks",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "code_challenge_methods_supported": ["S256"],
        }

    @app.get("/demo-idp/jwks")
    def keys():
        return {"keys": [public]}

    @app.get("/demo-idp/authorize", response_class=HTMLResponse)
    def authorize(request: Request):
        params = dict(request.query_params)
        if (
            params.get("client_id") != config.oidc_client_id
            or params.get("redirect_uri") != config.callback
            or params.get("code_challenge_method") != "S256"
            or params.get("response_type") != "code"
        ):
            raise PortalError(400, "INVALID_OIDC_REQUEST")
        if not all(params.get(k) for k in ["state", "nonce", "code_challenge"]):
            raise PortalError(400, "INVALID_OIDC_REQUEST")
        flow = store.transient("idp_flow", "", params, 300)
        links = "".join(
            f'<a class="identity" href="/demo-idp/choose?{urlencode({"flow": flow, "subject": subject})}"><strong>{html.escape(name)}</strong><span>{role} · {"chỉ Gold, không download" if subject == "restricted" else "USDM Bronze / Silver / Gold"}</span></a>'
            for subject, (name, role) in DEMO_USERS.items()
        )
        return f"""<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Đăng nhập · Climate Atlas demo</title><style>body{{font:16px system-ui;background:#edf3f2;color:#183b37;margin:0;display:grid;place-items:center;min-height:100vh}}main{{max-width:500px;padding:40px}}h1{{font-size:32px}}p{{line-height:1.6}}.identity{{display:block;padding:18px 22px;border:1px solid #cadbd7;border-radius:12px;background:white;color:inherit;text-decoration:none;margin:12px 0}}.identity:hover{{border-color:#168674;background:#f5fffc}}span{{display:block;font-size:14px;margin-top:6px;color:#596e69}}small{{color:#75682a}}</style><main><small>OIDC DEMO · CHỈ LOCALHOST</small><h1>Chọn tài khoản demo</h1><p>Luồng Authorization Code + PKCE với token RSA. Đây là IdP thử nghiệm, không dùng để xác thực người dùng production.</p>{links}</main></html>"""

    @app.get("/demo-idp/choose")
    def choose(flow: str, subject: str):
        if subject not in DEMO_USERS:
            raise PortalError(400, "INVALID_OIDC_REQUEST")
        params = store.resolve(flow, "idp_flow", "", consume=True)
        code = store.transient("idp_code", "", params | {"subject": subject}, 60)
        return RedirectResponse(
            params["redirect_uri"] + "?" + urlencode({"code": code, "state": params["state"]}),
            status_code=303,
        )

    @app.post("/demo-idp/token")
    async def token(request: Request):
        form = await request.form()
        saved = store.resolve(str(form.get("code", "")), "idp_code", "", consume=True)
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(str(form.get("code_verifier", "")).encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        if (
            form.get("grant_type") != "authorization_code"
            or form.get("redirect_uri") != config.callback
            or form.get("client_id") != config.oidc_client_id
            or not secrets.compare_digest(challenge, saved["code_challenge"])
        ):
            raise PortalError(400, "INVALID_GRANT")
        now = int(time.time())
        encoded = jwt.encode(
            {
                "iss": config.oidc_issuer,
                "aud": config.oidc_client_id,
                "sub": saved["subject"],
                "name": DEMO_USERS[saved["subject"]][0],
                "nonce": saved["nonce"],
                "iat": now,
                "exp": now + 300,
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "local-demo"},
        )
        return {"id_token": encoded, "token_type": "Bearer", "expires_in": 300}

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
    for subject, (name, role) in DEMO_USERS.items():
        _, user = store.user_login(config.oidc_issuer, subject, name, config.bootstrap_subject)
        with store.db() as db:
            db.execute("DELETE FROM sessions WHERE user_id=?", (user["user_id"],))
            db.execute("UPDATE users SET role=? WHERE user_id=?", (role, user["user_id"]))
            for did in rel.catalog["datasets"]:
                for layer in ["gold"] if subject == "restricted" else ["bronze", "silver", "gold"]:
                    actions = ["read"] if subject == "restricted" else ["read", "download"]
                    db.execute(
                        "INSERT OR IGNORE INTO grants VALUES (?,?,?,?,1)",
                        (user["user_id"], did, layer, json.dumps(actions)),
                    )
    with store.db() as db:
        db.execute("INSERT INTO config VALUES ('demo_seeded','1')")
        store.audit(db, "demo-bootstrap", "seed_demo_accounts", None)
