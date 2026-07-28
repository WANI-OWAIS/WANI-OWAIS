#!/usr/bin/env python3
"""
Generate the animated projects panel (projects.svg + projects-light.svg).

Reads merged.json — projects.json enriched with live GitHub data by the
workflow — and lays the entries out as a two-column grid of mini terminal
cards. Add, remove or reorder projects by editing projects.json; the README
never changes because it just points at the generated SVG.

Each card shows a logo or monogram, name, wrapped description, tag pills, an
animated language donut, and either star count + last-push age (GitHub repos)
or a live deployment badge (externally hosted work).

Palette matches the hero banner: #0D1117 base, #3B82F6 / #06B6D4 / #8B5CF6.

Usage:  python3 .github/scripts/generate_projects.py [merged.json] [outdir]
"""
import base64
import html
import json
import math
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------- themes ----
THEMES = {
    "dark": {
        "BG": "#0D1117", "PANEL": "#0F1523", "PANEL_BAR": "#131C2E",
        "PRIMARY": "#3B82F6", "SECONDARY": "#06B6D4", "ACCENT": "#8B5CF6",
        "ACCENT_DEEP": "#6D28D9", "SUCCESS": "#10B981",
        "TEXT": "#F8FAFC", "MUTED": "#94A3B8", "DIM": "#475569",
        "STROKE": "rgba(59,130,246,0.30)",
        "STROKE_HI": "rgba(6,182,212,0.55)",
        "STROKE_LO": "rgba(59,130,246,0.22)",
        "BARLINE": "rgba(255,255,255,0.08)",
        "RING_BG": "rgba(148,163,184,0.16)",
        "PILL_BG": "rgba(139,92,246,0.22)",
        "PILL_STROKE": "rgba(139,92,246,0.50)",
        "MONOGRAM_TX": "#F5F3FF",
    },
    "light": {
        "BG": "#F8FAFC", "PANEL": "#FFFFFF", "PANEL_BAR": "#F1F5F9",
        "PRIMARY": "#2563EB", "SECONDARY": "#0891B2", "ACCENT": "#7C3AED",
        "ACCENT_DEEP": "#6D28D9", "SUCCESS": "#059669",
        "TEXT": "#0F172A", "MUTED": "#475569", "DIM": "#94A3B8",
        "STROKE": "rgba(37,99,235,0.28)",
        "STROKE_HI": "rgba(8,145,178,0.50)",
        "STROKE_LO": "rgba(37,99,235,0.18)",
        "BARLINE": "rgba(15,23,42,0.08)",
        "RING_BG": "rgba(71,85,105,0.18)",
        "PILL_BG": "rgba(124,58,237,0.12)",
        "PILL_STROKE": "rgba(124,58,237,0.40)",
        "MONOGRAM_TX": "#FFFFFF",
    },
}

C = {}
DONUT_COLORS = []
SUFFIX = ""


def set_theme(name):
    global C, DONUT_COLORS, SUFFIX
    C = THEMES[name]
    SUFFIX = name
    DONUT_COLORS = [
        C["PRIMARY"], C["SECONDARY"], C["ACCENT"],
        C["SUCCESS"], "#6366F1", "#94A3B8",
    ]


# ---------------------------------------------------------------- layout ----
W = 1180
CARD_W = 578
CARD_H = 168
GAP = 14
MARGIN = 5
COL_STEP = CARD_W + GAP + 4
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"


def esc(s):
    return html.escape(str(s), quote=True)


def rel_time(iso):
    if not iso:
        return "n/a"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        d = datetime.now(timezone.utc) - dt
        if d.days > 365:
            return f"{d.days // 365}y ago"
        if d.days > 30:
            return f"{d.days // 30}mo ago"
        if d.days > 0:
            return f"{d.days}d ago"
        h = d.seconds // 3600
        return f"{h}h ago" if h else "just now"
    except (ValueError, AttributeError):
        return "n/a"


def load_logo_b64(path):
    """Inline a logo as a data URI. Optional — cards fall back to a monogram."""
    if not path:
        return None
    for base in ("logos", "."):
        p = os.path.join(base, path)
        if os.path.exists(p):
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            mime = {
                "png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg",
                "jpeg": "image/jpeg", "webp": "image/webp",
            }.get(ext, "image/png")
            with open(p, "rb") as f:
                return f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    return None


def wrap_text(s, max_chars, max_lines=2):
    words = s.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words and " ".join(lines).count(" ") + 1 < len(words):
        lines[-1] = lines[-1][:max_chars - 1].rstrip() + "…"
    return lines


