#!/usr/bin/env python3
"""Build a static comparison page for Sling vs Demo solver output.

Reads profiles.json, demo.json, sling.json from the cwd, emits index.html
(self-contained: data inlined, no external assets, opens locally or on
GitHub Pages without a build step).
"""
import json
from datetime import datetime
from pathlib import Path

WEEK_START = "2026-05-25"  # Monday
DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
WEEKDAYS_ORDER = [1, 2, 3, 4, 5, 6, 0]  # Mon..Sun

GRID_START_HOUR = 6
GRID_END_HOUR = 22
HOUR_PX = 48  # pixels per hour in the visual

def load():
    profiles = json.loads(Path("profiles.json").read_text())
    demo = json.loads(Path("demo.json").read_text())
    sling = json.loads(Path("sling.json").read_text())
    return profiles, demo["shifts"], sling["rows"]

def normalize_sling(rows):
    """Convert Sling rows (start_local "YYYY-MM-DD HH:MM:SS") to common shape."""
    out = []
    week_monday = datetime.strptime(WEEK_START, "%Y-%m-%d")
    for r in rows:
        # Parse start_local; format "2026-05-25 06:20:00"
        s = datetime.strptime(r["start_local"], "%Y-%m-%d %H:%M:%S")
        e = datetime.strptime(r["end_local"], "%Y-%m-%d %H:%M:%S")
        delta_days = (s.date() - week_monday.date()).days
        # Convert delta_days (0..6 where 0=Mon) to JS-native weekday (0=Sun..6=Sat)
        weekday_js = (delta_days + 1) % 7
        out.append({
            "id": r["shift_id"],
            "weekday": weekday_js,
            "start_min": s.hour * 60 + s.minute,
            "duration_min": int((e - s).total_seconds() / 60),
            "sling_user_id": r["sling_user_id"],
            "role": r.get("effective_role") or r.get("inferred_role") or None,
            "source": "sling",
        })
    return out

def normalize_demo(shifts):
    """Convert demo (already in Shift shape) to common shape."""
    return [{
        "id": s["id"],
        "weekday": s["weekday"],
        "start_min": s["start_min"],
        "duration_min": s["duration_min"],
        "sling_user_id": s["sling_user_id"],
        "role": s.get("covers_role"),
        "source": "demo",
    } for s in shifts]

