#!/usr/bin/env python3
"""Render assets/stats.svg — a glass stats card built from live GitHub data.

Self-contained on purpose: the shared github-readme-stats instance rate-limits
and renders an error card into the profile when it does. This talks to the API
directly and, if anything fails, leaves the existing card in place.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("USER_LOGIN") or os.environ.get(
    "GITHUB_REPOSITORY", "SahanjithD/x"
).split("/")[0]
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = "assets/stats.svg"

# Byte counts for these are dominated by embedded output or boilerplate, so they
# drown out the languages actually being written.
SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS"}

LANG_COLOR = {
    "Ballerina": "#FF5000", "Python": "#3572A5", "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A", "Java": "#B07219", "C#": "#178600",
    "Go": "#00ADD8", "Rust": "#DEA584", "Shell": "#89E051",
    "HCL": "#844FBA", "PLpgSQL": "#336790", "C": "#555555",
    "C++": "#F34B7D", "Dockerfile": "#384D54",
}
FALLBACK = ["#58A6FF", "#22D3EE", "#A78BFA", "#F472B6", "#FBBF24", "#34D399"]


def api(path):
    url = path if path.startswith("http") else f"https://api.github.com/{path}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=30
            ) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def search(q):
    time.sleep(2)  # the search endpoint throttles hard
    return api(f"search/issues?q={urllib.parse.quote(q)}&per_page=1")["total_count"]


def esc(s):
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def collect():
    time.sleep(2)
    commits = api(
        f"search/commits?q={urllib.parse.quote('author:' + USER)}&per_page=1"
    )["total_count"]
    prs = search(f"author:{USER} type:pr")
    merged = search(f"author:{USER} type:pr is:merged")
    issues = search(f"author:{USER} type:issue")

    time.sleep(2)
    items = api(
        f"search/issues?q={urllib.parse.quote('author:' + USER + ' type:pr')}&per_page=100"
    )["items"]
    touched = len({i["repository_url"] for i in items})

    repos = [r for r in api(f"users/{USER}/repos?per_page=100") if not r["fork"]]

    langs = {}
    for r in repos:
        for name, n in (api(r["languages_url"]) or {}).items():
            if name not in SKIP_LANGS:
                langs[name] = langs.get(name, 0) + n

    return {
        "commits": commits, "prs": prs, "merged": merged, "issues": issues,
        "repos": len(repos), "touched": touched,
        "langs": sorted(langs.items(), key=lambda kv: -kv[1])[:5],
    }


def render(d):
    tiles = [
        (f"{d['commits']:,}", "COMMITS"),
        (f"{d['prs']:,}", f"PULL REQUESTS · {d['merged']:,} MERGED"),
        (f"{d['issues']:,}", "ISSUES"),
        (f"{d['repos']:,}", "REPOSITORIES"),
        (f"{d['touched']:,}", "CONTRIBUTED TO"),
    ]
    cells = []
    x = 64
    for i, (value, label) in enumerate(tiles):
        cells.append(
            f'<text x="{x}" y="118" font-size="34" font-weight="600" fill="#F0F6FC" '
            f'letter-spacing="-0.5">{esc(value)}</text>'
            f'<text x="{x}" y="140" font-size="9.5" font-weight="500" fill="#8B9BB4" '
            f'letter-spacing="1.1">{esc(label)}</text>'
        )
        x += 182 if i != 1 else 206
    cells = "\n    ".join(cells)

    total = sum(n for _, n in d["langs"]) or 1
    bar, legend, bx, lx = [], [], 64.0, 64.0
    for i, (name, n) in enumerate(d["langs"]):
        pct = n / total
        w = max(pct * 872, 3)
        color = LANG_COLOR.get(name, FALLBACK[i % len(FALLBACK)])
        bar.append(f'<rect x="{bx:.1f}" y="178" width="{w:.1f}" height="9" fill="{color}"/>')
        bx += w
        legend.append(
            f'<circle cx="{lx:.0f}" cy="209" r="3.5" fill="{color}"/>'
            f'<text x="{lx + 11:.0f}" y="213" font-size="11.5" fill="#AEBBD0">'
            f'{esc(name)} <tspan fill="#6E7F99">{pct * 100:.1f}%</tspan></text>'
        )
        lx += 22 + len(name) * 7.0 + 42
    bar, legend = "\n    ".join(bar), "\n    ".join(legend)

    stamp = datetime.now(timezone.utc).strftime("%d %b %Y")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="250" viewBox="0 0 1000 250"
     role="img" aria-label="GitHub activity for {esc(USER)}: {d['commits']:,} commits, {d['prs']:,} pull requests, {d['issues']:,} issues across {d['repos']:,} repositories">
  <title>GitHub activity for {esc(USER)}</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#070B16"/><stop offset="55%" stop-color="#101A38"/>
      <stop offset="100%" stop-color="#070B16"/>
    </linearGradient>
    <radialGradient id="g1"><stop offset="0%" stop-color="#1F6FEB" stop-opacity=".9"/><stop offset="100%" stop-color="#1F6FEB" stop-opacity="0"/></radialGradient>
    <radialGradient id="g2"><stop offset="0%" stop-color="#22D3EE" stop-opacity=".7"/><stop offset="100%" stop-color="#22D3EE" stop-opacity="0"/></radialGradient>
    <radialGradient id="g3"><stop offset="0%" stop-color="#A78BFA" stop-opacity=".7"/><stop offset="100%" stop-color="#A78BFA" stop-opacity="0"/></radialGradient>

    <g id="field">
      <rect width="1000" height="250" fill="url(#bg)"/>
      <ellipse cx="180" cy="210" rx="250" ry="150" fill="url(#g1)">
        <animateTransform attributeName="transform" type="translate"
          values="0 0; 80 -30; -30 -12; 0 0" dur="21s" repeatCount="indefinite"/></ellipse>
      <ellipse cx="620" cy="30" rx="240" ry="140" fill="url(#g2)">
        <animateTransform attributeName="transform" type="translate"
          values="0 0; -70 36; 40 14; 0 0" dur="25s" repeatCount="indefinite"/></ellipse>
      <ellipse cx="900" cy="200" rx="230" ry="140" fill="url(#g3)">
        <animateTransform attributeName="transform" type="translate"
          values="0 0; -48 -40; 26 20; 0 0" dur="29s" repeatCount="indefinite"/></ellipse>
    </g>

    <filter id="liquid" x="-20%" y="-20%" width="140%" height="140%">
      <feTurbulence type="fractalNoise" baseFrequency="0.010 0.016" numOctaves="2" seed="5" result="n">
        <animate attributeName="baseFrequency" values="0.010 0.016; 0.015 0.011; 0.010 0.016"
                 dur="26s" repeatCount="indefinite"/>
      </feTurbulence>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="26" xChannelSelector="R" yChannelSelector="G" result="w"/>
      <feGaussianBlur in="w" stdDeviation="14"/>
    </filter>

    <rect id="shape" x="26" y="26" width="948" height="198" rx="30"/>
    <clipPath id="clip"><use href="#shape"/></clipPath>
    <linearGradient id="sheen" x1="0" y1="0" x2="0.65" y2="1">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity=".20"/>
      <stop offset="42%" stop-color="#FFFFFF" stop-opacity=".05"/>
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity=".5"/>
      <stop offset="50%" stop-color="#FFFFFF" stop-opacity=".12"/>
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity=".3"/>
    </linearGradient>
  </defs>

  <use href="#field"/>
  <g clip-path="url(#clip)">
    <use href="#field" filter="url(#liquid)"/>
    <use href="#shape" fill="#FFFFFF" fill-opacity=".10"/>
    <use href="#shape" fill="url(#sheen)"/>
  </g>
  <use href="#shape" fill="none" stroke="url(#edge)" stroke-width="1.25"/>

  <g font-family="SF Pro Display,-apple-system,BlinkMacSystemFont,Segoe UI,Inter,Helvetica Neue,Arial,sans-serif">
    <text x="64" y="68" font-size="11" font-weight="500" fill="#8B9BB4" letter-spacing="1.4">GITHUB ACTIVITY</text>
    <text x="936" y="68" font-size="10.5" fill="#60728F" text-anchor="end">updated {stamp}</text>
    {cells}
    <g clip-path="url(#clip)">
      <rect x="64" y="178" width="872" height="9" rx="4.5" fill="#FFFFFF" fill-opacity=".07"/>
      <g clip-path="url(#barclip)">{bar}</g>
    </g>
    {legend}
  </g>
  <defs><clipPath id="barclip"><rect x="64" y="178" width="872" height="9" rx="4.5"/></clipPath></defs>
</svg>
'''


def main():
    data = collect()
    if not data["commits"] or not data["repos"]:
        print("incomplete data; keeping existing card")
        return 0
    os.makedirs("assets", exist_ok=True)
    svg = render(data)
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    # Ignore the date stamp so an unchanged card is not recommitted daily.
    strip = lambda s: re.sub(r"updated [^<]*", "", s)
    if strip(old) == strip(svg):
        print("no change")
        return 0
    open(OUT, "w", encoding="utf-8").write(svg)
    print("wrote", OUT, "|", {k: v for k, v in data.items() if k != "langs"})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - a scheduled run must never fail loudly
        print(f"stats update skipped: {e}", file=sys.stderr)
        sys.exit(0)