def donut_segments(languages, cx, cy, r, begin):
    """Language ring where each segment sweeps itself in, one after another."""
    total = sum(languages.values()) or 1
    entries = sorted(languages.items(), key=lambda kv: -kv[1])[:4]
    other = total - sum(v for _, v in entries)
    if other > 0:
        entries.append(("Other", other))

    circ = 2 * math.pi * r
    out, legend = [], []
    offset = 0.0
    t = begin
    for i, (lang, v) in enumerate(entries):
        frac = v / total
        seg = frac * circ
        col = DONUT_COLORS[i % len(DONUT_COLORS)]
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" '
            f'stroke-width="9" stroke-dasharray="{seg:.2f} {circ - seg:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.01s" '
            f'begin="{t:.2f}s" fill="freeze"/>'
            f'<animate attributeName="stroke-dasharray" from="0 {circ:.2f}" '
            f'to="{seg:.2f} {circ - seg:.2f}" dur="0.6s" begin="{t:.2f}s" fill="freeze" '
            f'calcMode="spline" keyTimes="0;1" keySplines="0.3 0 0.2 1"/></circle>'
        )
        legend.append((lang, frac, col))
        offset += seg
        t += 0.18
    return "".join(out), legend


# ------------------------------------------------------------------ card ----
def card(p, x, y, idx):
    b = 0.25 + idx * 0.15  # staggered entrance
    e = []
    a = e.append

    repo = (p.get("repo") or "").strip()
    external = not repo
    href = p.get("url") if external else f"https://github.com/{repo}"
    crumb = p.get("label") or (repo if repo else (href or "").split("//")[-1].rstrip("/"))

    if href:
        a(f'<a href="{esc(href)}" target="_blank" rel="noopener">')
    a(f'<g opacity="0" transform="translate({x},{y})">')
    a(f'<animate attributeName="opacity" from="0" to="1" dur="0.5s" '
      f'begin="{b:.2f}s" fill="freeze"/>')

    # shell — a mini terminal window with a breathing border
    a(f'<rect width="{CARD_W}" height="{CARD_H}" rx="12" fill="{C["PANEL"]}" '
      f'stroke="{C["STROKE"]}">'
      f'<animate attributeName="stroke" values="{C["STROKE_LO"]};{C["STROKE_HI"]};'
      f'{C["STROKE_LO"]}" dur="4.5s" begin="{b + idx * 0.7:.2f}s" '
      f'repeatCount="indefinite"/></rect>')
    a(f'<rect width="{CARD_W}" height="30" rx="12" fill="{C["PANEL_BAR"]}"/>')
    a(f'<rect y="18" width="{CARD_W}" height="12" fill="{C["PANEL_BAR"]}"/>')
    a(f'<line x1="0" y1="30" x2="{CARD_W}" y2="30" stroke="{C["BARLINE"]}"/>')
    a(f'<text x="16" y="19" font-size="10" fill="{C["MUTED"]}">'
      f'<tspan fill="{C["SECONDARY"]}">&#8226;</tspan> {esc(crumb)}</text>')

    # status dot: pulses for live deployments and repos pushed within 14 days
    days = 999
    try:
        dt = datetime.fromisoformat((p.get("pushed_at") or "").replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - dt).days
    except (ValueError, AttributeError):
        pass
    if p.get("live") or days <= 14:
        a(f'<circle cx="{CARD_W - 16}" cy="15" r="3.5" fill="{C["SUCCESS"]}">'
          f'<animate attributeName="opacity" values="1;0.25;1" dur="1.8s" '
          f'repeatCount="indefinite"/></circle>')
    else:
        a(f'<circle cx="{CARD_W - 16}" cy="15" r="3.5" fill="{C["DIM"]}"/>')

    # logo or monogram, gently floating
    float_anim = (
        f'<animateTransform attributeName="transform" type="translate" '
        f'values="0 0; 0 -2.5; 0 0" dur="5s" begin="{b + idx * 0.5:.2f}s" '
        f'repeatCount="indefinite" calcMode="spline" keyTimes="0;0.5;1" '
        f'keySplines="0.4 0 0.6 1;0.4 0 0.6 1"/>'
    )
    logo = p.get("_logo_b64")
    if logo:
        a(f'<g>{float_anim}<image x="16" y="44" width="40" height="40" href="{logo}" '
          f'preserveAspectRatio="xMidYMid meet"/></g>')
    else:
        initial = esc((p.get("name") or "?")[0].upper())
        a(f'<g>{float_anim}'
          f'<rect x="16" y="44" width="40" height="40" rx="10" '
          f'fill="url(#mono_{SUFFIX})"/>'
          f'<text x="36" y="71" text-anchor="middle" font-size="20" font-weight="700" '
          f'fill="{C["MONOGRAM_TX"]}">{initial}</text></g>')

    # name + blinking cursor
    a(f'<text x="68" y="61" font-size="17" font-weight="700" fill="{C["TEXT"]}">'
      f'{esc(p.get("name", "unnamed"))}'
      f'<tspan fill="{C["SECONDARY"]}">_<animate attributeName="opacity" '
      f'values="1;0;1" dur="1.2s" begin="{b + 0.4:.2f}s" repeatCount="indefinite"/>'
      f'</tspan></text>')

    for i, line in enumerate(wrap_text(p.get("description", ""), 52)):
        a(f'<text x="68" y="{80 + i * 16}" font-size="11" fill="{C["MUTED"]}">'
          f'{esc(line)}</text>')

    # tag pills
    tx = 68
    for tag in (p.get("tags") or [])[:3]:
        tw = len(tag) * 6.6 + 14
        a(f'<rect x="{tx}" y="118" width="{tw:.0f}" height="17" rx="8.5" '
          f'fill="{C["PILL_BG"]}" stroke="{C["PILL_STROKE"]}"/>')
        a(f'<text x="{tx + tw / 2:.0f}" y="130" text-anchor="middle" font-size="9.5" '
          f'fill="{C["ACCENT"]}">{esc(tag)}</text>')
        tx += tw + 7

    # footer: stars + freshness for repos, a deployment badge for external work
    if external:
        a(f'<text x="68" y="155" font-size="11" fill="{C["MUTED"]}">'
          f'<tspan fill="{C["SUCCESS"]}">&#9679;</tspan> live'
          f'<tspan fill="{C["DIM"]}" dx="14">shipped to production</tspan></text>')
    else:
        a(f'<text x="68" y="155" font-size="11" fill="{C["MUTED"]}">'
          f'<tspan fill="{C["SECONDARY"]}">&#9733;</tspan> {p.get("stars", 0)}'
          f'<tspan fill="{C["DIM"]}" dx="14">updated {rel_time(p.get("pushed_at"))}'
          f'</tspan></text>')

    # language donut + legend
    langs = p.get("languages") or {}
    if langs:
        cx, cy, r = CARD_W - 58, CARD_H // 2 + 6, 27
        segs, legend = donut_segments(langs, cx, cy, r, b + 0.3)
        a(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{C["RING_BG"]}" '
          f'stroke-width="9"/>')
        a(segs)
        a(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="11" '
          f'font-weight="700" fill="{C["TEXT"]}">{legend[0][1] * 100:.0f}%</text>')
        dot_x = cx - r - 92
        ly = cy - 22
        for lang, frac, col in legend[:3]:
            a(f'<circle cx="{dot_x}" cy="{ly}" r="3.5" fill="{col}"/>')
            a(f'<text x="{dot_x + 9}" y="{ly + 4}" font-size="10" fill="{C["MUTED"]}">'
              f'{esc(lang)} {frac * 100:.0f}%</text>')
            ly += 18

    a('</g>')
    if href:
        a('</a>')
    return "".join(e)


