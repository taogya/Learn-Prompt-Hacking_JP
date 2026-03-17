"""
汎用 CSV 翻訳エンジン。

CSV ファイルの指定フィールドを LLM で英日翻訳する。
バッチ翻訳・段階フォールバック・途中再開・retry-english をサポート。

使い方:
    from utils.translate_csv import TranslationConfig, run_translation

    config = TranslationConfig(
        input_csv="path/to/input.csv",
        output_csv="path/to/output_ja.csv",
        fields=["instruction"],
        system_prompt="あなたは英日翻訳の専門家です。...",
    )
    run_translation(config)
    # or
    run_translation(config, retry_english=True)
"""

import csv
import json
import os
import time
from dataclasses import dataclass, field

from utils.llm_client import (
    LLMClient, MODEL_NAME, PROVIDER, ProviderType,
)

# ---------------------------------------------------------------------------
# プロバイダ別デフォルト設定
# ---------------------------------------------------------------------------
_DEFAULT_BATCH_SIZES = {
    ProviderType.GITHUB: 10,
    ProviderType.OPENAI: 10,
    ProviderType.LOCAL: 50,
}
_DEFAULT_MAX_TOKENS = {
    ProviderType.GITHUB: 4000,
    ProviderType.OPENAI: 4000,
    ProviderType.LOCAL: 16000,
}
_DEFAULT_REQUEST_INTERVALS = {
    ProviderType.GITHUB: 4.5,
    ProviderType.OPENAI: 1.0,
    ProviderType.LOCAL: 0,
}


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
@dataclass
class TranslationConfig:
    """翻訳ジョブの設定。"""

    # 入出力
    input_csv: str
    output_csv: str
    fields: list[str]                       # 翻訳対象フィールド名

    # プロンプト
    system_prompt: str = (
        "あなたは英日翻訳の専門家です。"
        "与えられた英語テキストを自然な日本語に翻訳してください。"
        "必ず指定された JSON フォーマットで出力してください。"
    )
    extra_rules: list[str] = field(default_factory=list)

    # LLM
    provider: ProviderType = PROVIDER
    model: str = MODEL_NAME
    batch_size: int = 0         # 0 ならプロバイダ別デフォルト
    sub_batch_size: int = 10
    max_tokens: int = 0         # 0 ならプロバイダ別デフォルト
    request_interval: float = -1  # 負ならプロバイダ別デフォルト

    # CSV 読み込み
    input_encoding: str = "utf-8-sig"

    # 英語判定（retry-english 用）
    english_check_field: str = ""   # 空なら fields[0] を使用

    def __post_init__(self):
        if self.batch_size <= 0:
            self.batch_size = _DEFAULT_BATCH_SIZES.get(self.provider, 10)
        if self.max_tokens <= 0:
            self.max_tokens = _DEFAULT_MAX_TOKENS.get(self.provider, 4000)
        if self.request_interval < 0:
            self.request_interval = _DEFAULT_REQUEST_INTERVALS.get(
                self.provider, 4.5)
        if not self.english_check_field:
            self.english_check_field = self.fields[0]


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _is_english(text: str) -> bool:
    """テキストが主に英語（ASCII）かどうかを判定する。"""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / max(len(text), 1) > 0.8


