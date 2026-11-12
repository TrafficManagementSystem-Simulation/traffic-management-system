"""Run the app over HTTPS with TLS 1.2 or newer (PRJ-SR-001):  python scripts/run_https.py [port]

Creates a self-signed certificate in ./certs on first use (local demo only; browsers will warn).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from tms.common.config import get_settings  # noqa: E402
from tms.infra import tls  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    settings = get_settings()
    cert, key = ROOT / settings.tls_cert, ROOT / settings.tls_key
    if not (cert.exists() and key.exists()):
        tls.generate_self_signed(str(cert), str(key))
        print(f"Created self-signed certificate {cert}")
    config = uvicorn.Config("tms.main:create_app", factory=True, host="127.0.0.1",
                            port=port, ssl_certfile=str(cert), ssl_keyfile=str(key))
    config.load()                              # builds config.ssl, the context uvicorn will use
    tls.enforce_minimum_version(config.ssl)    # refuse anything older than TLS 1.2
    print(f"Serving on https://127.0.0.1:{port} (TLS 1.2 or newer)")
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
