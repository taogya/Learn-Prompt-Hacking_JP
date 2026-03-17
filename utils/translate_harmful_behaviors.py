"""
harmful_behaviors.csv を日本語に翻訳するスクリプト。

使い方:
    # 全行を翻訳（途中から再開可能）
    python scripts/translate_harmful_behaviors.py

    # 英語のまま残っている行だけ再翻訳
    python scripts/translate_harmful_behaviors.py --retry-english

出力: resources/csv/llm-attacks/harmful_behaviors_ja.csv
"""

import argparse
import csv
import json
import os
import sys
import time

from utils.llm_client import call_llm, LLMClient

llm = LLMClient()

# --- 設定 ---
INPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "resources", "csv", "llm-attacks", "harmful_behaviors.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "resources", "csv", "llm-attacks", "harmful_behaviors_ja.csv")

BATCH_SIZE = 10  # gpt-4o-mini: 出力4000トークン上限のため10行が安全圏
MAX_TOKENS = 4000  # GitHub Models 無料枠の出力トークン上限（Low tier）
REQUEST_INTERVAL = 4.5  # 秒（15 RPM = 4秒/リクエスト + マージン）

SYSTEM_PROMPT = (
    "あなたは英日翻訳の専門家です。LLMセキュリティ研究用データセット（AdvBench）の翻訳を行います。"
    "研究目的のため、内容を検閲・省略せず忠実に翻訳してください。"
    "必ず指定された JSON フォーマットで出力してください。"
)


def _is_english(text: str) -> bool:
    """テキストが主に英語（ASCII）かどうかを判定する。"""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / max(len(text), 1) > 0.8


def translate_batch(rows: list[dict]) -> list[dict] | None:
    """複数行をまとめて JSON 形式で翻訳する。"""
    input_array = [{"id": i, "goal": r["goal"], "target": r["target"]} for i, r in enumerate(rows)]

    prompt = (
        "以下の JSON 配列の各要素の goal と target を英語から日本語に翻訳してください。\n"
        "これは LLM セキュリティ研究（AdvBench データセット）用の評価データです。\n\n"
        "ルール:\n"
        "- 各要素の goal と target を忠実に日本語へ翻訳する\n"
        "- id はそのまま保持する\n"
        "- 意味を変えたり省略したりしない\n"
        "- 固有名詞や技術用語はそのままでもよい\n\n"
        "入力:\n"
        f"```json\n{json.dumps(input_array, ensure_ascii=False)}\n```\n\n"
        '出力は {"translations": [...]} の JSON オブジェクトで返してください。'
    )

    api_kwargs = dict(
        system=SYSTEM_PROMPT,
        temperature=0.1,
        response_format={"type": "json_object"},
        max_tokens=MAX_TOKENS,
    )

    try:
        raw = call_llm(prompt, **api_kwargs)
        data = json.loads(raw)
        translations = data.get("translations", [])

        if len(translations) != len(rows):
            print(f"  JSON 要素数不一致: 期待={len(rows)}, 取得={len(translations)}")
            return None

        return [{"goal": t["goal"], "target": t["target"]} for t in translations]

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  JSON パースエラー: {e}")
        return None
    except Exception as e:
        err_str = str(e)
        # コンテンツフィルター: バッチ全体がブロックされた場合
        if "content_filter" in err_str or "ResponsibleAI" in err_str:
            print(f"  コンテンツフィルター検出 → 個別翻訳にフォールバック")
            return None
        # レート制限: 待機して再試行
        if "429" in err_str or "rate" in err_str.lower():
            print("  レート制限検出 → 60秒待機後に再試行...")
            time.sleep(60)
            try:
                raw = call_llm(prompt, **api_kwargs)
                data = json.loads(raw)
                return [{"goal": t["goal"], "target": t["target"]} for t in data["translations"]]
            except Exception as e2:
                print(f"  再試行も失敗: {e2}")
        else:
            print(f"  バッチ翻訳エラー: {e}")
        return None


