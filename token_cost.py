#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 会话 Token 用量统计与费用换算工具。

数据源（只读，不写入任何 WorkBuddy 文件）:
  ~/.workbuddy/projects/*/*.jsonl   逐请求 providerData.rawUsage
  ~/.workbuddy/workbuddy.db        sessions 表（标题 / 模型 / 状态）
  ~/.workbuddy/sessions/*.json     当前活跃窗口 ID（可用 --exclude-current 排除）

定价源: DeepSeek 官方定价页，联网校验；失败时回落内置价格表。
价格单位: 人民币元 / 百万 tokens，顺序为 (缓存命中输入, 缓存未命中输入, 输出)。

运行模式:
  默认（双击 exe）        持续实时刷新：每 3 秒重扫一次，控制台原地重绘，Ctrl+C 退出
  --watch [秒]            同上，但可自定义刷新间隔
  --once                  只扫描一次，输出报告后退出（供脚本/管道使用）
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VERSION = "5.0.1"
PRICING_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing"
CN_TZ = timezone(timedelta(hours=8))
# 定价页正常约 100 KB；上限用于挡住异常或恶意超大响应，避免一次性读入内存
MAX_PRICING_BYTES = 4 * 1024 * 1024
USER_AGENT = f"Mozilla/5.0 (compatible; WorkBuddyTokenCost/{VERSION})"

# 内置兜底价（元/百万 tokens，快照 2026-09-10）：(缓存命中输入, 未命中输入, 输出)
FALLBACK_PRICES = {"offpeak": (0.02, 1.0, 4.0), "peak": (0.04, 2.0, 8.0)}

# 官网模型名 deepseek-flash 在本机日志中的等价标识；
# deepseek-v4-flash / -vision-exp 按官网脚注路由至 Flash 并按 Flash 价格计费。
FLASH_MODELS = {
    "deepseek-flash",
    "deepseek-v4.1-flash",
    "deepseek-v4-flash",
    "deepseek-v4-flash-vision-exp",
}
# 官网说明 2026-09-14 后 v4-pro 请求路由至 Flash 并按 Flash 价计费；默认仍单独排除。
ROUTED_PRO_MODELS = {"deepseek-v4-pro"}


def setup_console() -> None:
    """保证 Windows 控制台能正确显示中文。"""
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def enable_vt_mode() -> bool:
    """启用 Windows 控制台的 ANSI 转义序列，用于原地重绘。"""
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        handle = k.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = wintypes.DWORD()
        if not k.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def fetch_prices(timeout: float = 6.0):
    """从官网定价页解析 deepseek-flash 的 6 个单价；解析或校验失败则抛异常。

    响应先做状态码、Content-Type 与大小上限校验，再交给正则解析；
    任何异常都由调用方回落到 FALLBACK_PRICES。
    """
    req = urllib.request.Request(PRICING_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", 200)
        if status != 200:
            raise ValueError(f"定价页返回 HTTP {status}")
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype and ctype not in ("text/html", "text/plain"):
            raise ValueError(f"定价页返回了非文本内容: {ctype}")
        raw = resp.read(MAX_PRICING_BYTES + 1)
    if len(raw) > MAX_PRICING_BYTES:
        raise ValueError("定价页超过 4 MiB 上限，已中止解析")
    html = raw.decode("utf-8", "replace")
    start = html.find('rowspan="6">价格')
    segment = html[start:] if start >= 0 else html
    rows = re.findall(
        r"<td>(空闲|高峰)时段</td><td>([\d.]+)元</td><td>([\d.]+)元</td>", segment
    )
    labels = [r[0] for r in rows[:6]]
    values = [float(r[1]) for r in rows[:6]]
    if labels != ["空闲", "高峰", "空闲", "高峰", "空闲", "高峰"]:
        raise ValueError("定价表结构已变化，未解析到预期的 6 行")
    prices = {
        "offpeak": (values[0], values[2], values[4]),
        "peak": (values[1], values[3], values[5]),
    }
    for k in ("offpeak", "peak"):
        if min(prices[k]) <= 0 or not (prices[k][0] < prices[k][1] < prices[k][2]):
            raise ValueError("解析到的价格数值不合理")
    for a, b in zip(prices["offpeak"], prices["peak"]):
        if abs(a * 2 - b) > 1e-9:
            raise ValueError("闲时/高峰价格不满足 1:2 关系")
    return prices


def load_session_meta(db_path: Path) -> tuple[dict, str | None]:
    meta: dict[str, dict] = {}
    note = None
    # as_uri() 只接受绝对路径；--root 允许相对路径，这里先归一化
    db_path = db_path.expanduser().resolve()
    if not db_path.exists():
        return meta, "未找到 workbuddy.db，会话标题改用 jsonl 内的 ai-title 记录"
    try:
        con = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=3)
        for row in con.execute(
            "select id,title,custom_title,model,status,created_at,updated_at from sessions"
        ):
            sid, title, custom, model, status, created, updated = row
            meta[sid] = {
                "title": custom or title or "",
                "model": model or "",
                "status": status or "",
                "created": created,
                "updated": updated,
            }
        con.close()
    except Exception as exc:
        note = f"读取 workbuddy.db 失败（{type(exc).__name__}: {exc}），标题改用 jsonl"
    return meta, note


def load_active_ids(active_dir: Path) -> set[str]:
    ids: set[str] = set()
    for p in active_dir.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if d.get("kind") == "interactive" and d.get("sessionId"):
            ids.add(d["sessionId"])
    return ids


def parse_record(d: dict):
    """把一条 jsonl 记录规整为用量字典；无用量返回 None。"""
    pd = d.get("providerData") or {}
    ru = pd.get("rawUsage")
    model = pd.get("model") or ""
    if isinstance(ru, dict) and "prompt_tokens" in ru:
        p = int(ru.get("prompt_tokens") or 0)
        h = int(ru.get("prompt_cache_hit_tokens") or 0)
        m = int(ru.get("prompt_cache_miss_tokens") or 0)
        if h + m != p:
            details = ru.get("prompt_tokens_details") or {}
            if details.get("cached_tokens") is not None:
                h = int(details["cached_tokens"])
                m = p - h
            else:
                m = p - h
        o = int(ru.get("completion_tokens") or 0)
        quota = ru.get("quota") or {}
        model = model or (quota.get("model") if isinstance(quota, dict) else "") or ""
        return {
            "prompt": p, "hit": h, "miss": m, "output": o,
            "model": str(model),
            "message_id": pd.get("messageId") or d.get("id"),
        }
    msg = d.get("message") or {}
    u = msg.get("usage") if isinstance(msg, dict) else None
    if isinstance(u, dict) and "input_tokens" in u:
        p = int(u.get("input_tokens") or 0)
        h = int(u.get("cache_read_input_tokens") or 0)
        o = int(u.get("output_tokens") or 0)
        return {
            "prompt": p, "hit": h, "miss": p - h, "output": o,
            "model": str(model),
            "message_id": pd.get("messageId") or d.get("id"),
        }
    return None


def is_peak(ts_ms, holidays: set[str]) -> bool:
    """北京时间：工作日 9:00-12:00 / 14:00-18:00 为高峰；周末与指定节假日为闲时。"""
    if not isinstance(ts_ms, int):
        return False
    dt = datetime.fromtimestamp(ts_ms / 1000, CN_TZ)
    if dt.weekday() >= 5 or dt.date().isoformat() in holidays:
        return False
    return (9 <= dt.hour < 12) or (14 <= dt.hour < 18)


def fmt_num(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def disp_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def pad(s: str, width: int) -> str:
    return s + " " * max(0, width - disp_width(s))


def clip(s: str, width: int) -> str:
    out, w = "", 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
        if w + cw > width:
            return out + "…" if disp_width(out) + 1 <= width else out
        out += c
        w += cw
    return out


def new_stat(sid: str) -> dict:
    return {
        "sid": sid, "title": "", "status": "", "models": Counter(),
        "requests": 0, "prompt": 0, "hit": 0, "miss": 0, "output": 0,
        "total": 0, "cost": 0.0, "peak_requests": 0, "offpeak_requests": 0,
        "first_ts": None, "last_ts": None,
    }


@dataclass
class Snapshot:
    rows: list[dict] = field(default_factory=list)
    total: dict = field(default_factory=dict)
    excluded: dict = field(default_factory=dict)
    files: int = 0
    usage_records: int = 0
    read_errors: int = 0
    elapsed: float = 0.0
    scanned_at: float = 0.0
    hit_rate: float = 0.0
    # 按北京日期聚合：日期字符串 -> {requests, prompt, hit, miss, output, total, cost, peak, offpeak}
    daily_total: dict = field(default_factory=dict)
    daily_by_session: dict = field(default_factory=dict)
    # 当天按小时聚合：小时(0-23) -> 同上结构，供"今天"分时柱状图使用
    today: str = ""
    hourly_total: dict = field(default_factory=dict)
    hourly_by_session: dict = field(default_factory=dict)


@dataclass
class Context:
    args: object
    root: Path
    prices: dict
    price_source: str
    price_time: float
    meta: dict
    meta_note: str | None
    active_ids: set[str]
    excluded_active: set[str]
    since: date | None
    until: date | None
    holidays: set[str]


def new_daily() -> dict:
    """按日期/小时聚合的桶。"""
    return {"requests": 0, "prompt": 0, "hit": 0, "miss": 0, "output": 0,
            "total": 0, "cost": 0.0, "peak": 0, "offpeak": 0}


def bucket_add(bucket: dict, rec: dict, cost: float, peak: bool) -> None:
    bucket["requests"] += 1
    bucket["prompt"] += rec["prompt"]
    bucket["hit"] += rec["hit"]
    bucket["miss"] += rec["miss"]
    bucket["output"] += rec["output"]
    bucket["total"] += rec["prompt"] + rec["output"]
    bucket["cost"] += cost
    if peak:
        bucket["peak"] += 1
    else:
        bucket["offpeak"] += 1


def collect(ctx: Context) -> Snapshot:
    """扫描全部会话并返回一次快照；可反复调用。"""
    args = ctx.args
    started = time.perf_counter()
    stats: dict[str, dict] = {}
    excluded: dict[str, dict] = {}
    files = sorted((ctx.root / "projects").glob("*/*.jsonl"))
    read_errors = 0
    usage_records = 0
    daily_total: dict[str, dict] = {}
    daily_by_session: dict[str, dict] = {}
    hourly_total: dict[int, dict] = {}
    hourly_by_session: dict[str, dict] = {}
    today = datetime.now(CN_TZ).date().isoformat()

    for path in files:
        sid = path.stem
        if sid in ctx.excluded_active:
            continue
        title = ctx.meta.get(sid, {}).get("title", "") or path.parent.name
        if args.title and ctx.meta.get(sid, {}).get("title") and args.title not in title:
            continue
        st = new_stat(sid)
        st["title"] = title
        st["status"] = ctx.meta.get(sid, {}).get("status", "")
        seen_ids: set[str] = set()
        try:
            fh = path.open(encoding="utf-8", errors="replace")
        except OSError:
            read_errors += 1
            continue
        with fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if not title or title == path.parent.name:
                    if d.get("type") == "ai-title":
                        t = d.get("content") or d.get("title") or ""
                        if isinstance(t, str) and t.strip():
                            title = st["title"] = t.strip()
                rec = parse_record(d)
                if rec is None:
                    continue
                usage_records += 1
                mid = rec["message_id"]
                if mid and mid in seen_ids:
                    continue
                if mid:
                    seen_ids.add(mid)
                ts = d.get("timestamp")
                hour = None
                if isinstance(ts, int):
                    dt = datetime.fromtimestamp(ts / 1000, CN_TZ)
                    day = dt.date().isoformat()
                    hour = dt.hour
                else:
                    day = None
                if ctx.since or ctx.until:
                    if day is None:
                        continue
                    d0 = date.fromisoformat(day)
                    if ctx.since and d0 < ctx.since:
                        continue
                    if ctx.until and d0 > ctx.until:
                        continue
                model = rec["model"].lower()
                allowed = model in FLASH_MODELS or (
                    args.include_pro and model in ROUTED_PRO_MODELS
                ) or args.all_models
                if not allowed:
                    bucket = excluded.setdefault(sid, {}).setdefault(
                        rec["model"] or "unknown", Counter()
                    )
                    bucket["requests"] += 1
                    bucket["tokens"] += rec["prompt"] + rec["output"]
                    continue
                if args.peak == "all":
                    rate, peak = ctx.prices["peak"], True
                elif args.peak == "off":
                    rate, peak = ctx.prices["offpeak"], False
                else:
                    peak = is_peak(ts, ctx.holidays)
                    rate = ctx.prices["peak"] if peak else ctx.prices["offpeak"]
                cost = (
                    rec["hit"] / 1e6 * rate[0]
                    + rec["miss"] / 1e6 * rate[1]
                    + rec["output"] / 1e6 * rate[2]
                )
                st["requests"] += 1
                st["models"][rec["model"] or "unknown"] += 1
                st["prompt"] += rec["prompt"]
                st["hit"] += rec["hit"]
                st["miss"] += rec["miss"]
                st["output"] += rec["output"]
                st["total"] += rec["prompt"] + rec["output"]
                st["cost"] += cost
                st["peak_requests" if peak else "offpeak_requests"] += 1
                if day:
                    bucket_add(daily_total.setdefault(day, new_daily()),
                               rec, cost, peak)
                    bucket_add(daily_by_session.setdefault(sid, {}).setdefault(
                        day, new_daily()), rec, cost, peak)
                    if day == today and hour is not None:
                        bucket_add(hourly_total.setdefault(hour, new_daily()),
                                   rec, cost, peak)
                        bucket_add(hourly_by_session.setdefault(sid, {}).setdefault(
                            hour, new_daily()), rec, cost, peak)
                if isinstance(ts, int):
                    st["first_ts"] = ts if st["first_ts"] is None else min(st["first_ts"], ts)
                    st["last_ts"] = ts if st["last_ts"] is None else max(st["last_ts"], ts)
        if args.title and args.title not in st["title"]:
            excluded.pop(sid, None)
            continue
        if st["requests"]:
            stats[sid] = st

    rows = sorted(stats.values(), key=lambda s: s["cost"], reverse=True)
    total = new_stat("TOTAL")
    for s in rows:
        for k in ("requests", "prompt", "hit", "miss", "output", "total",
                  "cost", "peak_requests", "offpeak_requests"):
            total[k] += s[k]
    hit_rate = 100 * total["hit"] / total["prompt"] if total["prompt"] else 0.0
    return Snapshot(
        rows=rows, total=total, excluded=excluded, files=len(files),
        usage_records=usage_records, read_errors=read_errors,
        elapsed=time.perf_counter() - started,
        scanned_at=time.time(), hit_rate=hit_rate,
        daily_total=daily_total, daily_by_session=daily_by_session,
        today=today, hourly_total=hourly_total, hourly_by_session=hourly_by_session,
    )


