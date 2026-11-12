"""Run the app over plain HTTP:  python scripts/run_server.py [host] [port]

Host and port come from the settings (TMS_HOST, TMS_PORT, or the file named by TMS_ENV_FILE) unless given here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from tms.common.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    host = sys.argv[1] if len(sys.argv) > 1 else settings.host
    port = int(sys.argv[2]) if len(sys.argv) > 2 else settings.port
    uvicorn.run("tms.main:create_app", factory=True, host=host, port=port, app_dir=str(ROOT / "src"))


if __name__ == "__main__":
    main()