def _extract_json(raw: str) -> dict:
    """LLM 応答から JSON を抽出してパースする。"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


# ---------------------------------------------------------------------------
# 翻訳コア
# ---------------------------------------------------------------------------

def _build_batch_prompt(rows: list[dict], cfg: TranslationConfig) -> str:
    """バッチ翻訳用プロンプトを構築する。"""
    input_array = [
        {"id": i, **{f: r[f] for f in cfg.fields}}
        for i, r in enumerate(rows)
    ]

    rules = [
        f"- 各要素の {', '.join(cfg.fields)} を自然な日本語へ翻訳する",
        "- id はそのまま保持する",
        "- 意味を変えたり省略したりしない",
        "- 固有名詞や技術用語はそのままでもよい",
        "- 原文に改行(\\n)が含まれる場合は、翻訳後も同じ位置に改行を保持する",
    ]
    rules.extend(cfg.extra_rules)

    return (
        f"以下の JSON 配列の各要素の {', '.join(cfg.fields)} を"
        "英語から日本語に翻訳してください。\n\n"
        "ルール:\n" + "\n".join(rules) + "\n\n"
        "入力:\n"
        f"```json\n{json.dumps(input_array, ensure_ascii=False)}\n```\n\n"
        '出力は {"translations": [...]} の JSON オブジェクトで返してください。'
    )


def _build_single_prompt(row: dict, cfg: TranslationConfig) -> str:
    """1行翻訳用プロンプトを構築する。"""
    obj = {f: row[f] for f in cfg.fields}
    return (
        "以下の英語テキストを日本語に翻訳してください。\n"
        "原文に改行(\\n)が含まれる場合は、翻訳後も同じ位置に改行を保持してください。\n\n"
        f"{json.dumps(obj, ensure_ascii=False)}\n\n"
        f'出力は {json.dumps({f: "..." for f in cfg.fields})} の JSON で返してください。'
    )


def _make_api_kwargs(cfg: TranslationConfig, max_tokens: int | None = None):
    """共通の API kwargs を構築する。"""
    kwargs = dict(
        system=cfg.system_prompt,
        temperature=0.1,
        max_tokens=max_tokens or cfg.max_tokens,
    )
    if cfg.provider != ProviderType.LOCAL:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def _extract_fields(row: dict, fields: list[str]) -> dict:
    """翻訳結果から対象フィールドだけを抽出する。"""
    return {f: row[f] for f in fields}


def translate_batch(
    rows: list[dict], cfg: TranslationConfig, llm: LLMClient,
) -> list[dict] | None:
    """複数行をまとめて翻訳する。失敗時は None。"""
    prompt = _build_batch_prompt(rows, cfg)
    api_kwargs = _make_api_kwargs(cfg)

    try:
        raw = llm.call(prompt, **api_kwargs)
        data = _extract_json(raw)
        translations = data.get("translations", [])

        if len(translations) != len(rows):
            print(f"  JSON 要素数不一致: 期待={len(rows)}, "
                  f"取得={len(translations)}")
            return None

        return [_extract_fields(t, cfg.fields) for t in translations]

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  JSON パースエラー: {e}")
        return None
    except Exception as e:
        err_str = str(e)
        if "content_filter" in err_str or "ResponsibleAI" in err_str:
            print("  コンテンツフィルター検出 → フォールバック")
            return None
        if "429" in err_str or "rate" in err_str.lower():
            print("  レート制限検出 → 60秒待機後に再試行...")
            time.sleep(60)
            try:
                raw = llm.call(prompt, **api_kwargs)
                data = _extract_json(raw)
                return [_extract_fields(t, cfg.fields)
                        for t in data["translations"]]
            except Exception as e2:
                print(f"  再試行も失敗: {e2}")
        else:
            print(f"  バッチ翻訳エラー: {e}")
        return None


def translate_single(
    row: dict, cfg: TranslationConfig, llm: LLMClient,
) -> dict:
    """１行を個別に翻訳する（フォールバック用）。"""
    prompt = _build_single_prompt(row, cfg)
    api_kwargs = _make_api_kwargs(cfg, max_tokens=1024)

    try:
        raw = llm.call(prompt, **api_kwargs)
        data = _extract_json(raw)
        if all(f in data for f in cfg.fields):
            return _extract_fields(data, cfg.fields)
        print(f"  JSON キー不足、原文を使用: "
              f"{row[cfg.fields[0]][:40]}...")
        return {f: row[f] for f in cfg.fields}
    except Exception as e:
        err_str = str(e)
        if "content_filter" in err_str or "ResponsibleAI" in err_str:
            print(f"  コンテンツフィルター、原文保持: "
                  f"{row[cfg.fields[0]][:40]}...")
        else:
            print(f"  翻訳エラー: {e}")
        return {f: row[f] for f in cfg.fields}


def translate_with_fallback(
    rows: list[dict], cfg: TranslationConfig, llm: LLMClient,
) -> list[dict]:
    """段階的フォールバックで翻訳する。

    batch_size件 → sub_batch_size件ずつ → 1件ずつ の順で試行し、
    エラーが起きたブロックだけを細分化して再試行する。
    """
    result = translate_batch(rows, cfg, llm)
    if result is not None:
        return result

    if len(rows) <= cfg.sub_batch_size:
        print("→ 個別翻訳にフォールバック")
        result = []
        for row in rows:
            result.append(translate_single(row, cfg, llm))
            if cfg.request_interval:
                time.sleep(cfg.request_interval)
        return result

    print(f"→ {cfg.sub_batch_size}件ずつに分割して再試行")
    result = []
    for j in range(0, len(rows), cfg.sub_batch_size):
        sub = rows[j:j + cfg.sub_batch_size]
        sub_result = translate_batch(sub, cfg, llm)
        if sub_result is None:
            print(f"  サブバッチ({j+1}-{j+len(sub)})失敗 → 個別翻訳")
            sub_result = []
            for row in sub:
                sub_result.append(translate_single(row, cfg, llm))
                if cfg.request_interval:
                    time.sleep(cfg.request_interval)
        result.extend(sub_result)
        if cfg.request_interval:
            time.sleep(cfg.request_interval)
    return result


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def _save_csv(path: str, rows: list[dict], fields: list[str]):
    """全行書き込み。"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _append_csv(path: str, rows: list[dict], fields: list[str]):
    """追記。ファイルがなければヘッダー付きで新規作成。"""
    file_exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# メインワークフロー
