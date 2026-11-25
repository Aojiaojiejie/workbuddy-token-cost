from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from types import SimpleNamespace

import pytest

import token_cost as core

CN = core.CN_TZ


def ts(year: int, month: int, day: int, hour: int, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=CN).timestamp() * 1000)


def usage(ts_ms: int, mid: str, model: str = "deepseek-v4.1-flash",
          prompt: int = 1000, hit: int = 800, out: int = 100) -> dict:
    return {
        "timestamp": ts_ms,
        "id": mid,
        "providerData": {
            "model": model,
            "messageId": mid,
            "rawUsage": {
                "prompt_tokens": prompt,
                "prompt_cache_hit_tokens": hit,
                "prompt_cache_miss_tokens": prompt - hit,
                "completion_tokens": out,
            },
        },
    }


def write_session(root, sid: str, records: list[dict], project: str = "proj"):
    folder = root / "projects" / project
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sid}.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


def make_args(**over):
    base = dict(title="", include_pro=False, all_models=False, peak="auto",
                exclude_current=False, top=0, list=False, csv="", json="",
                offline=True, price_refresh=0, watch=0.0, count=0)
    base.update(over)
    return SimpleNamespace(**base)


def make_ctx(tmp_path, args=None, **over) -> core.Context:
    root = tmp_path / ".workbuddy"
    (root / "projects").mkdir(parents=True, exist_ok=True)
    ctx = core.Context(
        args=args or make_args(), root=root,
        prices=dict(core.FALLBACK_PRICES), price_source="test", price_time=0.0,
        meta={}, meta_note=None, active_ids=set(), excluded_active=set(),
        since=None, until=None, holidays=set(),
    )
    for key, value in over.items():
        setattr(ctx, key, value)
    return ctx


# ---------------------------------------------------------------- parsing
def test_parse_record_raw_usage():
    rec = core.parse_record(usage(0, "m1"))
    assert rec == {"prompt": 1000, "hit": 800, "miss": 200, "output": 100,
                   "model": "deepseek-v4.1-flash", "message_id": "m1"}


def test_parse_record_cached_tokens_fallback():
    record = {
        "providerData": {
            "model": "deepseek-flash",
            "messageId": "m2",
            "rawUsage": {
                "prompt_tokens": 1000,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 0,
                "prompt_tokens_details": {"cached_tokens": 600},
                "completion_tokens": 20,
            },
        }
    }
    rec = core.parse_record(record)
    assert (rec["hit"], rec["miss"]) == (600, 400)


def test_parse_record_message_usage():
    record = {
        "message": {"usage": {"input_tokens": 500,
                              "cache_read_input_tokens": 100,
                              "output_tokens": 50}},
        "providerData": {"model": "glm-4.6", "messageId": "m3"},
    }
    rec = core.parse_record(record)
    assert rec == {"prompt": 500, "hit": 100, "miss": 400, "output": 50,
                   "model": "glm-4.6", "message_id": "m3"}


def test_parse_record_without_usage_returns_none():
    assert core.parse_record({"type": "ai-title", "content": "x"}) is None


# ---------------------------------------------------------------- peak logic
@pytest.mark.parametrize("moment,expected", [
    ((2026, 11, 11, 8, 59), False),
    ((2026, 11, 11, 9, 0), True),
    ((2026, 11, 11, 11, 59), True),
    ((2026, 11, 11, 12, 0), False),
    ((2026, 11, 11, 13, 59), False),
    ((2026, 11, 11, 14, 0), True),
    ((2026, 11, 11, 17, 59), True),
    ((2026, 11, 11, 18, 0), False),
    ((2026, 11, 14, 10, 0), False),   # Saturday
])
def test_is_peak_boundaries(moment, expected):
    assert core.is_peak(ts(*moment), set()) is expected


def test_is_peak_holiday_override():
    holiday = ts(2026, 11, 11, 10, 0)
    assert core.is_peak(holiday, set()) is True
    assert core.is_peak(holiday, {"2026-11-11"}) is False


