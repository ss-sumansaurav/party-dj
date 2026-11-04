"""The songs page: see every song picked for the party, add new ones and remove others.

songs.yaml stays the one list of songs. Adding appends a line to it; removing deletes the
song's line. During the party the change also reaches the DJ straight away.
"""
from __future__ import annotations

import html
import json
import threading
from pathlib import Path

import yaml

from . import resolver
from .songs import MIN_ENERGY, Song, _song, norm, title_looks_explicit

LANGS = {"hi": "Hindi", "pa": "Punjabi", "en": "English"}
EDITS = Path(".cache/song_edits.json")   # star ratings and languages the host changed, and songs removed
_lock = threading.Lock()


def _row_line(indent: str, row: list) -> str:
    title, artist, lang, era, energy, *tags = row
    dump = lambda v: json.dumps(str(v), ensure_ascii=False)
    return f"{indent}- [{dump(title)}, {dump(artist)}, {lang}, {era}, {energy}" + "".join(f", {t}" for t in tags) + "]\n"


def _edits() -> dict:
    try:
        return json.loads(EDITS.read_text())
    except (OSError, ValueError):
        return {}


def _save_edits(e: dict):
    EDITS.parent.mkdir(exist_ok=True)
    EDITS.write_text(json.dumps(e, ensure_ascii=False, indent=1))


def _parse(line: str) -> list | None:
    if not line.lstrip().startswith("- ["):
        return None
    try:
        row = yaml.safe_load(line.strip()[2:])
    except yaml.YAMLError:
        return None
    return row if isinstance(row, list) and len(row) >= 5 else None


