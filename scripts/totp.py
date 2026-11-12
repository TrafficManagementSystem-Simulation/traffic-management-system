"""Print the current one-time code for a demo user:  python scripts/totp.py operator"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tms.admin import mfa  # noqa: E402
from tms.common.seed import DEMO_MFA_SECRETS  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else "operator"
secret = DEMO_MFA_SECRETS.get(name) or (sys.argv[2] if len(sys.argv) > 2 else None)
if not secret:
    sys.exit(f"No demo secret for '{name}'. Pass a secret as the second argument.")
print(mfa.totp(secret, datetime.now(timezone.utc).replace(tzinfo=None)))
