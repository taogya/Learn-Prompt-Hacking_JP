"""
tatsu-lab/alpaca の instruction を日本語に翻訳するスクリプト。

使い方:
    # 全行を翻訳（途中から再開可能）
    python utils/translate_alpaca_instructions.py

    # 英語のまま残っている行だけ再翻訳
    python utils/translate_alpaca_instructions.py --retry-english

出力: resources/csv/tatsu-lab/alpaca_instructions_ja.csv
"""

import argparse
import csv
import json
import os
import time

from utils.llm_client import LLMClient, ProviderType

# --- 設定 ---
INPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "resources", "csv", "tatsu-lab", "alpaca_instructions.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "resources", "csv", "tatsu-lab", "alpaca_instructions_ja.csv")

# ローカルモデルは大きめバッチで効率化、外部APIは出力トークン上限があるため小さめ
_DEFAULT_BATCH_SIZES = {
    ProviderType.GITHUB: 10,
    ProviderType.OPENAI: 10,
    ProviderType.LOCAL: 50,
}
SUB_BATCH_SIZE = 10  # 段階フォールバック時の中間バッチサイズ

_DEFAULT_MAX_TOKENS = {
    ProviderType.GITHUB: 4000,
    ProviderType.OPENAI: 4000,
    ProviderType.LOCAL: 3000,
}

# ローカルではレート制限不要
_REQUEST_INTERVALS = {
    ProviderType.GITHUB: 4.5,   # 15 RPM = 4秒/リクエスト + マージン
    ProviderType.OPENAI: 1.0,
    ProviderType.LOCAL: 0,
}

SYSTEM_PROMPT = (
    "あなたは英日翻訳の専門家です。"
    "与えられた英語の指示（instruction）を自然な日本語に翻訳してください。"
    "必ず指定された JSON フォーマットで出力してください。"
)

llm = LLMClient()
BATCH_SIZE = _DEFAULT_BATCH_SIZES.get(llm.provider, 10)
MAX_TOKENS = _DEFAULT_MAX_TOKENS.get(llm.provider, 4000)
REQUEST_INTERVAL = _REQUEST_INTERVALS.get(llm.provider, 4.5)


def _is_english(text: str) -> bool:
    """テキストが主に英語（ASCII）かどうかを判定する。"""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / max(len(text), 1) > 0.8


def translate_batch(rows: list[dict]) -> list[dict] | None:
    """複数行をまとめて JSON 形式で翻訳する。"""
    input_array = [{"id": i, "instruction": r["instruction"]} for i, r in enumerate(rows)]

    # prompt = (
    #     "以下の JSON 配列の各要素の instruction を英語から日本語に翻訳してください。\n\n"
    #     "ルール:\n"
    #     "- 各要素の instruction を自然な日本語へ翻訳する\n"
    #     "- id はそのまま保持する\n"
    #     "- 意味を変えたり省略したりしない\n"
    #     "- 固有名詞や技術用語はそのままでもよい\n"
    #     "- 原文に改行(\\n)が含まれる場合は、翻訳後も同じ位置に改行を保持する\n\n"
    #     "入力:\n"
    #     f"```json\n{json.dumps(input_array, ensure_ascii=False)}\n```\n\n"
    #     '出力は {"translations": [...]} の JSON オブジェクトで返してください。'
    # )
    prompt = (
        "以下のJSON配列の各instructionを日本語に翻訳してください。\n"
        "- 改行(\\n)は翻訳後も保持する\n"
        "- 意味を変えたり省略したりしない\n"
        "- 固有名詞や技術用語はそのままでもよい\n"
        "- JSON配列で返す\n\n"
        f"{json.dumps(input_array, ensure_ascii=False)}"
    )

    api_kwargs = dict(
        system=SYSTEM_PROMPT,
        temperature=0,
        max_tokens=MAX_TOKENS,
    )
    # ローカルモデル（Ollama）は response_format 非対応の場合がある
    if llm.provider != ProviderType.LOCAL:
        api_kwargs["response_format"] = {"type": "json_object"}

    try:
        raw = llm.call(prompt, **api_kwargs)
        # JSON ブロックを抽出（```json ... ``` で囲まれている場合に対応）
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        data = json.loads(text)
        translations = data if isinstance(data, list) else data.get("translations", [])

        if len(translations) != len(rows):
            print(f"  JSON 要素数不一致: 期待={len(rows)}, 取得={len(translations)}")
            return None

        return [{"instruction": t["instruction"].strip()} for t in translations]

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  JSON パースエラー: {e}")
        return None
    except Exception as e:
        err_str = str(e)
        # レート制限: 待機して再試行
        if "429" in err_str or "rate" in err_str.lower():
            print("  レート制限検出 → 60秒待機後に再試行...")
            time.sleep(60)
            try:
                raw = llm.call(prompt, **api_kwargs)
                text = raw.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                data = json.loads(text)
                translations = data if isinstance(data, list) else data.get("translations", [])
                return [{"instruction": t["instruction"].strip()} for t in translations]
            except Exception as e2:
                print(f"  再試行も失敗: {e2}")
        else:
            print(f"  バッチ翻訳エラー: {e}")
        return None


