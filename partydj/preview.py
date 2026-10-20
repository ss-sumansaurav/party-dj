"""30-second song previews in YouTube's own player, served from a local page.

Opening a youtube.com/embed link directly gives "Error 153" because the browser sends no
referrer. Serving the player from http://localhost fixes that. Nothing is downloaded.
"""
from __future__ import annotations

import html
import http.server
import json
import threading
import urllib.parse
import webbrowser

PREVIEW_SECONDS = 30

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="referrer" content="strict-origin-when-cross-origin">
<title>Party DJ previews</title>
<style>
 body{{font-family:-apple-system,sans-serif;background:#111;color:#eee;text-align:center;padding:24px}}
 button{{font-size:24px;padding:14px 30px;border-radius:12px;border:0;background:#e91e63;color:#fff;cursor:pointer;margin:6px}}
 button.alt{{background:#444}}
 #now{{font-size:22px;margin:16px}} #count{{color:#aaa}} a{{color:#8cf}}
</style></head><body>
<h1>Party DJ: every song, {secs} seconds each</h1>
<button id="go">▶ Play previews</button>
<div id="controls" hidden><button class="alt" id="skip">Skip ⏭</button></div>
<div id="count"></div><div id="now"></div><div id="player"></div>
<script>
const SONGS = {songs};
const SECS = {secs};
let i = 0, player, timer;
function show(t){{ document.getElementById('now').innerHTML = t; }}
function next(){{
  clearTimeout(timer);
  if (i >= SONGS.length) {{
    show('All done. Go back to Terminal and press Enter.');
    document.getElementById('controls').hidden = true;
    player && player.stopVideo(); return;
  }}
  const s = SONGS[i++];
  document.getElementById('count').textContent = 'Song ' + i + ' of ' + SONGS.length;
  show(s.label);
  player.loadVideoById({{videoId: s.id, startSeconds: 45, endSeconds: 45 + SECS}});
  timer = setTimeout(next, (SECS + 8) * 1000);  // in case the player never reports "ended"
}}
function onYouTubeIframeAPIReady(){{
  player = new YT.Player('player', {{height: '270', width: '480',
    playerVars: {{origin: location.origin, playsinline: 1}},
    events: {{
      onStateChange: e => {{ if (e.data === YT.PlayerState.ENDED) next(); }},
      onError: () => {{
        const s = SONGS[i-1];
        fetch('/blocked?id=' + encodeURIComponent(s.id));
        show(s.label + " can't play on this page. <a target=_blank href='https://music.youtube.com/watch?v=" + s.id + "'>Listen in YouTube Music</a>");
        clearTimeout(timer); timer = setTimeout(next, 5000);
      }}
    }}}});
}}
document.getElementById('go').onclick = () => {{
  document.getElementById('go').remove();
  document.getElementById('controls').hidden = false;
  next();
}};
document.getElementById('skip').onclick = next;
</script>
<script src="https://www.youtube.com/iframe_api"></script>
</body></html>"""


def serve_previews(songs) -> list:
    """Open a local page that plays 30 seconds of each song, wait for Enter,
    and return the songs YouTube wouldn't play on the page."""
    songs = [s for s in songs if s.video_id]
    data = json.dumps([{"id": s.video_id, "label": html.escape(s.label())} for s in songs])
    body = PAGE.format(songs=data, secs=PREVIEW_SECONDS).encode()
    blocked: set[str] = set()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path == "/blocked":
                blocked.update(urllib.parse.parse_qs(url.query).get("id", []))
                self.send_response(204)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://localhost:{server.server_address[1]}/"
    minutes = len(songs) * (PREVIEW_SECONDS + 3) // 60
    print(f"  Opening {url} in your browser. Click 'Play previews' there.")
    print(f"  {len(songs)} songs, about {minutes} minutes. Use 'Skip' on the page to move on early.")
    webbrowser.open(url)
    try:
        input("  Press Enter here when the previews are done... ")
    except EOFError:
        pass
    server.shutdown()
    return [s for s in songs if s.video_id in blocked]
