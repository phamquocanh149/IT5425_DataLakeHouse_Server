import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse, Response

from .store import PortalError, token_hash


def oidc_document(config):
    with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
        response = client.get(config.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration")
        response.raise_for_status()
        document = response.json()
    if document["issuer"] != config.oidc_issuer:
        raise PortalError(503, "OIDC_UNAVAILABLE")
    for field in ["authorization_endpoint", "token_endpoint", "jwks_uri"]:
        uri = urlparse(document[field])
        if uri.scheme != "https" and not (
            config.demo and uri.scheme == "http" and uri.hostname in {"127.0.0.1", "localhost"}
        ):
            raise PortalError(503, "OIDC_UNAVAILABLE")
    return document


def auth_router(config, store):
    router = APIRouter()

    @router.get("/auth/login")
    def login(request: Request, return_to: str = "/portal/"):
        if (
            not return_to.startswith("/portal/")
            or "\\" in return_to
            or any(ord(c) < 32 for c in return_to)
        ):
            raise PortalError(422, "INVALID_RETURN_URL")
        verifier = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(32)
        flow = store.transient(
            "oauth", "", {"verifier": verifier, "nonce": nonce, "return_to": return_to}, 300
        )
        document = oidc_document(config)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        response = RedirectResponse(
            document["authorization_endpoint"]
            + "?"
            + urlencode(
                {
                    "client_id": config.oidc_client_id,
                    "redirect_uri": config.callback,
                    "response_type": "code",
                    "scope": "openid profile",
                    "state": flow,
                    "nonce": nonce,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )
        response.set_cookie(
            "portal_login",
            flow,
            max_age=300,
            httponly=True,
            secure=config.secure_cookie,
            samesite="lax",
            path="/api/portal/v1/auth",
        )
        return response

    @router.get("/auth/callback")
    def callback(request: Request, code: str = "", state: str = ""):
        import jwt

        if (
            not state
            or not secrets.compare_digest(state, request.cookies.get("portal_login", ""))
            or not code
        ):
            raise PortalError(401, "OIDC_STATE_INVALID")
        flow = store.resolve(state, "oauth", "", consume=True)
        document = oidc_document(config)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.callback,
            "client_id": config.oidc_client_id,
            "code_verifier": flow["verifier"],
        }
        if config.oidc_client_secret:
            data["client_secret"] = config.oidc_client_secret
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            result = client.post(document["token_endpoint"], data=data)
            result.raise_for_status()
            encoded = result.json()["id_token"]
            try:
                header = jwt.get_unverified_header(encoded)
            except jwt.PyJWTError:
                raise PortalError(401, "OIDC_TOKEN_INVALID") from None
            if header.get("alg") != "RS256":
                raise PortalError(401, "OIDC_TOKEN_INVALID")
            keys_response = client.get(document["jwks_uri"])
            keys_response.raise_for_status()
            keys = keys_response.json()["keys"]
        try:
            key = next(
                k for k in keys if k.get("kid") == header.get("kid") and k.get("kty") == "RSA"
            )
            claims = jwt.decode(
                encoded,
                jwt.PyJWK.from_dict(key).key,
                algorithms=["RS256"],
                audience=config.oidc_client_id,
                issuer=config.oidc_issuer,
                options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce"]},
            )
            if not secrets.compare_digest(claims["nonce"], flow["nonce"]):
                raise ValueError("nonce")
            if (
                isinstance(claims["aud"], list)
                and len(claims["aud"]) > 1
                and claims.get("azp") != config.oidc_client_id
            ):
                raise ValueError("azp")
        except (jwt.PyJWTError, ValueError, StopIteration, KeyError, TypeError):
            raise PortalError(401, "OIDC_TOKEN_INVALID") from None
        token, _ = store.user_login(
            config.oidc_issuer,
            claims["sub"],
            claims.get("name", claims["sub"]),
            config.bootstrap_subject,
        )
        old = request.cookies.get("portal_session")
        if old:
            with store.db() as db:
                db.execute("DELETE FROM sessions WHERE token=?", (token_hash(old),))
        response = RedirectResponse(flow["return_to"], status_code=303)
        response.set_cookie(
            "portal_session",
            token,
            max_age=config.session_max_seconds,
            httponly=True,
            secure=config.secure_cookie,
            samesite="lax",
            path="/",
        )
        response.delete_cookie("portal_login", path="/api/portal/v1/auth")
        return response

    @router.get("/session")
    def session(request: Request):
        user = request.state.portal_user
        return {
            "user_id": user["user_id"],
            "display_name": user["display_name"],
            "role": user["role"],
            "csrf_token": user["csrf"],
            "demo": config.demo,
            "request_id": request.state.request_id,
        }

    @router.post("/auth/logout")
    def logout(request: Request):
        with store.db() as db:
            db.execute(
                "DELETE FROM sessions WHERE token=?",
                (token_hash(request.cookies.get("portal_session", "")),),
            )
            store.audit(
                db,
                request.state.portal_user["user_id"],
                "logout",
                None,
                request_id=request.state.request_id,
            )
        response = Response(status_code=204)
        response.delete_cookie("portal_session", path="/")
        return response

    return router