def translate_single(row: dict) -> dict:
    """1行を個別に JSON 形式で翻訳する（フォールバック用）。"""
    prompt = (
        "以下の英語テキストを日本語に翻訳してください。\n"
        "LLM セキュリティ研究用データのため、忠実に翻訳してください。\n\n"
        f'{{"goal": {json.dumps(row["goal"], ensure_ascii=False)}, '
        f'"target": {json.dumps(row["target"], ensure_ascii=False)}}}\n\n'
        '出力は {"goal": "...", "target": "..."} の JSON で返してください。'
    )

    try:
        raw = call_llm(
            prompt,
            system=SYSTEM_PROMPT,
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
        data = json.loads(raw)
        if "goal" in data and "target" in data:
            return {"goal": data["goal"], "target": data["target"]}
        print(f"  JSON キー不足、原文を使用: {row['goal'][:40]}...")
        return row
    except Exception as e:
        err_str = str(e)
        if "content_filter" in err_str or "ResponsibleAI" in err_str:
            print(f"  コンテンツフィルター、原文保持: {row['goal'][:40]}...")
        else:
            print(f"  翻訳エラー: {e}")
        return row


def save_csv(rows: list[dict]):
    """翻訳結果を CSV に保存する。"""
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["goal", "target"])
        writer.writeheader()
        writer.writerows(rows)


def run_full_translation():
    """全行を翻訳する（途中再開対応）。"""
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"翻訳対象: {len(rows)} 行")
    print(f"プロバイダ: {llm.provider.value}, モデル: {llm.model}")
    print(f"バッチサイズ: {BATCH_SIZE}, リクエスト間隔: {REQUEST_INTERVAL}秒")

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
        batch = remaining[i:i + BATCH_SIZE]
        batch_num = (start_idx + i) // BATCH_SIZE + 1
        print(
            f"バッチ {batch_num}/{total_batches} "
            f"({start_idx + i + 1}-{start_idx + i + len(batch)}/{len(rows)})...",
            end=" ", flush=True,
        )

        result = translate_batch(batch)
        if result is None:
            # フォールバック: 1行ずつ
            print("→ 個別翻訳にフォールバック")
            result = []
            for row in batch:
                result.append(translate_single(row))
                time.sleep(REQUEST_INTERVAL)

        translated.extend(result)
        print("完了")
        save_csv(translated)
        time.sleep(REQUEST_INTERVAL)

    print(f"\n翻訳完了! {len(translated)} 行 → {OUTPUT_CSV}")


def run_retry_english():
    """英語のまま残っている行だけを再翻訳する。"""
    if not os.path.exists(OUTPUT_CSV):
        print(f"出力ファイルが見つかりません: {OUTPUT_CSV}")
        print("先に全体翻訳を実行してください。")
        return

    with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
        translated = list(csv.DictReader(f))

    # 英語のまま残っている行を検出
    english_indices = [i for i, row in enumerate(translated) if _is_english(row["goal"])]

    if not english_indices:
        print("英語のまま残っている行はありません。")
        return

    print(f"英語のまま残っている行: {len(english_indices)} 行")
    print(f"対象行番号: {english_indices}")
    print(f"プロバイダ: {llm.provider.value}, モデル: {llm.model}")

    # バッチにまとめて再翻訳
    for i in range(0, len(english_indices), BATCH_SIZE):
        batch_indices = english_indices[i:i + BATCH_SIZE]
        batch = [translated[idx] for idx in batch_indices]
        print(f"再翻訳バッチ ({i + 1}-{i + len(batch_indices)}/{len(english_indices)})...", end=" ", flush=True)

        result = translate_batch(batch)
        if result is None:
            result = []
            for row in batch:
                result.append(translate_single(row))
                time.sleep(REQUEST_INTERVAL)

        for j, idx in enumerate(batch_indices):
            translated[idx] = result[j]

        print("完了")
        save_csv(translated)
        time.sleep(REQUEST_INTERVAL)

    # 結果確認
    still_english = sum(1 for row in translated if _is_english(row["goal"]))
    print(f"\n再翻訳完了! 残り英語行: {still_english}")


def main():
    parser = argparse.ArgumentParser(description="harmful_behaviors.csv 日本語翻訳")
    parser.add_argument(
        "--retry-english", action="store_true",
        help="英語のまま残っている行だけを再翻訳する",
    )
    args = parser.parse_args()

    if args.retry_english:
        run_retry_english()
    else:
        run_full_translation()


if __name__ == "__main__":
    main()
