from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.invite import invite_url, permission_summary


if __name__ == "__main__":
    url = invite_url()
    if not url:
        raise SystemExit("Set APPLICATION_ID in .env first.")
    print("Invite URL:")
    print(url)
    print()
    print("Recommended permissions:")
    print(permission_summary())
