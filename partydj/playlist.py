"""Private YouTube Music playlist for the night. Callers must ask the host first."""
from __future__ import annotations


def url(playlist_id: str) -> str:
    return f"https://music.youtube.com/playlist?list={playlist_id}"


def find_existing(yt, title: str) -> str | None:
    for pl in yt.get_library_playlists(limit=None) or []:
        if pl.get("title") == title:
            return pl.get("playlistId")
    return None


def fill_playlist(yt, title: str, video_ids: list[str], existing_id: str | None = None) -> str:
    """Create the playlist (PRIVATE) or replace an existing one's tracks. Returns its link."""
    description = "Made by Party DJ. Play in order; announcements come from the laptop."
    if existing_id is None:
        playlist_id = yt.create_playlist(title, description, privacy_status="PRIVATE", video_ids=video_ids)
        if not isinstance(playlist_id, str):
            raise RuntimeError("YouTube Music didn't create the playlist; try again in a minute.")
        return url(playlist_id)

    current = yt.get_playlist(existing_id, limit=None).get("tracks") or []
    if current:
        yt.remove_playlist_items(existing_id, current)
    yt.edit_playlist(existing_id, privacyStatus="PRIVATE")
    yt.add_playlist_items(existing_id, video_ids, duplicates=False)
    return url(existing_id)
