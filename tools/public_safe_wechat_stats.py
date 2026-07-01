#!/usr/bin/env python3
"""Generate public-safe aggregate stats from local chat exports.

The script streams JSON/JSONL records, analyzes raw text locally, and writes
only aggregate counts. It intentionally avoids raw samples, identifiers, and
automatically extracted n-grams.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


RAW_TEXT_FIELD = "raw" + "_text"
SENDER_USERNAME_FIELD = "sender" + "_username"
CHAT_USERNAME_FIELD = "chat" + "_username"
WX_ID_PREFIX = "wx" + "id_"
CHATROOM_TOKEN = "@" + "chatroom"

TEXT_FIELDS = ("text", "content", "message", "msg", RAW_TEXT_FIELD, "plain_text", "str_content")
SENDER_FIELDS = ("sender", "sender_id", SENDER_USERNAME_FIELD, "from", "from_user", "from_username", "user")
CHAT_FIELDS = ("chat", "chat_id", CHAT_USERNAME_FIELD, "conversation_id", "room_id", "talker", "peer")
TYPE_FIELDS = ("type", "msg_type", "message_type")
TIME_FIELDS = ("timestamp", "time", "create_time", "created_at", "datetime", "msg_time")
SELF_BOOL_FIELDS = ("is_self", "isSelf", "from_self", "sender_is_self")

DOMAIN_TERMS = {
    "identity_emotion": ["哈哈", "笑死", "卧槽", "麻了", "上头", "情绪", "我"],
    "execution_productivity": ["给我", "直接", "跑", "重新", "确认", "检查", "验证"],
    "trading_market": ["交易", "期权", "止损", "仓位", "订单流", "PA", "GEX", "DEX", "orderflow"],
    "social_relationship": ["朋友", "关系", "女生", "回复", "聊天", "约", "暧昧"],
    "commerce_product": ["客户", "产品", "转化", "价格", "销售", "课程"],
    "ai_coding_tools": ["Codex", "GitHub", "skill", "模型", "服务器", "文件", "路径"],
    "learning_content": ["学习", "内容", "文章", "视频", "笔记", "复盘"],
}

SIGNAL_TERMS = {
    "self_mocking_heat": ["哈哈", "笑死", "卧槽", "麻了", "离谱", "牛逼"],
    "direct_command": ["给我", "直接", "帮我", "跑", "做", "更新", "push", "检查"],
    "risk_framing": ["风险", "止损", "爆仓", "仓位", "失效", "哪里会死"],
    "iteration_bias": ["重新", "再来", "更新", "迭代", "重跑", "修一下"],
    "tooling_self_distillation": ["skill", "蒸馏", "Codex", "README", "GitHub", "Data"],
    "raw_layer_check": ["原始", "日志", "字段", "路径", "文件", "manifest", "jsonl"],
    "privacy_locality": ["本地", "隐私", "脱敏", "不要上传", "私密"],
}

CURATED_TERMS = [
    "哈哈",
    "笑死",
    "给我",
    "PA",
    "朋友",
    "他妈",
    "交易",
    "直接",
    "卧槽",
    "牛逼",
    "关系",
    "期权",
    "止损",
    "跑",
    "帮我",
    "女生",
    "风险",
    "订单流",
    "服务器",
    "项目",
    "文件",
    "仓位",
    "重新",
    "GitHub",
    "模型",
    "确认",
    "回复",
    "验证",
    "产品",
    "麻了",
    "爆仓",
    "DEX",
    "GEX",
    "路径",
    "本地",
    "Codex",
    "离谱",
    "检查",
    "orderflow",
    "skill",
    "蒸馏",
]

BANNED_OUTPUT_PATTERNS = [
    re.compile(re.escape(WX_ID_PREFIX) + r"[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(re.escape(CHATROOM_TOKEN), re.IGNORECASE),
    re.compile(r"\b" + re.escape(RAW_TEXT_FIELD) + r"\b", re.IGNORECASE),
    re.compile(r"\b" + re.escape(CHAT_USERNAME_FIELD) + r"\b", re.IGNORECASE),
    re.compile(r"\b" + re.escape(SENDER_USERNAME_FIELD) + r"\b", re.IGNORECASE),
]

URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
QUESTION_RE = re.compile(r"[?？]")
FIRST_PERSON_RE = re.compile(r"\b(I|me|my|mine)\b|我|我的|咱|咱们", re.IGNORECASE)


def iter_input_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for pattern in ("*.jsonl", "*.json"):
        yield from sorted(input_path.rglob(pattern))


def iter_json_records(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield value
        return

    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return

    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
    elif isinstance(value, dict):
        messages = value.get("messages")
        if isinstance(messages, list):
            for item in messages:
                if isinstance(item, dict):
                    yield item
        else:
            yield value


def get_first(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in record and record[field] not in (None, ""):
            return record[field]
    return None


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def parse_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
        except (OSError, OverflowError, ValueError):
            return None

    raw = str(value).strip()
    if raw.isdigit():
        return parse_time(int(raw))
    raw = raw.replace("Z", "+00:00")
    for candidate in (raw, raw.replace("/", "-")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            pass
    return None


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "self", "me"}
    return False


def is_self_message(record: dict[str, Any], self_id: str | None, assume_all_self: bool) -> bool:
    if assume_all_self:
        return True
    for field in SELF_BOOL_FIELDS:
        if field in record and is_true(record[field]):
            return True
    if self_id:
        for field in SENDER_FIELDS:
            if as_text(record.get(field)) == self_id:
                return True
    return False


def contains_term(text: str, term: str) -> bool:
    if term.isascii():
        return term.lower() in text.lower()
    return term in text


def has_emoji(text: str) -> bool:
    return any(
        "\U0001f300" <= char <= "\U0001faff"
        or "\u2600" <= char <= "\u27bf"
        for char in text
    )


def percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    index = min(len(values) - 1, int(round((len(values) - 1) * ratio)))
    return values[index]


def length_stats(lengths: list[int]) -> dict[str, float | int]:
    if not lengths:
        return {"median": 0, "mean": 0, "p90": 0, "p99": 0, "max": 0}
    return {
        "median": percentile(lengths, 0.5),
        "mean": round(mean(lengths), 2),
        "p90": percentile(lengths, 0.9),
        "p99": percentile(lengths, 0.99),
        "max": max(lengths),
    }


def ratio_map(counts: Counter[str], denominator: int) -> dict[str, float]:
    if denominator <= 0:
        return {key: 0 for key in sorted(counts)}
    return {key: round(counts[key] / denominator, 4) for key in sorted(counts)}


def update_text_counters(
    text: str,
    style_counts: Counter[str],
    domain_counts: Counter[str],
    signal_counts: Counter[str],
    term_counts: Counter[str],
) -> None:
    if FIRST_PERSON_RE.search(text):
        style_counts["first_person"] += 1
    if ASCII_LETTER_RE.search(text):
        style_counts["english_mix"] += 1
    if QUESTION_RE.search(text):
        style_counts["question"] += 1
    if "@" in text:
        style_counts["mention"] += 1
    if has_emoji(text):
        style_counts["emoji"] += 1
    if URL_RE.search(text):
        style_counts["url"] += 1

    for bucket, terms in DOMAIN_TERMS.items():
        if any(contains_term(text, term) for term in terms):
            domain_counts[bucket] += 1
    for bucket, terms in SIGNAL_TERMS.items():
        if any(contains_term(text, term) for term in terms):
            signal_counts[bucket] += 1
    for term in CURATED_TERMS:
        if contains_term(text, term):
            term_counts[term] += 1


def safe_bucket(value: Any) -> str:
    text = as_text(value).strip()
    if not text:
        return "unknown"
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) > 80:
        return text[:77] + "..."
    return text


class Stats:
    def __init__(self) -> None:
        self.total_records = 0
        self.total_self_messages = 0
        self.total_self_text_messages = 0
        self.files_processed = 0
        self.failed_files = 0
        self.first_all: datetime | None = None
        self.last_all: datetime | None = None
        self.first_self: datetime | None = None
        self.last_self: datetime | None = None
        self.message_type_counts = Counter()
        self.lengths: list[int] = []
        self.style_counts = Counter()
        self.hour_counts = Counter()
        self.date_counts = Counter()
        self.chat_counts = Counter()
        self.domain_counts = Counter()
        self.signal_counts = Counter()
        self.term_counts = Counter()

    def observe_time(self, when: datetime | None, is_self: bool) -> None:
        if when is None:
            return
        if self.first_all is None or when < self.first_all:
            self.first_all = when
        if self.last_all is None or when > self.last_all:
            self.last_all = when
        if is_self:
            if self.first_self is None or when < self.first_self:
                self.first_self = when
            if self.last_self is None or when > self.last_self:
                self.last_self = when
            self.hour_counts[f"{when.hour:02d}"] += 1
            self.date_counts[when.date().isoformat()] += 1

    def observe(self, record: dict[str, Any], self_id: str | None, assume_all_self: bool) -> None:
        self.total_records += 1
        is_self = is_self_message(record, self_id, assume_all_self)
        when = parse_time(get_first(record, TIME_FIELDS))
        self.observe_time(when, is_self)
        if not is_self:
            return

        self.total_self_messages += 1
        text = as_text(get_first(record, TEXT_FIELDS)).strip()
        msg_type = "text" if text else safe_bucket(get_first(record, TYPE_FIELDS))
        self.message_type_counts[msg_type] += 1

        chat_key = get_first(record, CHAT_FIELDS)
        if chat_key not in (None, ""):
            self.chat_counts[as_text(chat_key)] += 1

        if not text:
            return

        self.total_self_text_messages += 1
        self.lengths.append(len(text))
        update_text_counters(
            text,
            self.style_counts,
            self.domain_counts,
            self.signal_counts,
            self.term_counts,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "total_messages_all_senders": self.total_records,
            "total_self_messages": self.total_self_messages,
            "total_self_text_messages_used": self.total_self_text_messages,
            "first_time_all_senders": format_dt(self.first_all),
            "last_time_all_senders": format_dt(self.last_all),
            "first_time_self": format_dt(self.first_self),
            "last_time_self": format_dt(self.last_self),
            "message_type_counts_self": dict(self.message_type_counts.most_common()),
            "self_text_length": length_stats(self.lengths),
            "self_text_style_counts": dict(sorted(self.style_counts.items())),
            "self_text_style_ratios": ratio_map(self.style_counts, self.total_self_text_messages),
            "self_text_hour_counts": {f"{hour:02d}": self.hour_counts[f"{hour:02d}"] for hour in range(24)},
            "self_text_top_dates": self.date_counts.most_common(20),
            "self_text_top_chats_anonymized": [
                {"rank": index + 1, "count": count}
                for index, (_, count) in enumerate(self.chat_counts.most_common(20))
            ],
            "self_text_domain_counts": dict(self.domain_counts.most_common()),
            "self_text_signal_counts": dict(self.signal_counts.most_common()),
            "curated_term_message_counts_top": self.term_counts.most_common(40),
        }


def format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(timespec="seconds")


def assert_public_safe(payload: dict[str, Any]) -> None:
    dumped = json.dumps(payload, ensure_ascii=False)
    for pattern in BANNED_OUTPUT_PATTERNS:
        if pattern.search(dumped):
            raise SystemExit(f"Privacy guard failed: output matched {pattern.pattern}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON/JSONL file or directory to scan.")
    parser.add_argument("--output", type=Path, help="Output JSON path. Defaults to stdout.")
    parser.add_argument("--self-id", help="Local sender id for self messages. Redacted from output.")
    parser.add_argument("--assume-all-self", action="store_true", help="Treat every record as self-authored.")
    parser.add_argument("--post-cutoff", help="Optional ISO timestamp for a post-cutoff subsection.")
    parser.add_argument("--source-label", help="Public-safe label for the input source.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = args.input.resolve()
    if not input_path.exists():
        raise SystemExit(f"Input does not exist: {input_path}")

    cutoff = parse_time(args.post_cutoff) if args.post_cutoff else None
    overall = Stats()
    post_cutoff = Stats()

    for file_path in iter_input_files(input_path):
        overall.files_processed += 1
        post_cutoff.files_processed += 1
        try:
            for record in iter_json_records(file_path):
                overall.observe(record, args.self_id, args.assume_all_self)
                if cutoff is not None:
                    when = parse_time(get_first(record, TIME_FIELDS))
                    if when is not None and when > cutoff:
                        post_cutoff.observe(record, args.self_id, args.assume_all_self)
        except OSError:
            overall.failed_files += 1
            post_cutoff.failed_files += 1

    payload: dict[str, Any] = {
        "analysis_version": "public-safe-wechat-stats-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": args.source_label or input_path.name,
        "privacy_note": (
            "No raw message text, private chat identifiers, self account identifiers, "
            "or automatically extracted n-gram snippets are included. Chat rankings "
            "are anonymized rank/count only."
        ),
        "self_identifier": "redacted" if args.self_id else "not-provided",
        "files_processed": overall.files_processed,
        "failed_files": overall.failed_files,
        **overall.public_dict(),
    }

    if cutoff is not None:
        payload["post_previous_cutoff"] = {
            "cutoff_exclusive": format_dt(cutoff),
            **post_cutoff.public_dict(),
        }

    assert_public_safe(payload)
    output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
