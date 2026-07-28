#!/usr/bin/env python3
"""
Merge projects.json (hand-curated) with live GitHub data into merged.json.

You control:    name, repo, url, label, description, tags, live, order
Fetched live:   stars, languages (byte split, drives the donut), pushed_at

Entries without a "repo" — client work, private codebases, anything hosted
outside GitHub — are passed straight through, so a card can point at a live
deployment instead. Give those a manual "languages" map if you want a donut.

If the API fails for a repo the card still renders from config alone, so a rate
limit or a network blip degrades the panel instead of breaking the build.
"""
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"


def gh(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "projects-panel",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"{API}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def normalize_repo(raw):
    """Accept 'owner/repo' or a full GitHub URL; return 'owner/repo'."""
    return (
        raw.strip()
        .replace("https://github.com/", "")
        .replace("http://github.com/", "")
        .rstrip("/")
    )


def main():
    with open("projects.json", encoding="utf-8") as f:
        projects = json.load(f)

    fetched = 0
    for p in projects:
        repo = normalize_repo(p.get("repo") or "")
        if not repo:
            # externally hosted — nothing to fetch, keep whatever config supplied
            p.pop("repo", None)
            p.setdefault("languages", {})
            p.setdefault("pushed_at", None)
            continue

        p["repo"] = repo
        try:
            info = gh(f"/repos/{repo}")
            p["stars"] = info.get("stargazers_count", 0)
            p["pushed_at"] = info.get("pushed_at")
            if not p.get("description"):
                p["description"] = info.get("description") or ""
            p["languages"] = gh(f"/repos/{repo}/languages")
            fetched += 1
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
            print(f"warn: could not fetch {repo}: {e}", file=sys.stderr)
            p.setdefault("stars", 0)
            p.setdefault("languages", {})
            p.setdefault("pushed_at", None)

    with open("merged.json", "w", encoding="utf-8") as f:
        json.dump(projects, f)
    print(f"merged {len(projects)} projects ({fetched} enriched from the API)")


if __name__ == "__main__":
    main()
