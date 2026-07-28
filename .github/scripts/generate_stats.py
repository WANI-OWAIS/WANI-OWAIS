#!/usr/bin/env python3
"""
Generate a self-hosted GitHub stats panel (stats.svg + stats-light.svg).

This exists because the popular third-party card services are unreliable — the
public github-readme-stats instance rate-limits to HTTP 503 and the trophy
service returns 402 once its Vercel quota is spent. Rendering the cards from
the API ourselves means the profile never shows a broken image.

Left panel  — headline metrics, counted up on load.
Right panel — most-used languages by byte share across all public repos.

Data comes from the REST API, plus one GraphQL call for contribution counts
(which REST does not expose). Without a token the GraphQL step is skipped and
those tiles are simply omitted, so the script still runs locally.

Palette matches the hero banner: #0D1117 base, #3B82F6 / #06B6D4 / #8B5CF6.

Usage:  python3 .github/scripts/generate_stats.py <username> [outdir]
"""
import html
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"

# ---------------------------------------------------------------- themes ----
THEMES = {
    "dark": {
        "BG": "#0D1117", "PANEL": "#0F1523", "PANEL_BAR": "#131C2E",
        "PRIMARY": "#3B82F6", "SECONDARY": "#06B6D4", "ACCENT": "#8B5CF6",
        "SUCCESS": "#10B981",
        "TEXT": "#F8FAFC", "MUTED": "#94A3B8", "DIM": "#475569",
        "STROKE": "rgba(59,130,246,0.30)",
        "STROKE_HI": "rgba(6,182,212,0.55)",
        "STROKE_LO": "rgba(59,130,246,0.22)",
        "BARLINE": "rgba(255,255,255,0.08)",
        "TRACK": "rgba(148,163,184,0.16)",
        "TILE": "rgba(148,163,184,0.05)",
    },
    "light": {
        "BG": "#F8FAFC", "PANEL": "#FFFFFF", "PANEL_BAR": "#F1F5F9",
        "PRIMARY": "#2563EB", "SECONDARY": "#0891B2", "ACCENT": "#7C3AED",
        "SUCCESS": "#059669",
        "TEXT": "#0F172A", "MUTED": "#475569", "DIM": "#94A3B8",
        "STROKE": "rgba(37,99,235,0.28)",
        "STROKE_HI": "rgba(8,145,178,0.50)",
        "STROKE_LO": "rgba(37,99,235,0.18)",
        "BARLINE": "rgba(15,23,42,0.08)",
        "TRACK": "rgba(71,85,105,0.14)",
        "TILE": "rgba(71,85,105,0.05)",
    },
}

C = {}
SUFFIX = ""

# ---------------------------------------------------------------- layout ----
W, H = 1180, 262
MARGIN = 5
CARD_W = 578
COL2_X = MARGIN + CARD_W + 18
PANEL_Y = 42
PANEL_H = H - PANEL_Y - MARGIN
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

LANG_COLORS = [
    "#3B82F6", "#06B6D4", "#8B5CF6", "#10B981", "#F59E0B", "#EC4899",
]


def set_theme(name):
    global C, SUFFIX
    C = THEMES[name]
    SUFFIX = name


def esc(s):
    return html.escape(str(s), quote=True)


