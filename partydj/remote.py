"""TV remote support: every page the app shows gets this script, so the remote's arrow keys
move between buttons (nearest one in that direction), OK presses the one in focus, and the
button in focus has a bright yellow ring. On a phone or a Mac it changes nothing until an
arrow key is pressed."""
from __future__ import annotations

SCRIPT = r"""
<style>
.dpad :focus { outline: 4px solid #FFC93C !important; outline-offset: 3px;
  box-shadow: 0 0 0 8px rgba(255,201,60,.35) !important; }
</style>
<script>
(function(){
  if (window.__dpad) return; window.__dpad = 1;
  const SEL = 'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"]), iframe.dpadframe';
  const DIRS = {ArrowUp:[0,-1], ArrowDown:[0,1], ArrowLeft:[-1,0], ArrowRight:[1,0]};
  const log = m => { try { fetch('/clientlog?m=' + encodeURIComponent(m)); } catch(e){} };
  function shown(el){
    if (el.disabled || el.closest('[hidden]')) return false;
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  }
  function label(el){ return (el.innerText || el.value || el.placeholder || el.id || el.tagName).trim().slice(0, 40); }
  function typing(el, dx){   // inside a text box, left/right move the cursor
    if (!el || (el.readOnly && el.type !== 'range')) return false;   // not typing yet: arrows move on
    if (el.tagName === 'TEXTAREA') return true;
    if (el.tagName === 'INPUT' && !/^(button|submit|checkbox|radio|range|color|file)$/.test(el.type)) return dx !== 0;
    if (el.tagName === 'INPUT' && el.type === 'range') return dx !== 0;
    return false;
  }
  function first(){
    const els = [...document.querySelectorAll(SEL)].filter(shown);
    return document.getElementById('start') && shown(document.getElementById('start')) ? document.getElementById('start') : els[0];
  }
  // A TV pops its keyboard up as soon as a text box gets focus, and the keyboard then takes the
  // arrow keys. So a box reached with the arrows is read-only until OK is pressed on it.
  function textBox(el){
    return el && (el.tagName === 'TEXTAREA' ||
      (el.tagName === 'INPUT' && !/^(button|submit|checkbox|radio|range|color|file|date|time)$/.test(el.type)));
  }
  function go(el){
    if (!el) return;
    if (textBox(el) && !el.readOnly) {
      el.readOnly = true; el.dataset.dpadRo = '1';
      el.addEventListener('blur', () => { if (el.dataset.dpadRo) { el.readOnly = false; delete el.dataset.dpadRo; } }, {once: true});
    }
    el.focus({preventScroll: true});
    el.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'smooth'});
    log('focus: ' + label(el));
  }
  document.addEventListener('keydown', e => {
    const d = DIRS[e.key];
    const a = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
    if (e.key === 'Enter' && a && a.dataset && a.dataset.dpadRo) {   // OK on a text box: now type
      e.preventDefault(); delete a.dataset.dpadRo; a.readOnly = false; a.blur(); a.focus();
      const n = (a.value || '').length; try { a.setSelectionRange(n, n); } catch(err){}
      return;
    }
    if (e.key === 'Enter' && a && (a.matches('input[type=radio], input[type=checkbox]') ||
        (a.matches('[tabindex]') && !a.matches('button, a, input, select, textarea')))) {
      e.preventDefault(); a.click(); return;
    }
    if (!d) return;
    document.documentElement.classList.add('dpad');
    if (typing(a, d[0])) return;
    if (!a) { e.preventDefault(); go(first()); return; }
    const from = a.getBoundingClientRect();
    const fx = from.left + from.width/2, fy = from.top + from.height/2;
    let best = null, bestScore = Infinity;
    for (const el of document.querySelectorAll(SEL)) {
      if (el === a || !shown(el) || a.contains(el)) continue;
      const r = el.getBoundingClientRect();
      // how far it is in the pressed direction (edge to edge), and how far off to the side
      const along = d[0] ? (d[0] > 0 ? r.left - from.right : from.left - r.right)
                         : (d[1] > 0 ? r.top - from.bottom : from.top - r.bottom);
      const cx = r.left + r.width/2, cy = r.top + r.height/2;
      const ahead = d[0] ? (cx - fx) * d[0] : (cy - fy) * d[1];
      if (ahead <= 2 || along < -Math.min(r.width, r.height) / 2) continue;
      const side = d[0] ? Math.max(0, Math.max(r.top - from.bottom, from.top - r.bottom))
                        : Math.max(0, Math.max(r.left - from.right, from.left - r.right));
      const score = Math.max(0, along) + side * 3 + (d[0] ? Math.abs(cy - fy) : Math.abs(cx - fx)) * 0.3;
      if (score < bestScore) { bestScore = score; best = el; }
    }
    e.preventDefault();
    if (best) go(best);
    else if (d[1]) window.scrollBy({top: d[1] * innerHeight * 0.6, behavior: 'smooth'});
  }, true);
  // A TV has no touch screen or mouse: start with the main button in focus.
  const start = () => setTimeout(() => {
    if (document.activeElement === document.body && (matchMedia('(any-pointer: none)').matches || window.__tv)) {
      document.documentElement.classList.add('dpad'); go(first());
    }
  }, 400);
  addEventListener('load', start);
  addEventListener('focus', start);   // the songs list or big screen opened over the DJ page
})();
</script>
"""


def add(body: bytes) -> bytes:
    """Put the remote-control script into an HTML page (once)."""
    if b"window.__dpad" in body or b"</body>" not in body:
        return body
    i = body.rfind(b"</body>")
    return body[:i] + SCRIPT.encode() + body[i:]
