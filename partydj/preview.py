"""30-second song previews in YouTube's own player, served from a local page.

Opening a youtube.com/embed link directly gives "Error 153" because the browser sends no
referrer. Serving the player from http://localhost fixes that. Nothing is downloaded.
"""
from __future__ import annotations

import html
import http.server
import json
import threading
import webbrowser

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="referrer" content="strict-origin-when-cross-origin">
<title>Party DJ previews</title>
<style>
 body{{font-family:-apple-system,sans-serif;background:#111;color:#eee;text-align:center;padding:24px}}
 button{{font-size:28px;padding:18px 36px;border-radius:14px;border:0;background:#e91e63;color:#fff;cursor:pointer}}
 #now{{font-size:22px;margin:18px}} a{{color:#8cf}}
</style></head><body>
<h1>Party DJ: 30-second previews</h1>
<button id="go">▶ Play previews</button>
<div id="now"></div><div id="player"></div>
<script>
const SONGS = {songs};
let i = 0, player;
function show(t){{ document.getElementById('now').innerHTML = t; }}
function next(){{
  if (i >= SONGS.length) {{ show('Done. You can close this tab.'); player && player.stopVideo(); return; }}
  const s = SONGS[i++];
  show('Now: ' + s.label + ' (30 s)');
  player.loadVideoById({{videoId: s.id, startSeconds: 45, endSeconds: 75}});
}}
function onYouTubeIframeAPIReady(){{
  player = new YT.Player('player', {{height: '270', width: '480',
    playerVars: {{origin: location.origin, playsinline: 1}},
    events: {{
      onStateChange: e => {{ if (e.data === YT.PlayerState.ENDED) next(); }},
      onError: () => {{
        const s = SONGS[i-1];
        show(s.label + " can't play here. <a target=_blank href='https://music.youtube.com/watch?v=" + s.id + "'>Open in YouTube Music</a>");
        setTimeout(next, 4000);
      }}
    }}}});
}}
document.getElementById('go').onclick = () => {{ document.getElementById('go').remove(); next(); }};
</script>
<script src="https://www.youtube.com/iframe_api"></script>
</body></html>"""


def serve_previews(songs) -> None:
    """Open a local page that plays 30 seconds of each song, then wait for Enter."""
    data = json.dumps([{"id": s.video_id, "label": html.escape(s.label())} for s in songs if s.video_id])
    body = PAGE.format(songs=data).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://localhost:{server.server_address[1]}/"
    print(f"  Opening {url} in your browser. Click 'Play previews' there.")
    webbrowser.open(url)
    try:
        input("  Press Enter here when the previews are done... ")
    except EOFError:
        pass
    server.shutdown()
