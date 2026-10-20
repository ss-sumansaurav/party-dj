"""Pause, resume and pick songs in YouTube Music running in Google Chrome on this Mac.

Uses AppleScript to run a line of JavaScript in the YouTube Music tab. Chrome needs one
setting turned on: View > Developer > Allow JavaScript from Apple Events.
"""
from __future__ import annotations

import json
import subprocess
import time

SCRIPT = """
on run argv
  if application "Google Chrome" is not running then return "ERR:NOCHROME"
  tell application "Google Chrome"
    repeat with w in windows
      repeat with t in tabs of w
        if URL of t contains "music.youtube.com" then
          set r to execute t javascript (item 1 of argv)
          if r is missing value then return ""
          return r as text
        end if
      end repeat
    end repeat
  end tell
  return "ERR:NOTAB"
end run
"""

STATUS_JS = """(function(){var v=document.querySelector('video');
return JSON.stringify({vid:new URLSearchParams(location.search).get('v'),
t:v?v.currentTime:0,d:v?v.duration:0,paused:v?v.paused:true});})()"""


class PlayerError(RuntimeError):
    pass


FIXES = {
    "ERR:NOCHROME": "Open Google Chrome with YouTube Music in a tab.",
    "ERR:NOTAB": "Open music.youtube.com in a Chrome tab.",
    "JS": "In Chrome's menu bar choose View > Developer > Allow JavaScript from Apple Events.",
    "PERM": "Allow Terminal to control Google Chrome: System Settings > Privacy & Security > "
            "Automation > Terminal > Google Chrome.",
}


class ChromePlayer:
    def __init__(self, playlist_id: str | None):
        self.playlist_id = playlist_id

    def _js(self, code: str) -> str:
        try:
            r = subprocess.run(["osascript", "-e", SCRIPT, code], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise PlayerError(f"Couldn't reach Chrome ({type(e).__name__}); this needs the Mac's osascript.") from None
        out, err = r.stdout.strip(), r.stderr
        if "JavaScript through AppleScript is turned off" in err or "Allow JavaScript" in err:
            raise PlayerError(FIXES["JS"])
        if "-1743" in err or "Not authorized" in err:
            raise PlayerError(FIXES["PERM"])
        if r.returncode != 0:
            raise PlayerError(f"Couldn't talk to Chrome: {err.strip()[:200]}")
        if out in FIXES:
            raise PlayerError(FIXES[out])
        return out

    def status(self) -> dict | None:
        out = self._js(STATUS_JS)
        try:
            return json.loads(out)
        except ValueError:
            return None  # page still loading

    def pause(self):
        self._js("(function(){var v=document.querySelector('video');if(v)v.pause();return 'ok'})()")

    def resume(self):
        self._js("(function(){var v=document.querySelector('video');if(v)v.play();return 'ok'})()")

    def open(self, video_id: str):
        """Play this song inside the party playlist, so the playlist carries on after it."""
        url = f"https://music.youtube.com/watch?v={video_id}"
        if self.playlist_id:
            url += f"&list={self.playlist_id}"
        self._js(f"(function(){{location.href={json.dumps(url)};return 'ok'}})()")
        # Wait for the new page to start playing; nudge it if autoplay was held back.
        for attempt in range(12):
            time.sleep(1)
            st = self.status()
            if st and st.get("vid") == video_id and st.get("d"):
                if st.get("paused") and attempt >= 3:
                    self.resume()
                elif not st.get("paused"):
                    return True
        return False

    def check(self) -> None:
        """Raise PlayerError with a fix if Chrome can't be controlled."""
        self._js("'ok'")
