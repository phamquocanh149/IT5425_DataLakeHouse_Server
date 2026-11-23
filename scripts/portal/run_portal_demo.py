"""Start the USDM Portal demo on loopback. Never exposes the test IdP to the LAN."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def main():
    import uvicorn
    from climate_platform.api.portal.config import PortalConfig
    from climate_platform.api.portal.demo import create_demo_app

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8010)
    p.add_argument(
        "--portal-root", type=Path, default=Path(__file__).resolve().parents[2] / "data_lake/portal"
    )
    a = p.parse_args()
    origin = f"http://127.0.0.1:{a.port}"
    cfg = PortalConfig(
        enabled=True,
        demo=True,
        origin=origin,
        oidc_issuer=origin + "/demo-idp",
        storage_root=a.portal_root,
        bootstrap_subject="admin",
    )
    app = create_demo_app(cfg)
    print(f"Climate Atlas demo: {origin}/portal/", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=a.port, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
