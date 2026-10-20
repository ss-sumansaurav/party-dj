"""YouTube Music client built from local credentials. Never logs secrets."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from dotenv import load_dotenv
from ytmusicapi import YTMusic


class AuthError(RuntimeError):
    pass


def auth_file() -> Path:
    load_dotenv()
    return Path(os.environ.get("YTMUSIC_AUTH_FILE", "browser.json")).expanduser()


def client() -> YTMusic:
    path = auth_file()
    if not path.exists():
        raise AuthError(
            f"No YouTube Music auth file at {path}. "
            "Run: ytmusicapi browser --file browser.json  (see README, 'Sign in')."
        )
    # The file holds session cookies, so keep it readable by you only.
    if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        path.chmod(0o600)
    return YTMusic(str(path))


def check_auth() -> str:
    """Make one signed-in call and return the account name. Raises AuthError on failure."""
    yt = client()
    try:
        info = yt.get_account_info()
    except Exception as e:  # ytmusicapi raises several types; don't echo request details
        raise AuthError(
            f"Signed-in request failed ({type(e).__name__}). "
            "Your headers may have expired: copy them again and rerun the sign-in step."
        ) from None
    return info.get("accountName") or "(unknown account)"
