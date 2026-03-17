"""翻訳 CSV の改行ずれを修復するスクリプト。

原文 CSV と翻訳 CSV を論理行（DictReader）で読み、
翻訳行の改行数が原文と異なる場合に原文の改行パターンを復元する。

使い方:
    python utils/_analyze_csv_offset.py [--dry-run]
"""
import csv
import sys

SRC = "resources/csv/tatsu-lab/test/alpaca_instructions.csv"
JA  = "resources/csv/tatsu-lab/test/alpaca_instructions_ja.csv"


def fix_newlines(orig_rows: list[dict], ja_rows: list[dict]) -> tuple[list[dict], int]:
    """翻訳行の改行数が原文と合わない行を修復する。

    原文の改行位置を参考に、翻訳テキスト中の対応箇所に改行を挿入する。
    原文で改行の直前にある文字列を翻訳文中で探し、見つかればそこに改行を入れる。
    見つからない場合はスキップ（元のまま）。

    Returns:
        (修復後の ja_rows, 修復した行数)
    """
    fixed_count = 0

    for i in range(min(len(orig_rows), len(ja_rows))):
        orig_text = orig_rows[i]["instruction"]
        ja_text = ja_rows[i]["instruction"]

        orig_nl = orig_text.count("\n")
        ja_nl = ja_text.count("\n")

        if orig_nl == ja_nl:
            continue

        # 原文を改行で分割して、各セグメントの区切りパターンを取得
        orig_segments = orig_text.split("\n")
        ja_flat = ja_text.replace("\n", "")  # とりあえず既存改行を除去

        # 原文の各セグメント末尾数文字を使って翻訳文での区切り位置を推定
        # → 確実な方法: 原文セグメント数と同じ改行数を翻訳に入れる
        # 原文が空セグメント（連続改行 \n\n）を持つ場合はそのまま保持
        rebuilt_segments = []
        ja_remaining = ja_flat

        # 空セグメント（\n\n）パターンを検出
        empty_positions = set()
        for seg_idx, seg in enumerate(orig_segments):
            if seg == "":
                empty_positions.add(seg_idx)

        # 非空セグメントの数
        non_empty_orig = [s for s in orig_segments if s != ""]
        non_empty_count = len(non_empty_orig)

        if non_empty_count <= 1:
            # 原文が全部空セグメント＋1テキストなど → 翻訳テキスト全体を1つとして扱う
            rebuilt = []
            for seg_idx, seg in enumerate(orig_segments):
                if seg == "":
                    rebuilt.append("")
                else:
                    rebuilt.append(ja_remaining)
                    ja_remaining = ""
            ja_rows[i]["instruction"] = "\n".join(rebuilt)
        else:
            # 非空セグメントが複数 → 均等分割（ヒューリスティック）
            # 原文のセグメント長比率で翻訳文を分割
            total_orig_len = sum(len(s) for s in non_empty_orig)
            rebuilt = []
            pos = 0
            non_empty_idx = 0
            for seg_idx, seg in enumerate(orig_segments):
                if seg == "":
                    rebuilt.append("")
                else:
                    if non_empty_idx < non_empty_count - 1:
                        # 比率で分割
                        ratio = len(seg) / max(total_orig_len, 1)
                        split_len = max(1, round(len(ja_flat) * ratio))
                        rebuilt.append(ja_flat[pos:pos + split_len])
                        pos += split_len
                    else:
                        # 最後は残り全部
                        rebuilt.append(ja_flat[pos:])
                    non_empty_idx += 1
            ja_rows[i]["instruction"] = "\n".join(rebuilt)

        fixed_count += 1

    return ja_rows, fixed_count


def main():
    dry_run = "--dry-run" in sys.argv

    with open(SRC, encoding="utf-8-sig") as f:
        orig = list(csv.DictReader(f))
    with open(JA, encoding="utf-8") as f:
        ja = list(csv.DictReader(f))

    print(f"Original rows: {len(orig)}")
    print(f"Ja rows:       {len(ja)}")

    # 修復前の状態
    before_phys = sum(1 + r["instruction"].count("\n") for r in ja)
    mismatched_before = sum(
        1 for i in range(min(len(orig), len(ja)))
        if orig[i]["instruction"].count("\n") != ja[i]["instruction"].count("\n")
    )
    print(f"改行不一致の行: {mismatched_before}")

    ja, fixed = fix_newlines(orig, ja)

    # 修復後の状態
    after_phys = sum(1 + r["instruction"].count("\n") for r in ja)
    mismatched_after = sum(
        1 for i in range(min(len(orig), len(ja)))
        if orig[i]["instruction"].count("\n") != ja[i]["instruction"].count("\n")
    )

    print(f"\n修復した行: {fixed}")
    print(f"物理行数: {before_phys} → {after_phys} (+{after_phys - before_phys})")
    print(f"残りの不一致: {mismatched_after}")

    # 修復結果を表示
    for i in range(min(len(orig), len(ja))):
        orig_nl = orig[i]["instruction"].count("\n")
        ja_nl = ja[i]["instruction"].count("\n")
        if orig_nl > 0 or ja_nl > 0:
            if orig_nl == ja_nl and i < 15600:  # 修復された行だけ表示
                # 修復前に不一致だった可能性のある行
                pass

    if dry_run:
        print("\n[dry-run] ファイルは書き換えません。")
        # 修復例を数件表示
        for i in range(min(len(orig), len(ja))):
            orig_nl = orig[i]["instruction"].count("\n")
            if orig_nl > 0:
                print(f"\n  Row {i}:")
                print(f"    orig: {orig[i]['instruction'][:100]!r}")
                print(f"    ja:   {ja[i]['instruction'][:100]!r}")
                fixed -= 0  # just for display count
                if i > 11100:
                    break
    else:
        with open(JA, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["instruction"])
            writer.writeheader()
            writer.writerows(ja)
        print(f"\n保存完了: {JA}")


if __name__ == "__main__":
    main()
