"""Generate a synthetic WorkBuddy data directory for screenshots and manual tests.

The real ~/.workbuddy store contains session titles and usage that must never be
committed. This script builds an equivalent read-only fixture under demo-data/
so screenshots can be reproduced without leaking personal data.

Usage:
    python scripts/make_demo_data.py --days 30 --force
    python gui_app.py --root demo-data --offline --shot docs/images/dashboard.png
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CN_TZ = timezone(timedelta(hours=8))
MARKER = ".demo-data"

SESSIONS = [
    ("demo-001", "示例 · 竞品调研摘要", "deepseek-v4.1-flash", 1.0),
    ("demo-002", "示例 · 接口文档生成", "deepseek-v4.1-flash", 0.9),
    ("demo-003", "示例 · 单元测试补全", "deepseek-v4.1-flash", 0.8),
    ("demo-004", "示例 · 日志异常聚类", "deepseek-v4.1-flash", 0.7),
    ("demo-005", "示例 · 数据表清洗", "deepseek-v4-flash", 0.55),
    ("demo-006", "示例 · 发布说明整理", "deepseek-flash", 0.45),
    ("demo-007", "示例 · 会议纪要归档", "deepseek-v4.1-flash", 0.35),
    ("demo-008", "示例 · 旧版迁移评估", "deepseek-v4-pro", 0.25),
]


def prepare(out: Path, force: bool) -> None:
    if out.exists() and any(out.iterdir()):
        if not force and not (out / MARKER).exists():
            raise SystemExit(f"{out} is not empty and is not a demo-data directory; "
                             "pass --force to overwrite it.")
        shutil.rmtree(out)
    (out / "projects" / "demo-project").mkdir(parents=True, exist_ok=True)
    (out / "sessions").mkdir(exist_ok=True)
    (out / MARKER).write_text("synthetic fixture\n", encoding="utf-8")


def build(out: Path, days: int, seed: int) -> None:
    rnd = random.Random(seed)
    today = datetime.now(CN_TZ).date()
    start = today - timedelta(days=days - 1)

    con = sqlite3.connect(out / "workbuddy.db")
    con.execute(
        "create table sessions "
        "(id text primary key, title text, custom_title text, model text, "
        " status text, created_at text, updated_at text)"
    )

    for sid, title, model, weight in SESSIONS:
        records = [{"type": "ai-title", "content": title}]
        for offset in range(days):
            day = start + timedelta(days=offset)
            day_weight = weight * (0.55 if day.weekday() >= 5 else 1.0)
            if rnd.random() > day_weight:
                continue
            for _ in range(rnd.randint(4, 26)):
                hour = rnd.choice([9, 10, 11, 14, 15, 16, 17, 20, 21, 22])
                moment = datetime(day.year, day.month, day.day, hour,
                                  rnd.randrange(60), rnd.randrange(60), tzinfo=CN_TZ)
                prompt = rnd.randint(18_000, 140_000)
                hit_ratio = rnd.uniform(0.94, 0.995)
                hit = int(prompt * hit_ratio)
                mid = f"{sid}-{moment.timestamp():.0f}-{rnd.randrange(100000)}"
                records.append({
                    "timestamp": int(moment.timestamp() * 1000),
                    "id": mid,
                    "providerData": {
                        "model": model,
                        "messageId": mid,
                        "rawUsage": {
                            "prompt_tokens": prompt,
                            "prompt_cache_hit_tokens": hit,
                            "prompt_cache_miss_tokens": prompt - hit,
                            "completion_tokens": rnd.randint(600, 9_000),
                        },
                    },
                })
        path = out / "projects" / "demo-project" / f"{sid}.jsonl"
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
            encoding="utf-8",
        )
        con.execute("insert into sessions values (?,?,?,?,?,?,?)",
                    (sid, title, "", model, "idle", "", ""))

    con.commit()
    con.close()

    # Mark one session as the "current" interactive window; the GUI can exclude it.
    (out / "sessions" / "current.json").write_text(
        json.dumps({"kind": "interactive", "sessionId": "demo-001"}), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic demo data")
    parser.add_argument("--out", default=str(ROOT / "demo-data"))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261125)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    if args.days < 1 or args.days > 365:
        raise SystemExit("--days must be between 1 and 365")

    prepare(out, args.force)
    build(out, args.days, args.seed)
    print(f"demo data written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