def compute_delta(prev: Snapshot, cur: Snapshot) -> dict:
    """两次快照之间的增量，含变化最明显的会话。"""
    a, b = prev.total, cur.total
    prev_map = {s["sid"]: s for s in prev.rows}
    changed = []
    for s in cur.rows:
        old = prev_map.get(s["sid"])
        d_tokens = s["total"] - (old["total"] if old else 0)
        d_cost = s["cost"] - (old["cost"] if old else 0.0)
        if d_tokens > 0 or d_cost > 0:
            changed.append((s["title"], d_tokens, d_cost))
    changed.sort(key=lambda x: -x[1])
    return {
        "requests": b["requests"] - a["requests"],
        "tokens": b["total"] - a["total"],
        "cost": b["cost"] - a["cost"],
        "changed": changed[:3],
    }


def build_report(ctx: Context, snap: Snapshot, delta: dict | None = None,
                 watch: dict | None = None) -> str:
    args = ctx.args
    total, rows = snap.total, snap.rows
    lines = ["=" * 96,
             f" WorkBuddy Token 费用统计  v{VERSION}" + ("   [实时刷新]" if watch else ""),
             "=" * 96,
             f" 数据目录 : {ctx.root}",
             f" 会话文件 : {snap.files} 个 jsonl / {snap.usage_records:,} 条用量记录，"
             f"纳入计费 {len(rows)} 个会话 / {total['requests']:,} 次请求",
             " 计价模型 : " + (
                 "全部模型（非 Flash 按 Flash 价估算）" if args.all_models
                 else "deepseek-flash 系列" + (" + deepseek-v4-pro" if args.include_pro else "")
             ),
             f" 价格来源 : {ctx.price_source}  |  时段模式: {args.peak}"]
    p_off, p_pk = ctx.prices["offpeak"], ctx.prices["peak"]
    lines.append(
        f" 官网单价 : 元/百万 tokens  命中 {p_off[0]:g}/{p_pk[0]:g}  "
        f"未命中 {p_off[1]:g}/{p_pk[1]:g}  输出 {p_off[2]:g}/{p_pk[2]:g}（闲时/高峰）"
    )
    if ctx.meta_note:
        lines.append(f" 提示     : {ctx.meta_note}")
    if args.exclude_current and ctx.active_ids:
        lines.append(f" 已排除   : {len(ctx.active_ids)} 个当前活跃窗口")
    elif ctx.active_ids:
        lines.append(f" 活跃窗口 : {len(ctx.active_ids)} 个已纳入统计（--exclude-current 可排除）")
    if args.peak == "auto" and not ctx.holidays:
        lines.append(" 提示     : 法定节假日未指定，按普通工作日处理；可用 --holidays 补充日期")
    lines.append("-" * 96)

    if args.list:
        for i, s in enumerate(rows, 1):
            lines.append(
                f" {i:>3}. {s['title']}  [{s['models'].most_common(1)[0][0]}]  {s['requests']} 次请求"
            )
    else:
        lines.append(
            f" {'#':>3}  {pad('会话标题', 28)}  {pad('请求', 7)}{pad('输入', 11)}"
            f"{pad('命中率', 10)}{pad('输出', 10)}{pad('总Token', 12)}{'费用(元)':>10}"
        )
        lines.append("-" * 96)
        shown = rows if args.top == 0 else rows[: args.top]
        for i, s in enumerate(shown, 1):
            r = 100 * s["hit"] / s["prompt"] if s["prompt"] else 0.0
            lines.append(
                f" {i:>3}  {pad(clip(s['title'], 28), 28)}  "
                f"{pad(str(s['requests']), 7)}"
                f"{pad(fmt_num(s['prompt']), 11)}"
                f"{pad(f'{r:.2f}%', 10)}"
                f"{pad(fmt_num(s['output']), 10)}"
                f"{pad(fmt_num(s['total']), 12)}"
                f"{s['cost']:>10.4f}"
            )
        if args.top > 0 and len(rows) > args.top:
            lines.append(f"      ... 另有 {len(rows) - args.top} 个会话未显示（--top 0 查看全部）")
        lines.append("-" * 96)
        lines.append(
            f" 合计     : 输入 {total['prompt']:,}（命中 {total['hit']:,} / 未命中 {total['miss']:,}）"
            f"  输出 {total['output']:,}  总计 {total['total']:,} tokens"
        )
        lines.append(f" 整体缓存命中率 : {snap.hit_rate:.4f}%")
        lines.append(f" 峰/闲请求数   : {total['peak_requests']} / {total['offpeak_requests']}")
        lines.append(f" 折算费用合计 : {total['cost']:.4f} 元"
                     + ("（含非 Flash 模型估算）" if args.all_models else ""))
        agg: dict[str, dict] = {}
        for models in snap.excluded.values():
            for model, c in models.items():
                a = agg.setdefault(model, {"requests": 0, "tokens": 0})
                a["requests"] += c["requests"]
                a["tokens"] += c["tokens"]
        if agg:
            parts = ", ".join(
                f"{k}: {v['requests']}次/{v['tokens']:,}tokens"
                for k, v in sorted(agg.items(), key=lambda x: -x[1]["tokens"])
            )
            lines.append(f" 已排除模型   : {parts}")
    if snap.read_errors:
        lines.append(f" 警告     : {snap.read_errors} 个文件无法读取")

    if watch:
        ts = datetime.fromtimestamp(snap.scanned_at, CN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        lines.append("-" * 96)
        lines.append(
            f" 实时模式  : 每 {watch['interval']:g}s 刷新 | 第 {watch['round']} 次 | "
            f"{ts} | 扫描 {snap.elapsed:.2f}s | 价格更新于 "
            f"{datetime.fromtimestamp(ctx.price_time, CN_TZ).strftime('%H:%M:%S')} | Ctrl+C 退出"
        )
        if delta is None:
            lines.append(" 本次增量  : 首次快照，从下一次刷新开始计算增量")
        else:
            lines.append(
                f" 本次增量  : {'+' if delta['requests'] >= 0 else ''}{delta['requests']} 次请求 / "
                f"{'+' if delta['tokens'] >= 0 else ''}{delta['tokens']:,} tokens / "
                f"{'+' if delta['cost'] >= 0 else ''}{delta['cost']:.4f} 元"
            )
            for title, d_tokens, d_cost in delta["changed"]:
                lines.append(f"    · {clip(title, 30)}  +{d_tokens:,} tokens  +{d_cost:.4f} 元")
            if not delta["changed"]:
                lines.append("    · 无变化")
        if watch.get("exports"):
            lines.append(f" 导出同步  : {watch['exports']}")
    lines.append("=" * 96)
    return "\n".join(lines) + "\n"


def export_files(ctx: Context, snap: Snapshot, quiet: bool = False) -> list[str]:
    args = ctx.args
    msgs: list[str] = []
    rows, total = snap.rows, snap.total
    if args.csv:
        try:
            with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["session_id", "title", "status", "model", "requests",
                            "prompt_tokens", "cache_hit_tokens", "cache_miss_tokens",
                            "output_tokens", "total_tokens", "hit_rate_pct",
                            "peak_requests", "offpeak_requests", "cost_cny"])
                for s in rows:
                    w.writerow([s["sid"], s["title"], s["status"],
                                ",".join(m for m, _ in s["models"].most_common()),
                                s["requests"], s["prompt"], s["hit"], s["miss"],
                                s["output"], s["total"],
                                f"{100 * s['hit'] / s['prompt']:.4f}" if s["prompt"] else "",
                                s["peak_requests"], s["offpeak_requests"],
                                f"{s['cost']:.6f}"])
            msgs.append(f"CSV -> {Path(args.csv).resolve()}")
        except OSError as exc:
            msgs.append(f"[错误] CSV 导出失败: {exc}")
    if args.json:
        payload = {
            "version": VERSION, "root": str(ctx.root), "price_source": ctx.price_source,
            "prices_cny_per_million": ctx.prices, "peak_mode": args.peak,
            "model_scope": "all" if args.all_models else "deepseek-flash",
            "scanned_at": snap.scanned_at,
            "total": {k: v for k, v in total.items() if k not in ("title", "models", "sid")},
            "total_hit_rate_pct": round(snap.hit_rate, 4),
            "daily": snap.daily_total,
            "today": snap.today,
            "hourly_today": snap.hourly_total,
            "sessions": [
                {**{k: v for k, v in s.items() if k != "models"},
                 "models": dict(s["models"])}
                for s in rows
            ],
        }
        try:
            Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
            msgs.append(f"JSON -> {Path(args.json).resolve()}")
        except OSError as exc:
            msgs.append(f"[错误] JSON 导出失败: {exc}")
    if not quiet:
        for m in msgs:
            print(m)
    return msgs


