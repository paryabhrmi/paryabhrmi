#!/usr/bin/env python3
"""Render the contribution calendar as an SVG in this profile's own palette.

GitHub's calendar is GitHub's UI — it cannot be restyled or scripted from a
README. This draws the same data as a plain SVG the repository serves itself,
so the colours, the type and the motion belong to the profile rather than to
GitHub's green.

    python3 tools/contribution_grid.py --login paryabhrmi     # live data
    python3 tools/contribution_grid.py --demo                 # synthetic data

Live mode needs a token on GITHUB_TOKEN with permission to read the account's
public contribution calendar.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import random
import sys
import urllib.error
import urllib.request

OUT = pathlib.Path("assets")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""

THEMES = {
    "dark": dict(
        bg="#0D1117", ink="#E6EDF3", muted="#8A7C73", hair="#2A2320",
        empty="#1B1613",
        ramp=["#4A2214", "#7A3319", "#AE451F", "#E2673A"],
        glow="#FFFFFF",
    ),
    "light": dict(
        bg="#FFFFFF", ink="#1A1512", muted="#8A7C73", hair="#E4DAD0",
        empty="#F1EAE3",
        ramp=["#F0CDBC", "#DFA184", "#CC6E48", "#BE4A22"],
        glow="#1A1512",
    ),
}

CELL, GAP = 11, 3
STEP = CELL + GAP
PAD_L, PAD_T = 34, 26
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONO = ('ui-monospace,&quot;SF Mono&quot;,SFMono-Regular,Menlo,Consolas,'
        '&quot;Liberation Mono&quot;,monospace')


def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "contribution-grid",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    user = payload.get("data", {}).get("user")
    if not user:
        raise SystemExit(f"No such user in response: {payload}")
    return user["contributionsCollection"]["contributionCalendar"]


def demo() -> dict:
    """Synthetic calendar, for previewing the design without a token."""
    rng = random.Random(7)
    end = dt.date(2026, 8, 10)
    start = end - dt.timedelta(days=end.weekday() + 7 * 52)
    weeks, total, day = [], 0, start
    while day <= end:
        days = []
        for _ in range(7):
            if day > end:
                break
            age = (day - start).days / 371
            n = 0 if rng.random() > 0.12 + age * 0.5 else rng.randint(1, 9)
            total += n
            days.append({"date": day.isoformat(), "contributionCount": n,
                         "weekday": (day.weekday() + 1) % 7})
            day += dt.timedelta(days=1)
        weeks.append({"contributionDays": days})
    return {"totalContributions": total, "weeks": weeks}


def level(n: int, peak: int) -> int:
    """0 for an empty day, then three quartiles of the year's own busiest day."""
    if n <= 0:
        return 0
    if peak <= 1:
        return 4
    return min(4, 1 + int(3 * math.log1p(n) / math.log1p(peak)))


def render(cal: dict, theme: str) -> str:
    t = THEMES[theme]
    weeks = cal["weeks"]
    peak = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=0)

    width = PAD_L + len(weeks) * STEP + 14
    height = PAD_T + 7 * STEP + 34

    cells, labels, seen = [], [], set()
    for wi, week in enumerate(weeks):
        x = PAD_L + wi * STEP
        for day in week["contributionDays"]:
            n = day["contributionCount"]
            lv = level(n, peak)
            y = PAD_T + day["weekday"] * STEP
            fill = t["empty"] if lv == 0 else t["ramp"][lv - 1]
            # Stagger by column so the year fills in left to right.
            cells.append(
                f'<rect class="c" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{fill}" style="animation-delay:{wi * 0.014:.3f}s">'
                f'<title>{day["date"]} — {n} contribution{"" if n == 1 else "s"}</title></rect>'
            )
        month = dt.date.fromisoformat(week["contributionDays"][0]["date"]).month
        if month not in seen and wi < len(weeks) - 2:
            seen.add(month)
            labels.append(f'<text x="{x}" y="{PAD_T - 9}">{MONTHS[month - 1]}</text>')

    legend_x = width - 14 - 5 * STEP - 46
    legend = "".join(
        f'<rect x="{legend_x + 30 + i * STEP}" y="{height - 22}" width="{CELL}" height="{CELL}" '
        f'rx="2.5" fill="{t["empty"] if i == 0 else t["ramp"][i - 1]}"/>'
        for i in range(5)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{cal['totalContributions']} contributions in the last year, shown as a calendar heat map.">
<style><![CDATA[
  text{{font-family:{MONO};font-size:9px;letter-spacing:.06em;fill:{t['muted']}}}
  .c{{animation:pop .55s cubic-bezier(.2,.8,.3,1) backwards}}
  @keyframes pop{{from{{opacity:0;transform:translateY(3px) scale(.6)}}
                  to{{opacity:1;transform:none}}}}
  .c{{transform-box:fill-box;transform-origin:center}}
  .sweep{{animation:sweep 7s linear infinite;animation-delay:1.4s}}
  @keyframes sweep{{0%{{transform:translateX(-90px)}}
                    55%,100%{{transform:translateX({width + 40}px)}}}}
  @media (prefers-reduced-motion:reduce){{
    .c{{animation:none}}
    .sweep{{display:none}}
  }}
]]></style>
<defs>
  <linearGradient id="sw" x1="0" x2="1" y1="0" y2="0">
    <stop offset="0" stop-color="{t['glow']}" stop-opacity="0"/>
    <stop offset=".5" stop-color="{t['glow']}" stop-opacity=".10"/>
    <stop offset="1" stop-color="{t['glow']}" stop-opacity="0"/>
  </linearGradient>
</defs>

<rect width="{width}" height="{height}" fill="{t['bg']}"/>
<g>{"".join(labels)}</g>
<g class="grid">{"".join(cells)}</g>
<rect class="sweep" x="0" y="{PAD_T - 4}" width="90" height="{7 * STEP + 4}" fill="url(#sw)"/>

<text x="{PAD_L}" y="{height - 12}" fill="{t['ink']}">{cal['totalContributions']} contributions in the last year</text>
<text x="{legend_x}" y="{height - 12}">Less</text>
{legend}
<text x="{legend_x + 30 + 5 * STEP + 4}" y="{height - 12}">More</text>

<g fill="{t['muted']}">
  <text x="6" y="{PAD_T + STEP + 9}">Mon</text>
  <text x="6" y="{PAD_T + 3 * STEP + 9}">Wed</text>
  <text x="6" y="{PAD_T + 5 * STEP + 9}">Fri</text>
</g>
</svg>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--login")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.demo:
        cal = demo()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not (args.login and token):
            sys.exit("need --login and GITHUB_TOKEN (or pass --demo)")
        try:
            cal = fetch(args.login, token)
        except urllib.error.HTTPError as e:
            sys.exit(f"GitHub returned {e.code}: {e.read().decode()[:300]}")

    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = OUT / f"contributions-{theme}.svg"
        path.write_text(render(cal, theme), encoding="utf-8")
        print(f"wrote {path}")
    print(f"total: {cal['totalContributions']}")


if __name__ == "__main__":
    main()
