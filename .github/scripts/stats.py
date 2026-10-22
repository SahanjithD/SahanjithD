#!/usr/bin/env python3
"""Regenerate the profile stats sentence between the README's stats markers.

Runs in GitHub Actions. If the API misbehaves the README is left untouched
rather than rewritten with wrong or partial numbers.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("USER_LOGIN") or os.environ["GITHUB_REPOSITORY"].split("/")[0]
TOKEN = os.environ["GITHUB_TOKEN"]
README = "README.md"
START, END = "<!-- stats:start -->", "<!-- stats:end -->"


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": f"{USER}-profile-stats",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                raise
            # Search endpoints throttle aggressively; back off and retry.
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def count(query):
    time.sleep(2)  # stay under the 30 req/min search limit
    return api(f"search/issues?q={query}&per_page=1")["total_count"]


def main():
    user = api(f"users/{USER}")
    created = datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    years = int((datetime.now(timezone.utc) - created).days / 365.25)

    time.sleep(2)
    commits = api(f"search/commits?q=author:{USER}&per_page=1")["total_count"]
    prs = count(f"author:{USER}+type:pr")
    merged = count(f"author:{USER}+type:pr+is:merged")
    issues = count(f"author:{USER}+type:issue")

    repos = api(f"users/{USER}/repos?per_page=100")
    own = sum(1 for r in repos if not r["fork"])

    # Distinct repositories touched by an authored pull request.
    time.sleep(2)
    items = api(f"search/issues?q=author:{USER}+type:pr&per_page=100")["items"]
    touched = len({i["repository_url"] for i in items})

    if not all([commits, prs, own]):
        print("incomplete data, leaving README unchanged")
        return 0

    plural = "year" if years == 1 else "years"
    sentence = (
        f"I joined GitHub **{years}** {plural} ago and have since pushed "
        f"**{commits:,}** commits, opened **{issues:,}** issues and\n"
        f"submitted **{prs:,}** pull requests — **{merged:,}** of them merged — across "
        f"**{own:,}** personal projects and\n**{touched:,}** repositories."
    )

    text = open(README, encoding="utf-8").read()
    new = re.sub(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        f"{START}\n{sentence}\n{END}",
        text,
        flags=re.DOTALL,
    )
    if new == text:
        print("no change")
        return 0
    open(README, "w", encoding="utf-8").write(new)
    print("updated:", sentence.replace("\n", " "))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - never fail the scheduled run
        print(f"stats update skipped: {e}", file=sys.stderr)
        sys.exit(0)