def watch_loop(ctx: Context, interval: float, pause_on_exit: bool = False) -> int:
    """持续重扫、原地重绘，并显示相邻两次快照之间的增量。"""
    vt = enable_vt_mode()
    prev: Snapshot | None = None
    round_no = 0
    exports = ", ".join(p for p in (ctx.args.csv, ctx.args.json) if p)
    try:
        while True:
            # 价格按间隔重新拉取，避免每轮都请求官网
            if (not ctx.args.offline and ctx.args.price_refresh > 0
                    and time.time() - ctx.price_time >= ctx.args.price_refresh):
                try:
                    ctx.prices = fetch_prices()
                    ctx.price_source = "官网实时价格"
                    ctx.price_time = time.time()
                except Exception:
                    pass
            snap = collect(ctx)
            delta = compute_delta(prev, snap) if prev else None
            round_no += 1
            report = build_report(ctx, snap, delta=delta,
                                  watch={"interval": interval, "round": round_no,
                                         "exports": exports})
            export_files(ctx, snap, quiet=True)
            if vt:
                sys.stdout.write("\033[H\033[J")
            else:
                os.system("cls")
            sys.stdout.write(report)
            sys.stdout.flush()
            prev = snap
            if ctx.args.count and round_no >= ctx.args.count:
                print(f"\n已完成 {round_no} 次重扫，退出实时模式。")
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n实时刷新已停止。")
    if pause_on_exit and not ctx.args.no_pause:
        try:
            input("按回车键退出...")
        except (EOFError, KeyboardInterrupt):
            pass
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="统计 WorkBuddy 各窗口会话的 token 用量，并按 deepseek-flash 官网价格换算费用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  WorkBuddyTokenCost.exe                          默认：每 3 秒重扫，实时刷新（Ctrl+C 退出）\n"
            "  WorkBuddyTokenCost.exe --watch 1                 每秒重扫一次\n"
            "  WorkBuddyTokenCost.exe --once                    只扫描一次后退出（脚本/管道用）\n"
            "  WorkBuddyTokenCost.exe --watch --title 交接       实时盯指定窗口\n"
            "  WorkBuddyTokenCost.exe --watch --csv live.csv     每轮同步导出 CSV\n"
            "  WorkBuddyTokenCost.exe --watch 2 --count 5        重扫 5 次后自动退出\n"
            "  WorkBuddyTokenCost.exe --once --title 交接 --peak all   一次性，全部按高峰价\n"
            "  WorkBuddyTokenCost.exe --once --offline --no-pause --top 0\n"
        ),
    )
    ap.add_argument("--root", default=str(Path.home() / ".workbuddy"),
                    help="WorkBuddy 数据根目录，默认 ~/.workbuddy")
    ap.add_argument("--title", default="", help="只统计标题包含该关键词的会话")
    ap.add_argument("--all-models", action="store_true",
                    help="纳入所有模型的会话（仍按 deepseek-flash 价格估算，结果标注为估算）")
    ap.add_argument("--include-pro", action="store_true",
                    help="纳入 deepseek-v4-pro（官网说明其已路由至 Flash 并按 Flash 价计费）")
    ap.add_argument("--exclude-current", action="store_true",
                    help="排除当前活跃窗口；默认统计全部窗口（含活跃窗口）")
    ap.add_argument("--peak", choices=("auto", "all", "off"), default="auto",
                    help="auto=按请求时间戳判峰谷（默认）；all=全按高峰；off=全按闲时")
    ap.add_argument("--since", default="", help="只统计该日期(YYYY-MM-DD)起的请求")
    ap.add_argument("--until", default="", help="只统计该日期(YYYY-MM-DD)止的请求")
    ap.add_argument("--holidays", default="",
                    help="逗号分隔的法定节假日 YYYY-MM-DD，这些日期按闲时计价")
    ap.add_argument("--offline", action="store_true", help="不联网，直接使用内置价格表")
    ap.add_argument("--top", type=int, default=20, help="表格显示前 N 个会话，0=全部（默认 20）")
    ap.add_argument("--watch", nargs="?", const=3.0, type=float, default=0.0, metavar="SEC",
                    help="实时刷新的间隔秒数（默认 3 秒；不带 --once 时即默认模式）")
    ap.add_argument("--once", action="store_true",
                    help="只扫描一次后退出；不加此参数则持续实时刷新")
    ap.add_argument("--count", type=int, default=0,
                    help="实时模式重扫 N 次后退出（0=持续，默认 0）")
    ap.add_argument("--price-refresh", type=float, default=600.0, metavar="SEC",
                    help="实时模式下重新拉取官网价格的间隔秒数（默认 600 秒）")
    ap.add_argument("--csv", default="", help="导出逐会话明细到 CSV 文件（实时模式下每轮覆盖）")
    ap.add_argument("--json", default="", help="导出汇总结果为 JSON 文件（实时模式下每轮覆盖）")
    ap.add_argument("--list", action="store_true", help="只列出会话，不计算金额")
    ap.add_argument("--pause", action="store_true", help="强制在结束前等待回车")
    ap.add_argument("--no-pause", action="store_true", help="结束前不等待回车")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return ap


