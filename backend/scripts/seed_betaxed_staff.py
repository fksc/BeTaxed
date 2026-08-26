"""Create or promote the local BeTaxed ops user (DEV + Auth emulator only).

  cd backend
  PYTHONPATH=. python scripts/seed_betaxed_staff.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.services.dev_seed import (  # noqa: E402
    DEFAULT_STAFF_EMAIL,
    DEFAULT_STAFF_PASSWORD,
    seed_betaxed_staff,
)


def main() -> int:
    email = os.environ.get("SEED_STAFF_EMAIL", DEFAULT_STAFF_EMAIL).strip()
    password = os.environ.get("SEED_STAFF_PASSWORD", DEFAULT_STAFF_PASSWORD)
    try:
        user = asyncio.run(seed_betaxed_staff(email, password))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Seeded BETAXED_STAFF")
    print(f"  email:    {user.email}")
    print(f"  user_id:  {user.id}")
    print("  password: SEED_STAFF_PASSWORD (default betaxed-dev)")
    print("  sign-in:  /en/login  then /en/admins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