# ---------------------------------------------------------------------------

def run_translation(cfg: TranslationConfig, *, retry_english: bool = False):
    """翻訳を実行する。

    Args:
        cfg: 翻訳設定
        retry_english: True なら英語のまま残っている行だけ再翻訳
    """
    if retry_english:
        _run_retry_english(cfg)
    else:
        _run_full(cfg)


def _run_full(cfg: TranslationConfig):
    """全行を翻訳する（途中再開対応）。"""
    with open(cfg.input_csv, "r", encoding=cfg.input_encoding) as f:
        rows = list(csv.DictReader(f))

    llm = LLMClient(provider=cfg.provider, model=cfg.model)

    print(f"翻訳対象: {len(rows)} 行")
    print(f"プロバイダ: {cfg.provider.value}, モデル: {cfg.model}")
    print(f"バッチサイズ: {cfg.batch_size}, "
          f"リクエスト間隔: {cfg.request_interval}秒")

    # 途中まで翻訳済みなら続きから
    translated: list[dict] = []
    if os.path.exists(cfg.output_csv):
        with open(cfg.output_csv, "r", encoding="utf-8") as f:
            translated = list(csv.DictReader(f))
        print(f"既存の翻訳: {len(translated)} 行 → 続きから再開")

    start_idx = len(translated)
    remaining = rows[start_idx:]
    total_batches = (len(rows) + cfg.batch_size - 1) // cfg.batch_size

    for i in range(0, len(remaining), cfg.batch_size):
        batch = remaining[i:i + cfg.batch_size]
        batch_num = (start_idx + i) // cfg.batch_size + 1
        print(
            f"バッチ {batch_num}/{total_batches} "
            f"({start_idx + i + 1}-"
            f"{start_idx + i + len(batch)}/{len(rows)})...",
            end=" ", flush=True,
        )

        result = translate_with_fallback(batch, cfg, llm)

        translated.extend(result)
        _append_csv(cfg.output_csv, result, cfg.fields)
        print("完了")
        if cfg.request_interval:
            time.sleep(cfg.request_interval)

    print(f"\n翻訳完了! {len(translated)} 行 → {cfg.output_csv}")


def _run_retry_english(cfg: TranslationConfig):
    """英語のまま残っている行だけを再翻訳する。"""
    if not os.path.exists(cfg.output_csv):
        print(f"出力ファイルが見つかりません: {cfg.output_csv}")
        print("先に全体翻訳を実行してください。")
        return

    with open(cfg.output_csv, "r", encoding="utf-8") as f:
        translated = list(csv.DictReader(f))

    check_field = cfg.english_check_field
    english_indices = [
        i for i, row in enumerate(translated)
        if _is_english(row[check_field])
    ]

    if not english_indices:
        print("英語のまま残っている行はありません。")
        return

    llm = LLMClient(provider=cfg.provider, model=cfg.model)

    print(f"英語のまま残っている行: {len(english_indices)} 行")
    print(f"対象行番号: {english_indices[:20]}"
          f"{'...' if len(english_indices) > 20 else ''}")
    print(f"プロバイダ: {cfg.provider.value}, モデル: {cfg.model}")

    for i in range(0, len(english_indices), cfg.batch_size):
        batch_indices = english_indices[i:i + cfg.batch_size]
        batch = [translated[idx] for idx in batch_indices]
        print(
            f"再翻訳バッチ ({i + 1}-"
            f"{i + len(batch_indices)}/{len(english_indices)})...",
            end=" ", flush=True,
        )

        result = translate_with_fallback(batch, cfg, llm)

        for j, idx in enumerate(batch_indices):
            translated[idx] = result[j]

        print("完了")
        _save_csv(cfg.output_csv, translated, cfg.fields)
        if cfg.request_interval:
            time.sleep(cfg.request_interval)

    still_english = sum(
        1 for row in translated if _is_english(row[check_field]))
    print(f"\n再翻訳完了! 残り英語行: {still_english}")
