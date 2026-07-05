"""Run YouTube OAuth setup and save the refresh token."""
from __future__ import annotations

from .youtube_uploader import get_authenticated_service


def main() -> int:
    get_authenticated_service()
    print("YouTube OAuth token saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
