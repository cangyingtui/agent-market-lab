from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地调用百炼 API 补齐缺失价格，并生成审核 CSV 与 SQL。")
    parser.add_argument("--input", required=True, help="缺价产品 CSV，来自 export_missing_product_prices.py。")
    parser.add_argument("--delimiter", default="auto", choices=["auto", "csv", "tsv"], help="输入文件分隔符。默认按扩展名自动识别。")
    parser.add_argument("--review-output", default="price_updates_review.csv", help="人工审核用 CSV 输出路径。")
    parser.add_argument("--sql-output", default="price_updates.sql", help="可上传远程执行的 SQL 输出路径。")
    parser.add_argument("--limit", type=int, default=50, help="最多处理多少条。")
    parser.add_argument("--offset", type=int, default=0, help="从输入 CSV 的偏移位置开始处理。")
    parser.add_argument("--min-confidence", type=float, default=None, help="最低写入置信度。")
    parser.add_argument("--api-key", default="", help="百炼 API Key。不填则读取 PRICE_ENRICHMENT_API_KEY。")
    parser.add_argument("--api-base", default="", help="OpenAI 兼容 API Base。默认百炼兼容地址。")
    parser.add_argument("--model", default="", help="模型名，默认 qwen-plus 或 PRICE_ENRICHMENT_MODEL。")
    parser.add_argument("--sleep-seconds", type=float, default=0.2, help="每次调用后的间隔，避免触发限流。")
    parser.add_argument("--include-low-confidence", action="store_true", help="低置信度结果也写入 SQL，默认不写。")
    parser.add_argument("--no-search", action="store_true", help="不传 enable_search=true。")
    return parser.parse_args()


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        text = value.replace(",", "").replace("￥", "").replace("¥", "").strip()
        match = re.search(r"\d+(?:\.\d+)?", text)
        if match:
            parsed = float(match.group(0))
            return parsed if parsed > 0 else None
    return None