class Songbook:
    def __init__(self, path: str | Path, yt=None, director=None):
        self.path, self.yt, self.director = Path(path), yt, director

    def rows(self) -> list[Song]:
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        return [_song(r) for r in raw.get("songs") or []]

    def listing(self) -> dict:
        d = self.director
        state = d.song_states() if d else {}
        out = []
        for i, s in enumerate(self.rows(), 1):
            out.append({"n": i, "title": s.title, "artist": s.artist, "lang": LANGS.get(s.lang, s.lang),
                        "code": s.lang, "energy": s.energy, "era": s.era, "old": s.old,
                        "state": "Not played: too slow (1 dot)" if s.energy < MIN_ENERGY else state.get(s.key, "")})
        return {"songs": out, "live": bool(d), "dislikes": [x.get("title", "") for x in self.dislikes()]}

    def add(self, title: str, artist: str, lang: str, energy: int) -> str:
        title, artist = title.strip(), artist.strip()
        if not title:
            return "Type the song name first."
        if lang not in LANGS or not 1 <= energy <= 5:
            return "Pick a language and an energy level."
        if title_looks_explicit(title):
            return "That title looks explicit, so it's not added."
        if any(s.key == norm(title) for s in self.rows()):
            return f"'{title}' is already on the list."
        song = Song(title, artist, lang, "new", energy)
        found = ""
        if self.yt is not None:
            try:
                resolver.resolve_all(self.yt, [song], progress=lambda *_: None)
            except Exception:
                pass
            if not song.video_id:
                return f"Couldn't find '{title}' on YouTube Music. Check the spelling or add the artist."
            if song.explicit:
                return f"'{title}' is marked explicit on YouTube Music, so it's not added."
            found = " Found on YouTube Music ✓"
        line = f"  - [{json.dumps(title, ensure_ascii=False)}, {json.dumps(artist, ensure_ascii=False)}, {lang}, new, {energy}]\n"
        with _lock:
            text = self.path.read_text(encoding="utf-8")
            if not text.endswith("\n"):
                text += "\n"
            self.path.write_text(text + line, encoding="utf-8")
        if self.director:
            self.director.add_song(song)
        return f"Added '{title}'.{found}"

    def dislikes(self) -> list[dict]:
        return list(_edits().get("dislikes", []))

    def save_dislike(self, d: dict | None):
        """Remember a 👎 for next time (None forgets them all)."""
        with _lock:
            e = _edits()
            e["dislikes"] = e.get("dislikes", []) + [d] if d else []
            _save_edits(e)

    def remove(self, title: str, quiet: bool = False) -> str:
        key = norm(title)
        with _lock:
            lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
            keep, gone = [], None
            for line in lines:
                if gone is None:
                    row = _parse(line)
                    if row and norm(str(row[0])) == key:
                        gone = str(row[0])
                        continue
                keep.append(line)
            if gone is None:
                return f"'{title}' isn't on the list."
            self.path.write_text("".join(keep), encoding="utf-8")
            e = _edits()
            e.setdefault("removed", []).append(key)
            _save_edits(e)
        if self.director and not quiet:
            self.director.remove_song(gone)
        return f"Removed '{gone}'."

    def set_song(self, title: str, energy: int | None = None, lang: str | None = None) -> str:
        """The host's own star rating (1-5) or language for a song, saved in songs.yaml and used
        by the DJ straight away."""
        if energy is not None and not 1 <= energy <= 5:
            return "Pick 1 to 5 stars."
        if lang is not None and lang not in LANGS:
            return "Pick Hindi, English or Punjabi."
        key = norm(title)
        with _lock:
            lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
            for i, line in enumerate(lines):
                row = _parse(line)
                if row and norm(str(row[0])) == key:
                    if energy is not None:
                        row[4] = energy
                    if lang is not None:
                        row[2] = lang
                    lines[i] = _row_line(line[:len(line) - len(line.lstrip())], row)
                    break
            else:
                # A song from a YouTube Music playlist (Play songs like…): rated for tonight only.
                if self.director and self.director.set_song(key, energy, lang):
                    return f"'{title}' is now {energy} ★ for tonight." if energy else f"'{title}' changed for tonight."
                return f"'{title}' isn't on the list."
            self.path.write_text("".join(lines), encoding="utf-8")
            e = _edits()
            mine = e.setdefault("songs", {}).setdefault(key, {})
            if energy is not None:
                mine["energy"] = energy
            if lang is not None:
                mine["lang"] = lang
            _save_edits(e)
        if self.director:
            self.director.set_song(key, energy, lang)
        what = f"{energy} ★" if energy is not None else LANGS[lang]
        return f"'{row[0]}' is now {what}."

    def merge_from(self, bundled: str | Path) -> int:
        """A new version of the app brings new songs and fixes: add the songs this copy doesn't
        have yet (unless the host removed them) and take the new languages and star ratings,
        except where the host set their own. Returns how many songs were added."""
        e = _edits()
        removed, mine = set(e.get("removed", [])), e.get("songs", {})
        fresh = {}
        for line in Path(bundled).read_text(encoding="utf-8").splitlines():
            row = _parse(line)
            if row:
                fresh.setdefault(norm(str(row[0])), row)
        with _lock:
            lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
            have, changed = set(), False
            for i, line in enumerate(lines):
                row = _parse(line)
                if not row:
                    continue
                key = norm(str(row[0]))
                have.add(key)
                new = fresh.get(key)
                own = mine.get(key, {})
                if new:
                    lang = own.get("lang", new[2])
                    energy = own.get("energy", new[4])
                    if (row[2], row[4], row[5:]) != (lang, energy, new[5:]):
                        row[2], row[4] = lang, energy
                        row[5:] = new[5:]
                        lines[i] = _row_line(line[:len(line) - len(line.lstrip())], row)
                        changed = True
            add = [r for k, r in fresh.items() if k not in have and k not in removed]
            if add:
                if lines and not lines[-1].endswith("\n"):
                    lines[-1] += "\n"
                lines += ["\n  # Added by an app update\n"] + [_row_line("  ", r) for r in add]
            if add or changed:
                self.path.write_text("".join(lines), encoding="utf-8")
        return len(add)

    def handle(self, handler, method: str, path: str, query: dict) -> bool:
        """Serve /songs and its API. Returns False for paths it doesn't own."""
        if method == "GET" and path == "/songs":
            title = html.escape(self.page_title)
            handler._send(200, SONGS_PAGE.replace("__TITLE__", title).encode())
        elif method == "GET" and path == "/api/songs":
            handler._json(self.listing())
        elif method == "POST" and path == "/api/songs/add":
            q = lambda k: query.get(k, [""])[0]
            energy = int(q("energy")) if q("energy").isdigit() else 0
            handler._json({"msg": self.add(q("title"), q("artist"), q("lang"), energy)})
        elif method == "POST" and path == "/api/songs/set":
            q = lambda k: query.get(k, [""])[0]
            energy = int(q("energy")) if q("energy").isdigit() else None
            handler._json({"msg": self.set_song(q("title"), energy, q("lang") or None)})
        elif method == "POST" and path == "/api/songs/remove":
            handler._json({"msg": self.remove(query.get("title", [""])[0])})
        else:
            return False
        return True

    page_title = "Party songs"


