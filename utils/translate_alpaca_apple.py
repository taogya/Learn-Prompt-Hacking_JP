"""
tatsu-lab/alpaca の instruction を Apple Translation API で日本語に翻訳するスクリプト。

前提:
    - macOS 26 以降
    - utils/apple_translate がビルド済み
      cd utils/apple_translate && swift build -c release

使い方:
    # 全行を翻訳（途中から再開可能）
    python utils/translate_alpaca_apple.py

    # 英語のまま残っている行だけ再翻訳
    python utils/translate_alpaca_apple.py --retry-english

出力: resources/csv/tatsu-lab/alpaca_instructions_at_ja.csv
"""

import argparse
import csv
import json
import os
import subprocess
import sys

# --- 設定 ---
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(_SCRIPT_DIR, "..", "resources", "csv", "tatsu-lab", "alpaca_instructions.csv")
OUTPUT_CSV = os.path.join(_SCRIPT_DIR, "..", "resources", "csv", "tatsu-lab", "alpaca_instructions_at_ja.csv")

SWIFT_CLI = os.path.join(_SCRIPT_DIR, "apple_translate", ".build", "release", "apple-translate")

BATCH_SIZE = 200  # Apple Translation はローカルNMT、高速なので大きめ


def _check_cli():
    """Swift CLI バイナリの存在を確認する。"""
    if not os.path.isfile(SWIFT_CLI):
        print(f"エラー: Swift CLI が見つかりません: {SWIFT_CLI}", file=sys.stderr)
        print("ビルド手順:", file=sys.stderr)
        print("  cd utils/apple_translate && swift build -c release", file=sys.stderr)
        sys.exit(1)


def _is_english(text: str) -> bool:
    """テキストが主に英語（ASCII）かどうかを判定する。"""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / max(len(text), 1) > 0.8


def translate_batch(texts: list[str]) -> list[str]:
    """Swift CLI を呼び出してバッチ翻訳する。"""
    # JSON Lines を stdin に流す
    input_lines = "\n".join(json.dumps({"text": t}, ensure_ascii=False) for t in texts)

    result = subprocess.run(
        [SWIFT_CLI, "--from", "en", "--to", "ja"],
        input=input_lines,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        print(f"  Swift CLI エラー (exit={result.returncode}):", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
        return texts  # 失敗時は原文を返す

    # stderr の警告を表示
    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            print(f"  [swift] {line}", file=sys.stderr)

    # stdout から JSON Lines をパース
    translated = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            translated.append(obj.get("text", ""))
        except json.JSONDecodeError:
            translated.append("")

    if len(translated) != len(texts):
        print(
            f"  出力行数不一致: 期待={len(texts)}, 取得={len(translated)}",
            file=sys.stderr,
        )
        # 足りない分は原文で埋める
        while len(translated) < len(texts):
            translated.append(texts[len(translated)])
        translated = translated[: len(texts)]

    return translated


def save_csv(rows: list[dict]):
    """翻訳結果を CSV に保存する（全行書き込み）。"""
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["instruction"])
        writer.writeheader()
        writer.writerows(rows)


def append_csv(rows: list[dict]):
    """翻訳結果を CSV に追記する。ファイルがなければヘッダー付きで新規作成。"""
    file_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["instruction"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def run_full_translation():
    """全行を翻訳する（途中再開対応）。"""
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"翻訳対象: {len(rows)} 行")
    print(f"翻訳エンジン: Apple Translation API (via Swift CLI)")
    print(f"バッチサイズ: {BATCH_SIZE}")

    # 途中まで翻訳済みなら続きから
    translated = []
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            translated = list(csv.DictReader(f))
        print(f"既存の翻訳: {len(translated)} 行 → 続きから再開")

    start_idx = len(translated)
    remaining = rows[start_idx:]
    total_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i : i + BATCH_SIZE]
        batch_num = (start_idx + i) // BATCH_SIZE + 1
        texts = [r["instruction"] for r in batch]

        print(
            f"バッチ {batch_num}/{total_batches} "
            f"({start_idx + i + 1}-{start_idx + i + len(batch)}/{len(rows)})...",
            end=" ",
            flush=True,
        )

        results = translate_batch(texts)
        result_rows = [{"instruction": t} for t in results]

        translated.extend(result_rows)
        append_csv(result_rows)
        print("完了")

    print(f"\n翻訳完了! {len(translated)} 行 → {OUTPUT_CSV}")


def run_retry_english():
    """英語のまま残っている行だけを再翻訳する。"""
    if not os.path.exists(OUTPUT_CSV):
        print(f"出力ファイルが見つかりません: {OUTPUT_CSV}")
        print("先に全体翻訳を実行してください。")
        return

    with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
        translated = list(csv.DictReader(f))

    english_indices = [i for i, row in enumerate(translated) if _is_english(row["instruction"])]

    if not english_indices:
        print("英語のまま残っている行はありません。")
        return

    print(f"英語のまま残っている行: {len(english_indices)} 行")
    print(f"対象行番号: {english_indices[:20]}{'...' if len(english_indices) > 20 else ''}")
    print(f"翻訳エンジン: Apple Translation API (via Swift CLI)")

    for i in range(0, len(english_indices), BATCH_SIZE):
        batch_indices = english_indices[i : i + BATCH_SIZE]
        texts = [translated[idx]["instruction"] for idx in batch_indices]

        print(
            f"再翻訳バッチ ({i + 1}-{i + len(batch_indices)}/{len(english_indices)})...",
            end=" ",
            flush=True,
        )

        results = translate_batch(texts)
        for j, idx in enumerate(batch_indices):
            translated[idx] = {"instruction": results[j]}

        print("完了")
        save_csv(translated)

    still_english = sum(1 for row in translated if _is_english(row["instruction"]))
    print(f"\n再翻訳完了! 残り英語行: {still_english}")


def main():
    _check_cli()

    parser = argparse.ArgumentParser(
        description="alpaca_instructions.csv 日本語翻訳 (Apple Translation API版)"
    )
    parser.add_argument(
        "--retry-english",
        action="store_true",
        help="英語のまま残っている行だけを再翻訳する",
    )
    args = parser.parse_args()

    if args.retry_english:
        run_retry_english()
    else:
        run_full_translation()


if __name__ == "__main__":
    main()
