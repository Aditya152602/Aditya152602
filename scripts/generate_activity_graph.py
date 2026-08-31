#!/usr/bin/env python3
"""
Generates profile/activity-graph.svg: a contribution-timeline chart styled to
match the old github-readme-activity-graph card, using only GitHub's own
GraphQL API. No third-party server is involved, so nothing here can go down
the way the Vercel-hosted version did.

Required environment variables:
  GH_TOKEN     - a token that can read public GitHub data (secrets.GITHUB_TOKEN
                 works; use a personal access token with `repo` scope if you
                 also want private contributions counted)
  GH_USERNAME  - the GitHub username to report on

Optional:
  GRAPH_DAYS   - how many trailing days to plot (default 31)
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

USERNAME = os.environ["GH_USERNAME"].strip()
TOKEN = os.environ["GH_TOKEN"].strip()  # a trailing newline here breaks HTTP header construction
DAYS = int(os.environ.get("GRAPH_DAYS", "31"))
OUT_PATH = "profile/activity-graph.svg"

# Same palette as the original custom_title=Contribution+Timeline card.
BG_COLOR = "#0A0E14"
AREA_COLOR = "#4FD1C5"
LINE_COLOR = "#E8A854"
POINT_COLOR = "#E9EDF4"
TEXT_COLOR = "#E9EDF4"
MUTED_COLOR = "#8B95A7"
TITLE = "Contribution Timeline"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_contributions():
    to_date = datetime.datetime.now(datetime.timezone.utc)
    from_date = to_date - datetime.timedelta(days=DAYS - 1)
    body = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "login": USERNAME,
                "from": from_date.strftime("%Y-%m-%dT00:00:00Z"),
                "to": to_date.strftime("%Y-%m-%dT23:59:59Z"),
            },
        }
    ).encode()

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": USERNAME,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub API returned {e.code}: {e.read().decode(errors='replace')}")

    if payload.get("errors"):
        sys.exit(f"GitHub API returned errors: {payload['errors']}")

    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    return days[-DAYS:]


def build_svg(days):
    width, height = 720, 260
    pad_l, pad_r, pad_t, pad_b = 40, 20, 50, 30
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    counts = [d["contributionCount"] for d in days]
    max_count = max(counts) if counts and max(counts) > 0 else 1
    n = len(days)

    def x_at(i):
        return pad_l + (chart_w * i / max(n - 1, 1))

    def y_at(c):
        return pad_t + chart_h - (chart_h * c / max_count)

    points = [(x_at(i), y_at(c)) for i, c in enumerate(counts)]
    line_path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area_path = (
        line_path
        + f" L {points[-1][0]:.1f},{pad_t + chart_h:.1f}"
        + f" L {points[0][0]:.1f},{pad_t + chart_h:.1f} Z"
    )

    dots = "\n  ".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{POINT_COLOR}" />' for x, y in points
    )

    label_idx = sorted(set([0, n // 2, n - 1]))
    labels = "\n  ".join(
        f'<text x="{x_at(i):.1f}" y="{height - 8}" font-size="11" '
        f'fill="{MUTED_COLOR}" text-anchor="middle" font-family="Segoe UI, sans-serif">'
        f'{datetime.date.fromisoformat(days[i]["date"]).strftime("%b %d")}</text>'
        for i in label_idx
    )

    total = sum(counts)

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" rx="8" fill="{BG_COLOR}" />
  <text x="{pad_l}" y="28" font-size="16" font-weight="600" fill="{TEXT_COLOR}" font-family="Segoe UI, sans-serif">{TITLE}</text>
  <text x="{width - pad_r}" y="28" font-size="12" fill="{MUTED_COLOR}" text-anchor="end" font-family="Segoe UI, sans-serif">{total} contributions / {DAYS}d</text>
  <path d="{area_path}" fill="{AREA_COLOR}" fill-opacity="0.18" stroke="none" />
  <path d="{line_path}" fill="none" stroke="{LINE_COLOR}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
  {dots}
  {labels}
</svg>"""


def main():
    days = fetch_contributions()
    svg = build_svg(days)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"Wrote {OUT_PATH} covering {days[0]['date']} to {days[-1]['date']}")


if __name__ == "__main__":
    main()