def translate_single(row: dict) -> dict:
    """1行を個別に JSON 形式で翻訳する（フォールバック用）。"""
    prompt = (
        "以下の英語の指示を日本語に翻訳してください。\n"
        "原文に改行(\\n)が含まれる場合は、翻訳後も同じ位置に改行を保持してください。\n\n"
        f'{{"instruction": {json.dumps(row["instruction"], ensure_ascii=False)}}}\n\n'
        '出力は {"instruction": "..."} の JSON で返してください。'
    )

    api_kwargs = dict(
        system=SYSTEM_PROMPT,
        temperature=0,
        max_tokens=1024,
    )
    if llm.provider != ProviderType.LOCAL:
        api_kwargs["response_format"] = {"type": "json_object"}

    try:
        raw = llm.call(prompt, **api_kwargs)
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        data = json.loads(text)
        if "instruction" in data:
            return {"instruction": data["instruction"]}
        print(f"  JSON キー不足、原文を使用: {row['instruction'][:40]}...")
        return row
    except Exception as e:
        print(f"  翻訳エラー: {e}")
        return row


def translate_with_fallback(rows: list[dict]) -> list[dict]:
    """段階的フォールバックで翻訳する。

    BATCH_SIZE件 → SUB_BATCH_SIZE件ずつ → 1件ずつ の順で試行し、
    エラーが起きたブロックだけを細分化して再試行する。
    """
    result = translate_batch(rows)
    if result is not None:
        return result

    # 1件以下 or サブバッチと同サイズ以下なら直接1件ずつ
    if len(rows) <= SUB_BATCH_SIZE:
        print("→ 個別翻訳にフォールバック")
        result = []
        for row in rows:
            result.append(translate_single(row))
            if REQUEST_INTERVAL:
                time.sleep(REQUEST_INTERVAL)
        return result

    # 中間バッチに分割して再試行
    print(f"→ {SUB_BATCH_SIZE}件ずつに分割して再試行")
    result = []
    for j in range(0, len(rows), SUB_BATCH_SIZE):
        sub = rows[j:j + SUB_BATCH_SIZE]
        sub_result = translate_batch(sub)
        if sub_result is None:
            # サブバッチも失敗 → 1件ずつ
            print(f"  サブバッチ({j+1}-{j+len(sub)})失敗 → 個別翻訳")
            sub_result = []
            for row in sub:
                sub_result.append(translate_single(row))
                if REQUEST_INTERVAL:
                    time.sleep(REQUEST_INTERVAL)
        result.extend(sub_result)
        if REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL)
    return result


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

        result = translate_with_fallback(batch)

        translated.extend(result)
        append_csv(result)
        print("完了")
        if REQUEST_INTERVAL:
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
    english_indices = [i for i, row in enumerate(translated) if _is_english(row["instruction"])]

    if not english_indices:
        print("英語のまま残っている行はありません。")
        return

    print(f"英語のまま残っている行: {len(english_indices)} 行")
    print(f"対象行番号: {english_indices[:20]}{'...' if len(english_indices) > 20 else ''}")
    print(f"プロバイダ: {llm.provider.value}, モデル: {llm.model}")

    # バッチにまとめて再翻訳
    for i in range(0, len(english_indices), BATCH_SIZE):
        batch_indices = english_indices[i:i + BATCH_SIZE]
        batch = [translated[idx] for idx in batch_indices]
        print(f"再翻訳バッチ ({i + 1}-{i + len(batch_indices)}/{len(english_indices)})...", end=" ", flush=True)

        result = translate_with_fallback(batch)

        for j, idx in enumerate(batch_indices):
            translated[idx] = result[j]

        print("完了")
        save_csv(translated)
        if REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL)

    # 結果確認
    still_english = sum(1 for row in translated if _is_english(row["instruction"]))
    print(f"\n再翻訳完了! 残り英語行: {still_english}")


def main():
    parser = argparse.ArgumentParser(description="alpaca_instructions.csv 日本語翻訳")
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