# ---------------------------------------------------------------- collection
def test_collect_aggregates_and_deduplicates(tmp_path):
    ctx = make_ctx(tmp_path)
    root = ctx.root
    write_session(root, "s1", [
        {"type": "ai-title", "content": "Demo Peak"},
        usage(ts(2026, 11, 11, 10), "m1"),
        usage(ts(2026, 11, 11, 10), "m1"),              # duplicate message id
        usage(ts(2026, 11, 11, 20), "m2", prompt=2000, hit=1500, out=300),
    ])
    ctx.meta, _ = core.load_session_meta(root / "workbuddy.db")

    snap = core.collect(ctx)

    assert len(snap.rows) == 1
    row = snap.rows[0]
    assert row["title"] == "Demo Peak"
    assert row["requests"] == 2
    assert row["prompt"] == 3000
    assert row["hit"] == 2300
    assert row["miss"] == 700
    assert row["output"] == 400
    assert row["total"] == 3400
    assert row["peak_requests"] == 1
    assert row["offpeak_requests"] == 1
    assert row["cost"] == pytest.approx(0.002962, rel=1e-9)
    assert snap.total["cost"] == pytest.approx(0.002962, rel=1e-9)
    assert snap.hit_rate == pytest.approx(2300 / 3000 * 100)
    assert snap.daily_total["2026-11-11"]["requests"] == 2
    assert snap.daily_total["2026-11-11"]["cost"] == pytest.approx(0.002962, rel=1e-9)


def test_collect_uses_sessions_table_title(tmp_path):
    ctx = make_ctx(tmp_path)
    root = ctx.root
    write_session(root, "s2", [usage(ts(2026, 11, 11, 10), "m1")])
    con = sqlite3.connect(root / "workbuddy.db")
    con.execute(
        "create table sessions (id,title,custom_title,model,status,created_at,updated_at)"
    )
    con.execute("insert into sessions values (?,?,?,?,?,?,?)",
                ("s2", "raw title", "Custom Title", "deepseek-v4.1-flash", "active", "", ""))
    con.commit()
    con.close()

    ctx.meta, note = core.load_session_meta(root / "workbuddy.db")
    snap = core.collect(ctx)
    assert note is None
    assert snap.rows[0]["title"] == "Custom Title"


def test_collect_excludes_non_flash_models(tmp_path):
    ctx = make_ctx(tmp_path)
    write_session(ctx.root, "s3", [
        usage(ts(2026, 11, 11, 10), "m1", model="deepseek-v4.1-flash"),
        usage(ts(2026, 11, 11, 10), "m2", model="glm-4.6"),
    ])
    snap = core.collect(ctx)
    assert snap.total["requests"] == 1
    assert snap.excluded["s3"]["glm-4.6"]["requests"] == 1

    ctx.args.all_models = True
    snap_all = core.collect(ctx)
    assert snap_all.total["requests"] == 2


def test_excluded_active_session_is_skipped(tmp_path):
    ctx = make_ctx(tmp_path)
    write_session(ctx.root, "s4", [usage(ts(2026, 11, 11, 10), "m1")])
    ctx.excluded_active = {"s4"}
    assert core.collect(ctx).rows == []


def test_load_active_ids(tmp_path):
    sessions = tmp_path / ".workbuddy" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "a.json").write_text(
        json.dumps({"kind": "interactive", "sessionId": "s1"}), encoding="utf-8")
    (sessions / "b.json").write_text(
        json.dumps({"kind": "background", "sessionId": "s2"}), encoding="utf-8")
    (sessions / "bad.json").write_text("{not json", encoding="utf-8")
    assert core.load_active_ids(sessions) == {"s1"}


# ---------------------------------------------------------------- reporting
def test_build_report_and_export(tmp_path):
    ctx = make_ctx(tmp_path)
    write_session(ctx.root, "s5", [
        {"type": "ai-title", "content": "Export Demo"},
        usage(ts(2026, 11, 11, 10), "m1"),
    ])
    snap = core.collect(ctx)

    report = core.build_report(ctx, snap)
    assert "Export Demo" in report
    assert "合计" in report
    assert "0.0012" in report

    ctx.args.csv = str(tmp_path / "out.csv")
    ctx.args.json = str(tmp_path / "out.json")
    core.export_files(ctx, snap, quiet=True)

    csv_text = (tmp_path / "out.csv").read_text(encoding="utf-8-sig")
    assert csv_text.splitlines()[0].startswith("session_id,title,status,model")
    assert "Export Demo" in csv_text

    payload = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert payload["version"] == core.VERSION
    assert payload["sessions"][0]["sid"] == "s5"
    assert payload["daily"]["2026-11-11"]["requests"] == 1


def test_build_parser_defaults():
    args = core.build_parser().parse_args([])
    assert args.root.endswith(".workbuddy")
    assert args.peak == "auto"
    assert args.top == 20
    assert args.once is False
