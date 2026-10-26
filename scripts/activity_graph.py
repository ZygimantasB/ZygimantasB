"""Generate a contribution activity graph SVG (tokyonight style).

Replaces the dead github-readme-activity-graph.vercel.app service.
Runs in GitHub Actions; needs GITHUB_TOKEN and GH_USER env vars.
Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# Tokyo Night palette
BG = "#1a1b27"
TITLE = "#70a5fd"
LINE = "#bf91f3"
POINT = "#38bdae"
AXIS = "#565f89"
TEXT = "#a9b1d6"

WIDTH, HEIGHT = 1200, 360
PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 60, 50


def fetch_days(user: str, token: str, days: int = 31) -> list[tuple[date, int]]:
    to_d = date.today()
    from_d = to_d - timedelta(days=days - 1)
    payload = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "login": user,
                "from": f"{from_d.isoformat()}T00:00:00Z",
                "to": f"{to_d.isoformat()}T23:59:59Z",
            },
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    result = [
        (date.fromisoformat(d["date"]), d["contributionCount"])
        for w in weeks
        for d in w["contributionDays"]
    ]
    return [r for r in result if from_d <= r[0] <= to_d]


def nice_max(value: int) -> int:
    if value <= 5:
        return 5
    step = 5 if value <= 50 else 10 if value <= 100 else 50
    return ((value + step - 1) // step) * step


def render_svg(user: str, days: list[tuple[date, int]]) -> str:
    plot_w = WIDTH - PAD_L - PAD_R
    plot_h = HEIGHT - PAD_T - PAD_B
    y_max = nice_max(max((c for _, c in days), default=0))
    n = max(len(days) - 1, 1)

    def xy(i: int, c: int) -> tuple[float, float]:
        return PAD_L + plot_w * i / n, PAD_T + plot_h * (1 - c / y_max)

    pts = [xy(i, c) for i, (_, c) in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    base_y = PAD_T + plot_h
    area = f"{PAD_L:.1f},{base_y} {line} {pts[-1][0]:.1f},{base_y}" if pts else ""

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Segoe UI, Ubuntu, sans-serif">',
        "<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
        f"<stop offset='0' stop-color='{LINE}' stop-opacity='0.45'/>"
        f"<stop offset='1' stop-color='{LINE}' stop-opacity='0.02'/></linearGradient></defs>",
        f'<rect width="100%" height="100%" rx="6" fill="{BG}"/>',
        f'<text x="{WIDTH / 2}" y="34" fill="{TITLE}" font-size="20" font-weight="600" '
        f'text-anchor="middle">{user}\'s Contribution Graph (last {len(days)} days)</text>',
    ]
    for k in range(6):
        val = y_max * k / 5
        y = PAD_T + plot_h * (1 - k / 5)
        out.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{WIDTH - PAD_R}" y2="{y:.1f}" '
            f'stroke="{AXIS}" stroke-width="0.6" stroke-dasharray="4 4"/>'
        )
        out.append(
            f'<text x="{PAD_L - 10}" y="{y + 4:.1f}" fill="{TEXT}" font-size="12" '
            f'text-anchor="end">{val:g}</text>'
        )
    if pts:
        out.append(f'<polygon points="{area}" fill="url(#g)"/>')
        out.append(
            f'<polyline points="{line}" fill="none" stroke="{LINE}" stroke-width="2.5" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )
    for i, ((d, c), (x, y)) in enumerate(zip(days, pts)):
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{POINT}">'
            f"<title>{d.isoformat()}: {c} contributions</title></circle>"
        )
        if i % 3 == 0 or i == len(days) - 1:
            out.append(
                f'<text x="{x:.1f}" y="{base_y + 22}" fill="{TEXT}" font-size="12" '
                f'text-anchor="middle">{d.day}</text>'
            )
    out.append(
        f'<text x="{WIDTH / 2}" y="{HEIGHT - 6}" fill="{AXIS}" font-size="12" '
        'text-anchor="middle">Days</text>'
    )
    out.append(
        f'<text x="18" y="{PAD_T + plot_h / 2}" fill="{AXIS}" font-size="12" text-anchor="middle" '
        f'transform="rotate(-90 18 {PAD_T + plot_h / 2})">Contributions</text>'
    )
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    user = os.environ.get("GH_USER", "ZygimantasB")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is not set", file=sys.stderr)
        return 1
    out_path = Path(sys.argv[1] if len(sys.argv) > 1 else "metrics/activity-graph.svg")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_svg(user, fetch_days(user, token)), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