SONGS_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
 :root{--bg:#0d0d12;--card:#1b1b24;--pink:#ff2d7a;--txt:#f4f4f8;--dim:#a0a0b0}
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--txt)}
 main{max-width:1000px;margin:auto;padding:16px} h1{text-align:center;margin:8px 0}
 .card{background:var(--card);border-radius:16px;padding:16px;margin:12px 0}
 .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 input,select{font-size:16px;padding:10px;border-radius:10px;border:0}
 #title{flex:2;min-width:180px} #artist{flex:1.4;min-width:150px} #find{width:100%}
 button{font-size:16px;padding:10px 16px;border-radius:10px;border:0;background:var(--pink);color:#fff;cursor:pointer}
 button:active{transform:scale(.95)} .del{background:#333;padding:6px 10px;font-size:14px}
 table{width:100%;border-collapse:collapse} th,td{padding:8px 6px;border-bottom:1px solid #2a2a35;text-align:left}
 th{color:var(--dim);font-weight:600;font-size:14px} td.n{color:var(--dim);width:36px}
 select.en,select.lg{font-size:15px;padding:6px;background:#2a2a35;color:#ffd54f}
 select.lg{color:var(--txt)} .art{color:var(--dim)} .st{font-size:13px;color:var(--pink)} .done{opacity:.45}
 #toast{position:fixed;left:50%;top:14px;transform:translateX(-50%);background:#2e7d32;padding:12px 22px;border-radius:12px;display:none;font-size:17px;max-width:90%}
 #summary{color:var(--dim);text-align:center} a{color:var(--pink)}
 @media (max-width:640px){.hide-s{display:none}}
</style></head><body><main>
<div id="toast"></div>
<h1>🎵 __TITLE__</h1>
<div id="summary"></div>
<div id="dis" style="display:none;text-align:center;color:var(--dim);margin-top:6px"></div>
<div class="card"><b>Add a song</b><div class="row" style="margin-top:10px">
 <input id="title" placeholder="Song name"><input id="artist" placeholder="Singer or artist">
 <select id="lang"><option value="hi">Hindi</option><option value="pa">Punjabi</option><option value="en">English</option></select>
 <select id="energy"><option value="1">1 Chill</option><option value="2">2 Groove</option><option value="3" selected>3 Dance</option>
  <option value="4">4 Banger</option><option value="5">5 On fire</option></select>
 <button id="add">Add</button></div></div>
<div class="card"><input id="find" placeholder="🔍 Search the list">
<table><thead><tr><th>#</th><th>Song</th><th>Language</th><th>Stars</th><th></th></tr></thead><tbody id="list"></tbody></table></div>
</main><script>
const $ = id => document.getElementById(id);
let all = [];
function toast(t, bad){ const e=$('toast'); e.textContent=t; e.style.background=bad?'#b71c1c':'#2e7d32'; e.style.display='block'; clearTimeout(e.t); e.t=setTimeout(()=>e.style.display='none',3500); }
const esc = s => String(s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function draw(){
  const f = $('find').value.toLowerCase();
  const rows = all.filter(s => !f || (s.title+' '+s.artist).toLowerCase().includes(f));
  $('list').innerHTML = rows.map(s => `<tr class="${s.state==='played'?'done':''}"><td class="n">${s.n}</td>
    <td><b>${esc(s.title)}</b><div class="art">${esc(s.artist)}</div>${s.state?`<div class="st">${esc(s.state)}</div>`:''}</td>
    <td><select class="lg" data-t="${esc(s.title)}">${LG.map(([v,n])=>`<option value="${v}"${v===s.code?' selected':''}>${n}</option>`).join('')}</select></td>
    <td><select class="en" data-t="${esc(s.title)}">${[1,2,3,4,5].map(n=>`<option value="${n}"${n===s.energy?' selected':''}>${'★'.repeat(n)}</option>`).join('')}</select></td>
    <td><button class="del" data-t="${esc(s.title)}">Remove</button></td></tr>`).join('');
  document.querySelectorAll('.del').forEach(b => b.onclick = () => remove(b.dataset.t));
  document.querySelectorAll('select.en').forEach(b => b.onchange = () => change(b.dataset.t, {energy:b.value}));
  document.querySelectorAll('select.lg').forEach(b => b.onchange = () => change(b.dataset.t, {lang:b.value}));
}
const LG = [['hi','Hindi'],['en','English'],['pa','Punjabi']];
async function change(title, what){
  try { const msg = await post('/api/songs/set', {title, ...what}); toast(msg, !msg.includes(' is now '));
    const s = all.find(x=>x.title===title); if(s){ if(what.energy) s.energy=+what.energy; if(what.lang){ s.code=what.lang; } } }
  catch(e){ toast("The DJ program isn't running. In Terminal run: python dj.py", true); }
}
async function load(){
  const r = await (await fetch('/api/songs')).json(); all = r.songs;
  const n = c => all.filter(s=>s.code===c).length;
  $('summary').textContent = `${all.length} songs · ${n('hi')} Hindi, ${n('pa')} Punjabi, ${n('en')} English · tap the stars or language to change them`
    + (r.live ? ' · changes reach the DJ straight away' : ' · changes are used the next time you run python dj.py');
  const d = r.dislikes || [];
  $('dis').style.display = d.length ? 'block' : 'none';
  $('dis').innerHTML = d.length ? `👎 Removed from the main screen: ${d.map(esc).join(', ')}. The DJ skips those singers and plays fewer songs like them.`
    + (r.live ? ' <button class="del" id="forget">Forget these</button>' : '') : '';
  if($('forget')) $('forget').onclick = async () => { await fetch('/undislike', {method:'POST'}); toast('Forgotten: every singer can play again'); load(); };
  draw();
}
async function post(path, params){
  const r = await fetch(path+'?'+new URLSearchParams(params), {method:'POST'}); return (await r.json()).msg;
}
$('add').onclick = async () => {
  const title = $('title').value.trim(); if(!title){ toast('Type the song name first', true); return; }
  $('add').disabled = true; $('add').textContent = 'Looking it up…';
  try { const msg = await post('/api/songs/add', {title, artist:$('artist').value, lang:$('lang').value, energy:$('energy').value});
    const ok = msg.startsWith('Added'); toast(msg, !ok); if(ok){ $('title').value=''; $('artist').value=''; } await load(); }
  catch(e){ toast("The DJ program isn't running. In Terminal run: python dj.py", true); }
  finally { $('add').disabled = false; $('add').textContent = 'Add'; }
};
async function remove(title){
  if(!confirm(`Remove "${title}" from the party list?`)) return;
  try { toast(await post('/api/songs/remove', {title})); await load(); }
  catch(e){ toast("The DJ program isn't running. In Terminal run: python dj.py", true); }
}
$('find').oninput = draw;
$('title').onkeydown = $('artist').onkeydown = e => { if(e.key==='Enter') $('add').click(); };
load(); setInterval(() => { if(!(document.activeElement||{}).matches?.('select,input')) load(); }, 15000);
</script></body></html>"""


def serve_alone(book: Songbook, port: int) -> str:
    """Run just the songs page, for editing the list before the party."""
    import http.server
    import urllib.parse

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body=b"", kind="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj):
            self._send(200, json.dumps(obj).encode(), "application/json")

        def _go(self, method):
            u = urllib.parse.urlparse(self.path)
            path = "/songs" if u.path == "/" else u.path
            if not book.handle(self, method, path, urllib.parse.parse_qs(u.query)):
                self._send(404)

        def do_GET(self):
            self._go("GET")

        def do_POST(self):
            self._go("POST")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://localhost:{port}/songs"