# ----------------------------------------------------------------- build ----
def build(projects):
    rows = math.ceil(len(projects) / 2)
    H = 56 + rows * (CARD_H + GAP) + MARGIN
    gid = f"acc_{SUFFIX}"
    odd_tail = len(projects) % 2 == 1  # lone final card gets centred

    s = []
    a = s.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
      f'aria-label="Featured projects">')
    a(f'<rect width="{W}" height="{H}" fill="{C["BG"]}"/>')

    a('<defs>'
      f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
      f'<stop offset="0" stop-color="{C["PRIMARY"]}"><animate attributeName="stop-color" '
      f'values="{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]};{C["PRIMARY"]}" '
      f'dur="10s" repeatCount="indefinite"/></stop>'
      f'<stop offset="1" stop-color="{C["ACCENT"]}"><animate attributeName="stop-color" '
      f'values="{C["ACCENT"]};{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]}" '
      f'dur="10s" repeatCount="indefinite"/></stop></linearGradient>'
      f'<linearGradient id="mono_{SUFFIX}" x1="0" y1="0" x2="1" y2="1">'
      f'<stop offset="0" stop-color="{C["PRIMARY"]}"/>'
      f'<stop offset="1" stop-color="{C["ACCENT_DEEP"]}"/></linearGradient>'
      '</defs>')

    a(f'<text x="{MARGIN + 2}" y="18" font-size="11" letter-spacing="2" '
      f'fill="{C["SECONDARY"]}">PROJECTS.LIST</text>')
    a(f'<text x="{MARGIN + 130}" y="18" font-size="10" fill="{C["DIM"]}">'
      f'./projects.sh --featured</text>')
    a(f'<line x1="{MARGIN}" y1="28" x2="{W - MARGIN}" y2="28" stroke="url(#{gid})" '
      f'stroke-width="1.5" opacity="0.75"/>')

    for i, p in enumerate(projects):
        lone = odd_tail and i == len(projects) - 1
        x = (W - CARD_W) // 2 if lone else MARGIN + (i % 2) * COL_STEP
        y = 42 + (i // 2) * (CARD_H + GAP)
        a(card(p, x, y, i))

    a('</svg>')
    return "".join(s)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "merged.json"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    with open(src, encoding="utf-8") as f:
        projects = json.load(f)
    for p in projects:
        p["_logo_b64"] = load_logo_b64(p.get("logo"))

    os.makedirs(outdir, exist_ok=True)
    for theme, fname in (("dark", "projects.svg"), ("light", "projects-light.svg")):
        set_theme(theme)
        svg = build(projects)
        path = os.path.join(outdir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}: {theme}, {len(projects)} projects, {len(svg) / 1024:.1f}KB")


if __name__ == "__main__":
    main()