def by_barista(shifts):
    """Group by sling_user_id and aggregate total minutes."""
    agg = {}
    for s in shifts:
        sid = s["sling_user_id"]
        agg[sid] = agg.get(sid, 0) + s["duration_min"]
    return agg

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Schedule Comparison — Week of {week_start}</title>
<style>
  :root {{
    --grid-bg: #fafafa;
    --row-line: #e5e7eb;
    --col-line: #d1d5db;
    --header-bg: #f3f4f6;
    --text: #1f2937;
    --muted: #6b7280;
    --hour-px: {hour_px}px;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--text);
    background: #fff;
    -webkit-font-smoothing: antialiased;
  }}
  header {{
    padding: 20px 24px;
    border-bottom: 1px solid var(--row-line);
    background: var(--header-bg);
  }}
  header h1 {{ margin: 0 0 4px; font-size: 22px; font-weight: 600; }}
  header p {{ margin: 0; color: var(--muted); font-size: 14px; }}
  header .stats {{ margin-top: 12px; display: flex; gap: 24px; font-size: 13px; }}
  header .stats > div {{ color: var(--muted); }}
  header .stats > div strong {{ color: var(--text); }}
  main {{ padding: 16px 24px 80px; }}
  section.week-block {{
    margin-bottom: 32px;
  }}
  section.week-block > h2 {{
    margin: 0 0 8px;
    font-size: 15px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }}
  .grid-wrap {{
    border: 1px solid var(--col-line);
    border-radius: 8px;
    overflow: hidden;
    background: var(--grid-bg);
  }}
  .grid {{
    display: grid;
    grid-template-columns: 56px repeat(7, 1fr);
    position: relative;
  }}
  .grid .day-header {{
    background: var(--header-bg);
    border-bottom: 1px solid var(--col-line);
    border-left: 1px solid var(--col-line);
    padding: 8px 6px;
    text-align: center;
    font-size: 12px;
    font-weight: 600;
  }}
  .grid .day-header.weekend {{ background: #fef3c7; }}
  .grid .day-header .date {{ display: block; color: var(--muted); font-weight: 400; margin-top: 2px; }}
  .grid .corner {{ background: var(--header-bg); border-bottom: 1px solid var(--col-line); }}
  .grid .hour-label {{
    padding: 2px 6px 0 0;
    font-size: 11px;
    color: var(--muted);
    text-align: right;
    height: var(--hour-px);
    border-top: 1px dashed var(--row-line);
  }}
  .grid .day-col {{
    position: relative;
    border-left: 1px solid var(--col-line);
    height: calc(var(--hour-px) * {grid_hours});
    background-image: repeating-linear-gradient(
      to bottom,
      transparent 0,
      transparent calc(var(--hour-px) - 1px),
      var(--row-line) calc(var(--hour-px) - 1px),
      var(--row-line) var(--hour-px)
    );
  }}
  .shift {{
    position: absolute;
    left: 2px;
    right: 2px;
    border-radius: 4px;
    padding: 3px 5px;
    font-size: 10px;
    line-height: 1.2;
    color: #fff;
    overflow: hidden;
    cursor: default;
    border: 1px solid rgba(0,0,0,0.1);
  }}
  .shift .name {{ font-weight: 600; display: block; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }}
  .shift .meta {{ opacity: 0.85; font-size: 9px; }}
  .shift.sling {{
    background: repeating-linear-gradient(
      135deg,
      var(--color),
      var(--color) 5px,
      color-mix(in srgb, var(--color), white 20%) 5px,
      color-mix(in srgb, var(--color), white 20%) 10px
    );
    border-color: rgba(0,0,0,0.2);
  }}
  table.summary {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 24px;
    font-size: 13px;
  }}
  table.summary th, table.summary td {{
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--row-line);
  }}
  table.summary th {{
    background: var(--header-bg);
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }}
  table.summary td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table.summary td.delta-pos {{ color: #059669; font-weight: 600; }}
  table.summary td.delta-neg {{ color: #dc2626; font-weight: 600; }}
  table.summary td.delta-zero {{ color: var(--muted); }}
  table.summary .swatch {{
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 3px;
    margin-right: 8px;
    vertical-align: middle;
  }}
  .legend {{
    display: flex;
    gap: 16px;
    align-items: center;
    margin: 8px 0 16px;
    font-size: 12px;
    color: var(--muted);
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-box {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    background: #94a3b8;
  }}
  .legend-box.solid {{ background: #94a3b8; }}
  .legend-box.striped {{
    background: repeating-linear-gradient(
      135deg, #94a3b8 0 5px, #cbd5e1 5px 10px
    );
  }}
</style>
</head>
<body>

<header>
  <h1>Schedule Comparison — Week of {week_start} (Mon–Sun)</h1>
  <p>Top grid: <strong>Sling</strong> — what employees actually have scheduled. Bottom grid: <strong>Demo solver</strong> — what the algorithm produced ignoring Sling input. Static snapshot, generated {generated_at}.</p>
  <div class="stats">
    <div>Baristas: <strong>{barista_count}</strong></div>
    <div>Sling shifts: <strong>{sling_count}</strong> · <strong>{sling_hours} h</strong></div>
    <div>Demo shifts: <strong>{demo_count}</strong> · <strong>{demo_hours} h</strong></div>
    <div>Hours delta: <strong>{hours_delta:+d} h</strong></div>
  </div>
  <div class="legend">
    <div class="legend-item"><div class="legend-box solid"></div> Solver-generated</div>
    <div class="legend-item"><div class="legend-box striped"></div> Sling-imported (striped)</div>
  </div>
</header>

<main>
  <section class="week-block">
    <h2>Sling (real schedule)</h2>
    <div class="grid-wrap">
      <div class="grid">
        <div class="corner"></div>
        {day_headers}
        {sling_grid}
      </div>
    </div>
  </section>

  <section class="week-block">
    <h2>Demo solver (ignoring Sling)</h2>
    <div class="grid-wrap">
      <div class="grid">
        <div class="corner"></div>
        {day_headers}
        <div></div>
        {demo_grid}
      </div>
    </div>
  </section>

  <section>
    <h2 style="margin: 0 0 8px; font-size: 15px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted);">Per-barista hours</h2>
    <table class="summary">
      <thead>
        <tr>
          <th>Barista</th>
          <th>Contract</th>
          <th class="num">Target / Max</th>
          <th class="num">Sling h</th>
          <th class="num">Demo h</th>
          <th class="num">Δ</th>
        </tr>
      </thead>
      <tbody>
{summary_rows}
      </tbody>
    </table>
  </section>
</main>

</body>
</html>
"""

def shift_block_html(s, profile_map, source):
    """Render one shift as a positioned absolute div inside its day column."""
    p = profile_map.get(s["sling_user_id"])
    color = (p or {}).get("color", "#94a3b8")
    name = (p or {}).get("name", f"id:{s['sling_user_id']}")
    role = s.get("role") or "no role"
    start_h = s["start_min"] / 60
    dur_h = s["duration_min"] / 60
    top = (start_h - GRID_START_HOUR) * HOUR_PX
    height = dur_h * HOUR_PX - 2
    start_label = f"{s['start_min']//60:02d}:{s['start_min']%60:02d}"
    end_min = s["start_min"] + s["duration_min"]
    end_label = f"{end_min//60:02d}:{end_min%60:02d}"
    return (
        f'<div class="shift {source}" style="top:{top:.1f}px;height:{height:.1f}px;background-color:{color};--color:{color};">'
        f'<span class="name">{name}</span>'
        f'<span class="meta">{role}<br>{start_label}–{end_label}</span>'
        f'</div>'
    )

def day_col_html(weekday, shifts, profile_map, source):
    blocks = [shift_block_html(s, profile_map, source) for s in shifts if s["weekday"] == weekday]
    return f'<div class="day-col">{"".join(blocks)}</div>'

def grid_html(shifts, profile_map, source):
    parts = []
    for hour in range(GRID_START_HOUR, GRID_END_HOUR):
        parts.append(f'<div class="hour-label">{hour:02d}:00</div>')
        for wd in WEEKDAYS_ORDER:
            if hour == GRID_START_HOUR:
                parts.append(day_col_html(wd, shifts, profile_map, source))
            else:
                parts.append('')  # placeholders for grid alignment — handled differently
    # Actually re-doing: each day column spans all hours via height: calc.
    # So the grid is 8 cols × 1 row of day-cols, with hour-labels in left col only.
    parts = []
    parts.append('<div class="hour-label"></div>'.join([''] * 0))  # noop
    # Build: row 0 already has day headers. Now we need: 16 hour labels + 7 day columns.
    # CSS Grid auto-flow: hour-labels go in column 1, day-cols span column 2..8 each at row spanning all.
    # Simpler: use a separate inner layout. Refactor here:
    out_html = []
    # Hour labels stacked in column 1
    out_html.append('<div style="grid-column: 1; display: flex; flex-direction: column;">')
    for hour in range(GRID_START_HOUR, GRID_END_HOUR):
        out_html.append(f'<div class="hour-label">{hour:02d}:00</div>')
    out_html.append('</div>')
    # Day columns
    for wd in WEEKDAYS_ORDER:
        out_html.append(day_col_html(wd, shifts, profile_map, source))
    return ''.join(out_html)

def day_headers_html():
    dates = ["25 May", "26 May", "27 May", "28 May", "29 May", "30 May", "31 May"]
    out = []
    for i, wd in enumerate(WEEKDAYS_ORDER):
        weekend_cls = " weekend" if wd in (0, 6) else ""
        out.append(f'<div class="day-header{weekend_cls}">{DAY_NAMES[wd]}<span class="date">{dates[i]}</span></div>')
    return ''.join(out)

def summary_rows_html(profiles, sling_by, demo_by):
    rows = []
    # sort by demo hours desc, then sling hours desc, then name
    def sort_key(p):
        sid = p["sling_user_id"]
        return (-demo_by.get(sid, 0), -sling_by.get(sid, 0), p["name"])
    for p in sorted(profiles, key=sort_key):
        sid = p["sling_user_id"]
        sling_h = sling_by.get(sid, 0) / 60
        demo_h = demo_by.get(sid, 0) / 60
        delta = demo_h - sling_h
        if abs(delta) < 0.1:
            delta_cls = "delta-zero"
            delta_str = "—"
        elif delta > 0:
            delta_cls = "delta-pos"
            delta_str = f"+{delta:.1f}"
        else:
            delta_cls = "delta-neg"
            delta_str = f"{delta:.1f}"
        target = p.get("target_hours") or "—"
        max_h = p.get("max_hours") or "—"
        rows.append(
            f'<tr>'
            f'<td><span class="swatch" style="background:{p["color"]}"></span>{p["name"]}</td>'
            f'<td>{p["contract"]}</td>'
            f'<td class="num">{target} / {max_h}</td>'
            f'<td class="num">{sling_h:.1f}</td>'
            f'<td class="num">{demo_h:.1f}</td>'
            f'<td class="num {delta_cls}">{delta_str}</td>'
            f'</tr>'
        )
    return '\n'.join(rows)

def main():
    profiles, demo_raw, sling_raw = load()
    sling_shifts = normalize_sling(sling_raw)
    demo_shifts = normalize_demo(demo_raw)
    profile_map = {p["sling_user_id"]: p for p in profiles}

    sling_by = by_barista(sling_shifts)
    demo_by = by_barista(demo_shifts)
    sling_hours = sum(sling_by.values()) // 60
    demo_hours = sum(demo_by.values()) // 60

    html = HTML_TEMPLATE.format(
        week_start=WEEK_START,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        hour_px=HOUR_PX,
        grid_hours=GRID_END_HOUR - GRID_START_HOUR,
        day_headers=day_headers_html(),
        sling_grid=grid_html(sling_shifts, profile_map, "sling"),
        demo_grid=grid_html(demo_shifts, profile_map, "demo"),
        summary_rows=summary_rows_html(profiles, sling_by, demo_by),
        barista_count=len(profiles),
        sling_count=len(sling_shifts),
        demo_count=len(demo_shifts),
        sling_hours=sling_hours,
        demo_hours=demo_hours,
        hours_delta=demo_hours - sling_hours,
    )
    Path("index.html").write_text(html)
    print(f"wrote index.html ({len(html)} bytes)")

if __name__ == "__main__":
    main()