def _json_from_text(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def _sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _load_specs(row: dict[str, str]) -> dict[str, Any]:
    raw = _text(row.get("specifications_json"))
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _build_prompt(row: dict[str, str]) -> list[dict[str, str]]:
    specs = _load_specs(row)
    product_name = _text(row.get("product_name") or row.get("confirmed_sku"))
    brand = _text(row.get("brand"))
    category = " / ".join(
        item
        for item in (_text(row.get("category")), _text(row.get("subcategory")))
        if item
    )
    payload = {
        "task": "估算中国市场公开零售价格",
        "product": {
            "brand": brand,
            "name": product_name,
            "category": category,
            "specifications": specs,
        },
        "requirements": [
            "请优先参考公开电商、品牌官网或可信资讯中的近期人民币价格。",
            "只返回 JSON，不要输出解释性文本。",
            "字段固定为 price_cny、currency、source_summary、confidence。",
            "price_cny 为单个数字，不要返回价格区间；如果只能找到区间，取主流成交价或中位数。",
            "confidence 为 0-1，低于 0.65 表示不建议自动写入数据库。",
        ],
    }
    return [
        {"role": "system", "content": "你是谨慎的商品价格补全助手，只根据公开资料估算价格。"},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
    ]


def _estimate(row: dict[str, str], *, api_key: str, api_base: str, model: str, enable_search: bool) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=api_base, timeout=settings.price_enrichment_timeout_seconds)
    kwargs = {
        "model": model,
        "messages": _build_prompt(row),
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        if enable_search:
            response = client.chat.completions.create(**kwargs, extra_body={"enable_search": True})
        else:
            response = client.chat.completions.create(**kwargs)
    except TypeError:
        response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    data = _json_from_text(content)
    price = _number(data.get("price_cny") or data.get("price") or data.get("estimated_price"))
    confidence = _number(data.get("confidence")) or 0.0
    if price is None:
        return {
            "status": "no_price",
            "price_cny": "",
            "currency": _text(data.get("currency")) or "CNY",
            "source_summary": _text(data.get("source_summary") or data.get("source")),
            "confidence": confidence,
            "raw": content[:1000],
        }
    return {
        "status": "ok",
        "price_cny": round(price, 2),
        "currency": _text(data.get("currency")) or "CNY",
        "source_summary": _text(data.get("source_summary") or data.get("source") or "公开资料估算"),
        "confidence": max(0.0, min(1.0, confidence)),
        "raw": content[:1000],
    }


def _sql_for_update(row: dict[str, str], estimate: dict[str, Any]) -> str:
    product_id = int(row["id"])
    price = float(estimate["price_cny"])
    meta = {
        "price_cny": price,
        "currency": estimate.get("currency") or "CNY",
        "source_summary": estimate.get("source_summary") or "公开资料估算",
        "confidence": float(estimate.get("confidence") or 0),
        "provider": "bailian_openai_compatible",
        "updated_by": "local_price_enrichment_sql",
        "requires_manual_review": True,
    }
    meta_json = json.dumps(meta, ensure_ascii=False, default=str)
    return (
        "UPDATE products "
        f"SET price_cny = {price:.2f}, "
        "specifications = JSON_SET(COALESCE(specifications, JSON_OBJECT()), "
        f"'$._price_enrichment', CAST({_sql_quote(meta_json)} AS JSON)), "
        "updated_at = NOW() "
        f"WHERE id = {product_id} AND price_cny IS NULL;"
    )


def main() -> int:
    args = parse_args()
    api_key = (
        args.api_key
        or os.getenv("PRICE_ENRICHMENT_API_KEY")
        or settings.price_enrichment_api_key
        or os.getenv("DASHSCOPE_API_KEY")
    )
    api_base = args.api_base or settings.price_enrichment_api_base or DEFAULT_API_BASE
    model = args.model or settings.price_enrichment_model or "qwen-plus"
    min_confidence = (
        float(args.min_confidence)
        if args.min_confidence is not None
        else settings.price_enrichment_min_confidence
    )
    if not api_key:
        print("缺少百炼 API Key。请设置 PRICE_ENRICHMENT_API_KEY，或使用 --api-key。")
        return 2

    input_path = Path(args.input)
    review_path = Path(args.review_output)
    sql_path = Path(args.sql_output)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.parent.mkdir(parents=True, exist_ok=True)

    delimiter = "\t" if args.delimiter == "tsv" or (args.delimiter == "auto" and input_path.suffix.lower() == ".tsv") else ","
    with input_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=delimiter))
    selected = rows[max(args.offset, 0) : max(args.offset, 0) + max(args.limit, 1)]

    review_fields = [
        "id",
        "category",
        "subcategory",
        "brand",
        "product_name",
        "confirmed_sku",
        "price_cny",
        "confidence",
        "currency",
        "status",
        "source_summary",
        "error",
    ]
    sql_lines = [
        "-- Price enrichment SQL generated locally.",
        "-- Review price_updates_review.csv before applying.",
        "START TRANSACTION;",
    ]
    scanned = 0
    accepted = 0
    with review_path.open("w", encoding="utf-8-sig", newline="") as review_fh:
        writer = csv.DictWriter(review_fh, fieldnames=review_fields)
        writer.writeheader()
        for row in selected:
            scanned += 1
            review_row = {field: _text(row.get(field)) for field in review_fields}
            review_row["error"] = ""
            try:
                estimate = _estimate(
                    row,
                    api_key=api_key,
                    api_base=api_base,
                    model=model,
                    enable_search=not args.no_search,
                )
                confidence = float(estimate.get("confidence") or 0)
                status = _text(estimate.get("status")) or "skip"
                if status == "ok" and (confidence >= min_confidence or args.include_low_confidence):
                    sql_lines.append(_sql_for_update(row, estimate))
                    accepted += 1
                elif status == "ok":
                    status = "low_confidence"
                review_row.update(
                    {
                        "price_cny": _text(estimate.get("price_cny")),
                        "confidence": f"{confidence:.2f}",
                        "currency": _text(estimate.get("currency") or "CNY"),
                        "status": status,
                        "source_summary": _text(estimate.get("source_summary")),
                    }
                )
                print(
                    f"[{status}] #{row.get('id')} {row.get('brand')} {row.get('product_name')} "
                    f"price={review_row['price_cny'] or '-'} confidence={review_row['confidence']}"
                )
            except Exception as exc:  # noqa: BLE001 - batch job should keep going and record failures.
                review_row["status"] = "error"
                review_row["error"] = f"{type(exc).__name__}: {exc}"
                print(f"[error] #{row.get('id')} {row.get('product_name')}: {review_row['error']}")
            writer.writerow(review_row)
            review_fh.flush()
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    sql_lines.append("COMMIT;")
    sql_path.write_text("\n".join(sql_lines) + "\n", encoding="utf-8")
    print(f"完成：处理 {scanned} 条，SQL 接受 {accepted} 条。")
    print(f"审核表：{review_path}")
    print(f"SQL：{sql_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