def main() -> int:
    setup_console()
    args = build_parser().parse_args()
    root = Path(args.root).expanduser().resolve()
    if not (root / "projects").is_dir():
        print(f"[错误] 未找到会话目录: {root / 'projects'}")
        print("       请用 --root 指定 WorkBuddy 数据根目录（含 projects 子目录）。")
        return 2
    if args.watch < 0 or args.count < 0:
        print("[错误] --watch / --count 不能为负数")
        return 2
    try:
        since = date.fromisoformat(args.since) if args.since else None
        until = date.fromisoformat(args.until) if args.until else None
    except ValueError:
        print("[错误] --since / --until 需为 YYYY-MM-DD 格式")
        return 2

    if args.offline:
        prices, price_source = dict(FALLBACK_PRICES), "内置价格表（离线）"
    else:
        try:
            prices, price_source = fetch_prices(), "官网实时价格"
        except Exception as exc:
            prices = dict(FALLBACK_PRICES)
            price_source = f"内置价格表（联网失败: {type(exc).__name__}）"
    meta, meta_note = load_session_meta(root / "workbuddy.db")
    active_ids = load_active_ids(root / "sessions")
    ctx = Context(
        args=args, root=root, prices=prices, price_source=price_source,
        price_time=time.time(), meta=meta, meta_note=meta_note,
        active_ids=active_ids,
        excluded_active=active_ids if args.exclude_current else set(),
        since=since, until=until,
        holidays={s.strip() for s in args.holidays.split(",") if s.strip()},
    )

    if not args.once:
        interval = args.watch if args.watch > 0 else 3.0
        return watch_loop(ctx, interval, pause_on_exit=(len(sys.argv) == 1))

    snap = collect(ctx)
    sys.stdout.write(build_report(ctx, snap))
    export_files(ctx, snap)
    if args.pause or (len(sys.argv) == 1 and not args.no_pause):
        try:
            input("\n按回车键退出...")
        except (EOFError, KeyboardInterrupt):
            pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
