#!/usr/bin/env python3
"""Render assets/stats.svg — a glass dashboard built from live GitHub data.

Self-contained on purpose: the shared github-readme-stats instance rate-limits
and renders an error card into the profile when it does. This reads the API and
the public contributions calendar directly, and if anything fails it leaves the
existing card untouched rather than publishing a broken one.
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
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(url, raw=False):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-stats"}
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {TOKEN}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=30
            ) as r:
                return r.read().decode() if raw else json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def api(path):
    return fetch(path if path.startswith("http") else f"https://api.github.com/{path}")


def search(q):
    time.sleep(2)  # the search endpoint throttles hard
    return api(f"search/issues?q={urllib.parse.quote(q)}&per_page=1")["total_count"]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def calendar():
    """Daily contribution counts, scraped from the public profile calendar.

    Deliberately not the GraphQL API: this needs no token and no scopes.
    """
    html = fetch(f"https://github.com/users/{USER}/contributions", raw=True)
    tips = dict(
        re.findall(
            r'<tool-tip[^>]*for="(contribution-day-component-[^"]+)"[^>]*>([^<]*)</tool-tip>',
            html,
        )
    )
    days = []
    for td in re.findall(r"<td\b[^>]*data-date=\"[^\"]+\"[^>]*>", html):
        attr = lambda a: (re.search(rf'{a}="([^"]*)"', td) or [None, None])[1]
        hit = re.match(r"([\d,]+) contribution", tips.get(attr("id"), ""))
        days.append((attr("data-date"), int(hit.group(1).replace(",", "")) if hit else 0))
    days.sort()
    return days


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
        "days": calendar(),
    }


def area_chart(days, x0, x1, top, bot):
    """Weekly contribution totals as a filled area chart."""
    weeks = [sum(c for _, c in days[i:i + 7]) for i in range(0, len(days), 7)]
    starts = [days[i][0] for i in range(0, len(days), 7)]
    peak = max(weeks) or 1
    step = (x1 - x0) / max(len(weeks) - 1, 1)
    pts = [(x0 + i * step, bot - (v / peak) * (bot - top)) for i, v in enumerate(weeks)]

    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    fill = f"{x0:.1f},{bot:.1f} {line} {x1:.1f},{bot:.1f}"

    ticks, last = [], -999
    for i, s in enumerate(starts):
        x = x0 + i * step
        if s[8:10] <= "07" and x - last > 58:  # first week of a month
            ticks.append(
                f'<text x="{x:.0f}" y="{bot + 18:.0f}" font-size="9.5" fill="#60728F" '
                f'text-anchor="middle">{MONTHS[int(s[5:7]) - 1]}</text>'
            )
            last = x

    hi = max(range(len(weeks)), key=lambda i: weeks[i])
    hx, hy = pts[hi]
    marker = (
        f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="3.5" fill="#58A6FF" '
        f'stroke="#0B1220" stroke-width="1.5"/>'
        f'<text x="{min(max(hx, x0 + 14), x1 - 14):.1f}" y="{hy - 10:.1f}" font-size="10.5" '
        f'font-weight="600" fill="#9FD0FF" text-anchor="middle">{peak}</text>'
    )

    grid = "".join(
        f'<line x1="{x0}" y1="{bot - f * (bot - top):.1f}" x2="{x1}" '
        f'y2="{bot - f * (bot - top):.1f}" stroke="#FFFFFF" stroke-opacity=".06"/>'
        for f in (0, 0.5, 1)
    )
    return (
        f'{grid}<polygon points="{fill}" fill="url(#chartfill)"/>'
        f'<polyline points="{line}" fill="none" stroke="#58A6FF" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>{marker}{"".join(ticks)}',
        sum(weeks),
    )


def lang_rows(langs, x0, x1, y0, gap):
    total = sum(n for _, n in langs) or 1
    track = x1 - x0
    out = []
    for i, (name, n) in enumerate(langs):
        pct = n / total
        y = y0 + i * gap
        color = LANG_COLOR.get(name, FALLBACK[i % len(FALLBACK)])
        out.append(
            f'<text x="{x0}" y="{y}" font-size="11.5" fill="#AEBBD0">{esc(name)}</text>'
            f'<text x="{x1}" y="{y}" font-size="11.5" fill="#6E7F99" text-anchor="end">{pct * 100:.1f}%</text>'
            f'<rect x="{x0}" y="{y + 7}" width="{track}" height="6" rx="3" fill="#FFFFFF" fill-opacity=".07"/>'
            f'<rect x="{x0}" y="{y + 7}" width="{max(track * pct, 3):.1f}" height="6" rx="3" fill="{color}"/>'
        )
    return "".join(out)


def render(d):
    tiles, x = [], 64
    for value, label in (
        (f"{d['commits']:,}", "COMMITS"),
        (f"{d['prs']:,}", f"PULL REQUESTS · {d['merged']:,} MERGED"),
        (f"{d['issues']:,}", "ISSUES"),
        (f"{d['repos']:,}", "REPOSITORIES"),
        (f"{d['touched']:,}", "CONTRIBUTED TO"),
    ):
        tiles.append(
            f'<text x="{x}" y="108" font-size="31" font-weight="600" fill="#F0F6FC" '
            f'letter-spacing="-0.5">{esc(value)}</text>'
            f'<text x="{x}" y="128" font-size="9" font-weight="500" fill="#8B9BB4" '
            f'letter-spacing="1.1">{esc(label)}</text>'
        )
        x += 180 if label != "PULL REQUESTS · {} MERGED".format(f"{d['merged']:,}") else 212
    tiles = "".join(tiles)

    chart, year_total = area_chart(d["days"], 64, 596, 196, 300)
    langs = lang_rows(d["langs"], 648, 936, 202, 26)
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="392" viewBox="0 0 1000 392"
     role="img" aria-label="GitHub activity for {esc(USER)}: {d['commits']:,} commits, {d['prs']:,} pull requests, {d['issues']:,} issues, {d['repos']:,} repositories, {year_total:,} contributions in the last year">
  <title>GitHub activity for {esc(USER)}</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#070B16"/><stop offset="55%" stop-color="#101A38"/>
      <stop offset="100%" stop-color="#070B16"/>
    </linearGradient>
    <radialGradient id="g1"><stop offset="0%" stop-color="#1F6FEB" stop-opacity=".9"/><stop offset="100%" stop-color="#1F6FEB" stop-opacity="0"/></radialGradient>
    <radialGradient id="g2"><stop offset="0%" stop-color="#22D3EE" stop-opacity=".7"/><stop offset="100%" stop-color="#22D3EE" stop-opacity="0"/></radialGradient>
    <radialGradient id="g3"><stop offset="0%" stop-color="#A78BFA" stop-opacity=".7"/><stop offset="100%" stop-color="#A78BFA" stop-opacity="0"/></radialGradient>
    <linearGradient id="chartfill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#58A6FF" stop-opacity=".40"/>
      <stop offset="100%" stop-color="#58A6FF" stop-opacity="0"/>
    </linearGradient>

    <g id="field">
      <rect width="1000" height="392" fill="url(#bg)"/>
      <ellipse cx="170" cy="330" rx="250" ry="170" fill="url(#g1)">
        <animateTransform attributeName="transform" type="translate"
          values="0 0; 80 -36; -30 -14; 0 0" dur="21s" repeatCount="indefinite"/></ellipse>
      <ellipse cx="640" cy="40" rx="250" ry="160" fill="url(#g2)">
        <animateTransform attributeName="transform" type="translate"
          values="0 0; -70 40; 40 16; 0 0" dur="25s" repeatCount="indefinite"/></ellipse>
      <ellipse cx="900" cy="320" rx="240" ry="160" fill="url(#g3)">
        <animateTransform attributeName="transform" type="translate"
          values="0 0; -50 -44; 28 22; 0 0" dur="29s" repeatCount="indefinite"/></ellipse>
    </g>

    <filter id="liquid" x="-20%" y="-20%" width="140%" height="140%">
      <feTurbulence type="fractalNoise" baseFrequency="0.010 0.016" numOctaves="2" seed="5" result="n">
        <animate attributeName="baseFrequency" values="0.010 0.016; 0.015 0.011; 0.010 0.016"
                 dur="26s" repeatCount="indefinite"/>
      </feTurbulence>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="26" xChannelSelector="R" yChannelSelector="G" result="w"/>
      <feGaussianBlur in="w" stdDeviation="14"/>
    </filter>

    <rect id="shape" x="26" y="26" width="948" height="340" rx="30"/>
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
    <text x="64" y="66" font-size="11" font-weight="500" fill="#8B9BB4" letter-spacing="1.4">GITHUB ACTIVITY</text>
    <text x="936" y="66" font-size="10.5" fill="#60728F" text-anchor="end">updated {stamp}</text>
    {tiles}
    <line x1="64" y1="152" x2="936" y2="152" stroke="#FFFFFF" stroke-opacity=".08"/>

    <text x="64" y="176" font-size="9" font-weight="500" fill="#8B9BB4" letter-spacing="1.1">CONTRIBUTIONS · LAST 12 MONTHS · {year_total:,}</text>
    {chart}

    <text x="648" y="176" font-size="9" font-weight="500" fill="#8B9BB4" letter-spacing="1.1">LANGUAGES</text>
    {langs}
  </g>
</svg>
'''


def main():
    d = collect()
    if not d["commits"] or not d["repos"] or not d["days"]:
        print("incomplete data; keeping existing card")
        return 0
    os.makedirs("assets", exist_ok=True)
    svg = render(d)
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    strip = lambda s: re.sub(r"updated [^<]*", "", s)  # ignore the date stamp
    if strip(old) == strip(svg):
        print("no change")
        return 0
    open(OUT, "w", encoding="utf-8").write(svg)
    print("wrote", OUT, "|", {k: v for k, v in d.items() if k not in ("langs", "days")})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - a scheduled run must never fail loudly
        print(f"stats update skipped: {e}", file=sys.stderr)
        sys.exit(0)
