"""YouTube Music client built from local credentials. Never logs secrets."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from dotenv import load_dotenv
from ytmusicapi import YTMusic


class AuthError(RuntimeError):
    pass


# Set from the party's config (youtube_auth_file): that party's own account, never the default one.
PARTY_AUTH_FILE: str | None = None


def auth_file() -> Path:
    if PARTY_AUTH_FILE:
        return Path(PARTY_AUTH_FILE).expanduser()
    load_dotenv()
    return Path(os.environ.get("YTMUSIC_AUTH_FILE", "browser.json")).expanduser()


def client() -> YTMusic:
    path = auth_file()
    if not path.exists():
        raise AuthError(
            f"No YouTube Music auth file at {path}. "
            "Copy the request headers and run: python dj.py --sign-in  (see README, 'Sign in')."
        )
    # The file holds session cookies, so keep it readable by you only.
    if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        path.chmod(0o600)
    try:
        return YTMusic(str(path))
    except Exception as e:  # malformed or incomplete headers; don't echo the file
        raise AuthError(
            f"Couldn't use the saved sign-in ({type(e).__name__}). "
            "Copy the request headers again and rerun: python dj.py --sign-in"
        ) from None


def check_auth() -> str:
    """Make one signed-in call and return the account name. Raises AuthError on failure."""
    yt = client()
    try:
        info = yt.get_account_info()
    except Exception as e:  # ytmusicapi raises several types; don't echo request details
        raise AuthError(
            f"Signed-in request failed ({type(e).__name__}). "
            "Your headers may have expired: copy them again and run: python dj.py --sign-in"
        ) from None
    return info.get("accountName") or "(unknown account)"
