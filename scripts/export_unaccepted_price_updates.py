from __future__ import annotations

import argparse
import csv
import glob
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从百炼补价审核表中导出未被接受的价格条目。")
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="一个或多个审核 CSV，支持通配符，例如 releases/price_enrichment/price_updates_review*.csv。",
    )
    parser.add_argument(
        "--output",
        default="releases/price_enrichment/unaccepted_price_updates.csv",
        help="未接受条目的输出 CSV。",
    )
    parser.add_argument(
        "--accepted-status",
        default="ok",
        help="视为已接受的 status，多个值用逗号分隔，默认 ok。",
    )
    return parser.parse_args()


def expand_inputs(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        matched = [Path(item) for item in glob.glob(pattern)]
        if matched:
            files.extend(matched)
        else:
            files.append(Path(pattern))
    seen: set[str] = set()
    unique: list[Path] = []
    for file_path in files:
        key = str(file_path.resolve()) if file_path.exists() else str(file_path)
        if key not in seen:
            seen.add(key)
            unique.append(file_path)
    return unique


def reason_for(row: dict[str, str]) -> str:
    status = (row.get("status") or "").strip()
    if status == "low_confidence":
        return "查到了价格，但置信度低于阈值，建议人工复核后再写入。"
    if status == "no_price":
        return "模型未返回可用的单一人民币价格。"
    if status == "error":
        return row.get("error") or "调用或解析过程中出现异常。"
    if not (row.get("price_cny") or "").strip():
        return "缺少 price_cny 数值。"
    return "未达到自动接受条件。"


def main() -> int:
    args = parse_args()
    accepted_statuses = {
        item.strip()
        for item in args.accepted_status.split(",")
        if item.strip()
    }
    input_files = expand_inputs(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    status_counter: Counter[str] = Counter()
    scanned = 0
    for input_file in input_files:
        if not input_file.exists():
            print(f"[skip] 文件不存在：{input_file}")
            continue
        with input_file.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                scanned += 1
                status = (row.get("status") or "").strip()
                if status in accepted_statuses:
                    continue
                copied = dict(row)
                copied["reject_reason"] = reason_for(copied)
                copied["review_file"] = str(input_file)
                rows.append(copied)
                status_counter[status or "empty_status"] += 1

    base_fields = [
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
        "reject_reason",
        "source_summary",
        "error",
        "review_file",
    ]
    extra_fields: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in base_fields and key not in extra_fields:
                extra_fields.append(key)
    fieldnames = base_fields + extra_fields

    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"扫描 {scanned} 条审核记录，导出未接受 {len(rows)} 条：{output_path}")
    if status_counter:
        print("未接受原因统计：")
        for status, count in status_counter.most_common():
            print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