def human(n):
    """1234 -> 1.2k, 1234567 -> 1.2M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


# ------------------------------------------------------------------ fetch ---
def gh(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "stats-panel"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"{API}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def graphql(query, variables):
    """Contribution totals are GraphQL-only. Returns None without a token."""
    if not TOKEN:
        return None
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "stats-panel",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("data")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
        print(f"warn: graphql unavailable: {e}", file=sys.stderr)
        return None


def collect(user, exclude_langs=(), exclude_repos=()):
    """Gather profile totals and aggregate language bytes across public repos.

    exclude_langs / exclude_repos let you drop entries that would otherwise
    skew the byte share — Jupyter notebooks, for instance, count their embedded
    base64 output as source, so a single notebook can outweigh a whole app.
    """
    skip_langs = {s.casefold() for s in exclude_langs}
    skip_repos = {s.casefold() for s in exclude_repos}
    profile = gh(f"/users/{user}")

    repos, page = [], 1
    while True:
        batch = gh(f"/users/{user}/repos?per_page=100&page={page}&type=owner")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    own = [r for r in repos if not r.get("fork")]
    stars = sum(r.get("stargazers_count", 0) for r in own)
    forks = sum(r.get("forks_count", 0) for r in own)

    languages = {}
    for r in own:
        if r["name"].casefold() in skip_repos:
            continue
        try:
            for lang, byts in gh(f"/repos/{r['full_name']}/languages").items():
                if lang.casefold() in skip_langs:
                    continue
                languages[lang] = languages.get(lang, 0) + byts
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
            print(f"warn: languages for {r['full_name']}: {e}", file=sys.stderr)

    contrib = graphql(
        """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              totalCommitContributions
              totalPullRequestContributions
              totalIssueContributions
            }
          }
        }
        """,
        {"login": user},
    )

    facts = {
        "repos": profile.get("public_repos", 0),
        "stars": stars,
        "followers": profile.get("followers", 0),
        "languages": len(languages),
    }

    tiles = [
        ("Public Repos", facts["repos"]),
        ("Total Stars", facts["stars"]),
        ("Followers", facts["followers"]),
    ]
    if contrib and contrib.get("user"):
        cc = contrib["user"]["contributionsCollection"]
        facts["commits"] = cc.get("totalCommitContributions", 0)
        facts["prs"] = cc.get("totalPullRequestContributions", 0)
        tiles += [
            ("Commits (1y)", facts["commits"]),
            ("Pull Requests", facts["prs"]),
            ("Issues Opened", cc.get("totalIssueContributions", 0)),
        ]
    else:
        # no token — fall back to figures REST can supply
        tiles += [
            ("Forks Earned", forks),
            ("Following", profile.get("following", 0)),
            ("Languages", facts["languages"]),
        ]

    return {"user": user, "tiles": tiles, "languages": languages, "facts": facts}


# ---------------------------------------------------------------- drawing ---
def panel(x, y, w, h, title, note="", pulse=0.0):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{C["PANEL"]}" '
        f'stroke="{C["STROKE"]}">'
        f'<animate attributeName="stroke" values="{C["STROKE_LO"]};{C["STROKE_HI"]};'
        f'{C["STROKE_LO"]}" dur="4.5s" begin="{pulse:.2f}s" repeatCount="indefinite"/></rect>'
        f'<rect x="{x}" y="{y}" width="{w}" height="28" rx="12" fill="{C["PANEL_BAR"]}"/>'
        f'<rect x="{x}" y="{y + 16}" width="{w}" height="12" fill="{C["PANEL_BAR"]}"/>'
        f'<line x1="{x}" y1="{y + 28}" x2="{x + w}" y2="{y + 28}" stroke="{C["BARLINE"]}"/>'
        f'<text x="{x + 16}" y="{y + 18}" font-size="9.5" letter-spacing="1.6" '
        f'fill="{C["MUTED"]}">{esc(title)}</text>'
        + (f'<text x="{x + w - 16}" y="{y + 18}" text-anchor="end" font-size="9.5" '
           f'fill="{C["DIM"]}">{esc(note)}</text>' if note else "")
    )


def count_up(x, y, target, begin, size=22, anchor="start", dur=1.0, steps=10):
    """Stepped numeric count-up — one <text> per frame, swapped by <set>."""
    out = []
    frame = dur / steps
    for k in range(steps + 1):
        val = round(target * k / steps)
        show = begin + k * frame
        hide = (f'<set attributeName="opacity" to="0" begin="{show + frame:.2f}s"/>'
                if k < steps else "")
        out.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
            f'font-weight="700" fill="{C["TEXT"]}" opacity="0">{human(val)}'
            f'<set attributeName="opacity" to="1" begin="{show:.2f}s"/>{hide}</text>'
        )
    return "".join(out)


def metrics_panel(tiles):
    x, y = MARGIN, PANEL_Y
    out = [panel(x, y, CARD_W, PANEL_H, "PROFILE.METRICS", "./stats.sh", pulse=0.0)]

    tile_w, tile_h = 178, 82
    for i, (label, value) in enumerate(tiles[:6]):
        col, row = i % 3, i // 3
        tx = x + 14 + col * (tile_w + 6)
        ty = y + 40 + row * (tile_h + 8)
        begin = 0.3 + i * 0.09
        accent = LANG_COLORS[i % len(LANG_COLORS)]

        out.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
            f'dur="0.45s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<rect x="{tx}" y="{ty}" width="{tile_w}" height="{tile_h}" rx="9" '
            f'fill="{C["TILE"]}"/>'
            f'<rect x="{tx}" y="{ty + 14}" width="3" height="{tile_h - 28}" rx="1.5" '
            f'fill="{accent}"/>'
            f'{count_up(tx + 18, ty + 44, value, begin + 0.1)}'
            f'<text x="{tx + 18}" y="{ty + 64}" font-size="10" fill="{C["MUTED"]}">'
            f'{esc(label)}</text></g>'
        )
    return "".join(out)


def languages_panel(languages):
    x, y = COL2_X, PANEL_Y
    out = [panel(x, y, CARD_W, PANEL_H, "TOP.LANGUAGES", "by byte share", pulse=1.4)]

    total = sum(languages.values()) or 1
    top = sorted(languages.items(), key=lambda kv: -kv[1])[:6]
    if not top:
        out.append(f'<text x="{x + CARD_W / 2:.0f}" y="{y + PANEL_H / 2:.0f}" '
                   f'text-anchor="middle" font-size="12" fill="{C["MUTED"]}">'
                   f'no language data</text>')
        return "".join(out)

    label_x = x + 16
    track_x = x + 150
    track_w = 318
    pct_x = x + CARD_W - 16
    # widest name the label column can hold before it would run into the track
    max_label = int((track_x - (label_x + 16) - 8) / 6.65)

    for i, (lang, byts) in enumerate(top):
        frac = byts / total
        ry = y + 54 + i * 26
        begin = 0.45 + i * 0.12
        col = LANG_COLORS[i % len(LANG_COLORS)]
        fill_w = max(2.0, track_w * frac)
        name = lang if len(lang) <= max_label else lang[:max_label - 1] + "…"

        out.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
            f'dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<circle cx="{label_x + 4}" cy="{ry - 4}" r="4" fill="{col}"/>'
            f'<text x="{label_x + 16}" y="{ry}" font-size="11" fill="{C["TEXT"]}">'
            f'{esc(name)}</text>'
            f'<rect x="{track_x}" y="{ry - 9}" width="{track_w}" height="7" rx="3.5" '
            f'fill="{C["TRACK"]}"/>'
            f'<rect x="{track_x}" y="{ry - 9}" width="0" height="7" rx="3.5" fill="{col}">'
            f'<animate attributeName="width" from="0" to="{fill_w:.1f}" dur="1.05s" '
            f'begin="{begin:.2f}s" fill="freeze" calcMode="spline" keyTimes="0;1" '
            f'keySplines="0.22 1 0.36 1"/></rect>'
            f'<text x="{pct_x}" y="{ry}" text-anchor="end" font-size="11" '
            f'font-weight="700" fill="{C["MUTED"]}">{frac * 100:.1f}%</text></g>'
        )
    return "".join(out)


# ------------------------------------------------------------ achievements --
# Tier thresholds, best first. Mirrors the idea behind the trophy services,
# but rendered locally so the section cannot break when someone else's Vercel
# quota runs out.
TIERS = [
    ("S", "#F59E0B"), ("A", "#8B5CF6"), ("B", "#06B6D4"),
    ("C", "#3B82F6"), ("D", "#64748B"),
]

TROPHY_SPECS = [
    ("Repositories", "repos", [100, 50, 25, 10]),
    ("Stars Earned", "stars", [500, 100, 25, 10]),
    ("Followers", "followers", [100, 50, 25, 10]),
    ("Languages", "languages", [10, 8, 6, 4]),
    ("Commits", "commits", [1000, 500, 200, 50]),
    ("Pull Requests", "prs", [100, 50, 20, 5]),
]

TROPHY_W, TROPHY_H = 186, 104


def tier_for(value, cuts):
    for i, cut in enumerate(cuts):
        if value >= cut:
            return TIERS[i]
    return TIERS[-1]


def build_trophies(data):
    """Achievement strip — one badge per metric, tiered S through D."""
    facts = data["facts"]
    gid = f"tacc_{SUFFIX}"
    width, height = 1180, 156

    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{FONT}" role="img" '
        f'aria-label="GitHub achievements for {esc(data["user"])}">',
        f'<rect width="{width}" height="{height}" fill="{C["BG"]}"/>',
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{C["PRIMARY"]}"><animate attributeName="stop-color" '
        f'values="{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]};{C["PRIMARY"]}" '
        f'dur="10s" repeatCount="indefinite"/></stop>'
        f'<stop offset="1" stop-color="{C["ACCENT"]}"><animate attributeName="stop-color" '
        f'values="{C["ACCENT"]};{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]}" '
        f'dur="10s" repeatCount="indefinite"/></stop></linearGradient></defs>',
        f'<text x="{MARGIN + 2}" y="18" font-size="11" letter-spacing="2" '
        f'fill="{C["SECONDARY"]}">ACHIEVEMENTS</text>',
        f'<text x="{MARGIN + 130}" y="18" font-size="10" fill="{C["DIM"]}">'
        f'tiered S &#8594; D</text>',
        f'<line x1="{MARGIN}" y1="28" x2="{width - MARGIN}" y2="28" stroke="url(#{gid})" '
        f'stroke-width="1.5" opacity="0.75"/>',
    ]

    step = (width - 2 * MARGIN - TROPHY_W) / (len(TROPHY_SPECS) - 1)
    for i, (title, key, cuts) in enumerate(TROPHY_SPECS):
        value = facts.get(key)
        if value is None:
            continue
        rank, col = tier_for(value, cuts)
        x = MARGIN + i * step
        y = 42
        begin = 0.25 + i * 0.11

        s.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
            f'dur="0.5s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<rect x="{x:.1f}" y="{y}" width="{TROPHY_W}" height="{TROPHY_H}" rx="11" '
            f'fill="{C["PANEL"]}" stroke="{C["STROKE"]}">'
            f'<animate attributeName="stroke" values="{C["STROKE_LO"]};{C["STROKE_HI"]};'
            f'{C["STROKE_LO"]}" dur="4.5s" begin="{begin + i * 0.4:.2f}s" '
            f'repeatCount="indefinite"/></rect>'
            # tier medallion
            f'<circle cx="{x + TROPHY_W / 2:.1f}" cy="{y + 34}" r="19" fill="none" '
            f'stroke="{col}" stroke-width="2" opacity="0.45">'
            f'<animate attributeName="r" values="19;21;19" dur="3.2s" '
            f'begin="{begin:.2f}s" repeatCount="indefinite"/></circle>'
            f'<circle cx="{x + TROPHY_W / 2:.1f}" cy="{y + 34}" r="15" fill="{col}" '
            f'opacity="0.16"/>'
            f'<text x="{x + TROPHY_W / 2:.1f}" y="{y + 40}" text-anchor="middle" '
            f'font-size="18" font-weight="700" fill="{col}">{rank}</text>'
            # value + label
            f'{count_up(x + TROPHY_W / 2, y + 74, value, begin + 0.15, size=16, anchor="middle", dur=0.9)}'
            f'<text x="{x + TROPHY_W / 2:.1f}" y="{y + 91}" text-anchor="middle" '
            f'font-size="10" fill="{C["MUTED"]}">{esc(title)}</text></g>'
        )

    s.append('</svg>')
    return "".join(s)


def build(data):
    gid = f"acc_{SUFFIX}"
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
        f'aria-label="GitHub statistics for {esc(data["user"])}">',
        f'<rect width="{W}" height="{H}" fill="{C["BG"]}"/>',
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{C["PRIMARY"]}"><animate attributeName="stop-color" '
        f'values="{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]};{C["PRIMARY"]}" '
        f'dur="10s" repeatCount="indefinite"/></stop>'
        f'<stop offset="1" stop-color="{C["ACCENT"]}"><animate attributeName="stop-color" '
        f'values="{C["ACCENT"]};{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]}" '
        f'dur="10s" repeatCount="indefinite"/></stop></linearGradient></defs>',

        f'<text x="{MARGIN + 2}" y="18" font-size="11" letter-spacing="2" '
        f'fill="{C["SECONDARY"]}">GITHUB.STATS</text>',
        f'<text x="{MARGIN + 130}" y="18" font-size="10" fill="{C["DIM"]}">'
        f'@{esc(data["user"])}</text>',
        f'<text x="{W - MARGIN}" y="18" text-anchor="end" font-size="10" '
        f'font-weight="700" fill="{C["SUCCESS"]}">&#9679; SYNCED'
        f'<animate attributeName="opacity" values="1;0.35;1" dur="2.2s" '
        f'repeatCount="indefinite"/></text>',
        f'<line x1="{MARGIN}" y1="28" x2="{W - MARGIN}" y2="28" stroke="url(#{gid})" '
        f'stroke-width="1.5" opacity="0.75"/>',

        metrics_panel(data["tiles"]),
        languages_panel(data["languages"]),
        '</svg>',
    ]
    return "".join(s)


def load_exclusions(path="profile.json"):
    """Optional `stats.excludeLanguages` / `stats.excludeRepos` in profile.json."""
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f).get("stats", {})
        return cfg.get("excludeLanguages", []), cfg.get("excludeRepos", [])
    except (OSError, ValueError):
        return [], []


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: generate_stats.py <username> [outdir]")
    user = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."

    ex_langs, ex_repos = load_exclusions()
    data = collect(user, ex_langs, ex_repos)
    os.makedirs(outdir, exist_ok=True)
    outputs = (
        ("dark", "stats.svg", build),
        ("light", "stats-light.svg", build),
        ("dark", "trophies.svg", build_trophies),
        ("light", "trophies-light.svg", build_trophies),
    )
    for theme, fname, renderer in outputs:
        set_theme(theme)
        svg = renderer(data)
        path = os.path.join(outdir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}: {theme}, {len(svg) / 1024:.1f}KB")


if __name__ == "__main__":
    main()
