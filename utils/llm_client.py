"""
LLM クライアント設定ユーティリティ

GitHub Models / OpenAI API / ローカル LLM（Ollama）を切り替えて利用するための共有モジュール。
詳細は 1_Basics/00_Setup.ipynb を参照してください。
"""

from enum import Enum
import os
import subprocess
from openai import OpenAI

# ---------------------------------------------------------------------------
# プロバイダ設定
#   環境変数 LLM_PROVIDER で切り替え可能（デフォルト: github）
#   - "github"  : GitHub Models（GitHub Token で利用）
#   - "openai"  : OpenAI API（OpenAI API Key で利用）
#   - "local"   : ローカル LLM（Ollama 等、OpenAI 互換サーバー）
# ---------------------------------------------------------------------------


class ProviderType(Enum):
    GITHUB = "github"
    OPENAI = "openai"
    LOCAL = "local"


PROVIDER = ProviderType(os.environ.get("LLM_PROVIDER", ProviderType.LOCAL.value).lower())
# PROVIDER = ProviderType(os.environ.get("LLM_PROVIDER", ProviderType.GITHUB.value).lower())
# PROVIDER = ProviderType(os.environ.get("LLM_PROVIDER", ProviderType.OPENAI.value).lower())

# ---------------------------------------------------------------------------
# モデル名
#   環境変数 LLM_MODEL で上書き可能
#   デフォルトはプロバイダに応じて自動設定:
#     github / openai → gpt-4o-mini
#     local           → gemma3:4b（軽量で日本語対応）
# ---------------------------------------------------------------------------
_DEFAULT_MODELS = {
    ProviderType.GITHUB: "openai/gpt-4o-mini",
    ProviderType.OPENAI: "openai/gpt-4o-mini",
    ProviderType.LOCAL: "gemma3:4b",
}
DEFAULT_MODEL = _DEFAULT_MODELS.get(PROVIDER, "openai/gpt-4o-mini")
MODEL_NAME = os.environ.get("LLM_MODEL", DEFAULT_MODEL)

CLIENT_TYPE = OpenAI


def _get_github_token() -> str:
    """GitHub Token を取得する（環境変数 → gh CLI の順で試行）"""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    raise EnvironmentError(
        "GitHub Token が見つかりません。\n"
        "以下のいずれかを設定してください:\n"
        "  1. 環境変数 GITHUB_TOKEN を設定する\n"
        "  2. GitHub CLI をインストールして `gh auth login` を実行する\n"
        "詳細は 1_Basics/00_Setup.ipynb を参照してください。"
    )


def create_client(provider: ProviderType | None = None) -> CLIENT_TYPE:
    """プロバイダに応じた OpenAI クライアントを生成する"""

    provider = provider or PROVIDER

    match provider:
        case ProviderType.GITHUB:
            api_key = _get_github_token()
            return OpenAI(
                base_url="https://models.github.ai/inference",
                api_key=api_key,
            )
        case ProviderType.OPENAI:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "OPENAI_API_KEY 環境変数が設定されていません。"
                )
            return OpenAI(api_key=api_key)
        case ProviderType.LOCAL:
            base_url = os.environ.get("LLM_LOCAL_URL", "http://localhost:11434/v1")
            return OpenAI(
                base_url=base_url,
                api_key="ollama",  # Ollama は API キー不要（ダミー値）
            )
        case _:
            raise ValueError(
                f"未対応のプロバイダ: {provider}\n"
                f"LLM_PROVIDER は {[p.value for p in ProviderType]} のいずれかを指定してください。"
            )


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def md_print(text: str):
    """テキストを Markdown として表示する（ノートブック用）"""
    from IPython.display import display, Markdown
    display(Markdown(text))


# ---------------------------------------------------------------------------
# LLMClient クラス
#   プロバイダ・モデル・API クライアントを一体管理する。
#   翻訳スクリプト等で独自のプロバイダ/モデルを使う場合に直接インスタンス化する。
#   モジュールレベル関数（call_llm 等）は内部でデフォルトインスタンスに委譲する。
# ---------------------------------------------------------------------------

class LLMClient:
    """プロバイダ・モデル・API クライアントを一体管理するクラス。"""

    def __init__(
        self,
        provider: ProviderType | None = None,
        model: str | None = None,
    ):
        self.provider = provider or PROVIDER
        self.model = model or os.environ.get(
            "LLM_MODEL",
            _DEFAULT_MODELS.get(self.provider, "openai/gpt-4o-mini"),
        )
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """API クライアント（初回アクセス時に生成）。"""
        if self._client is None:
            self._client = create_client(self.provider)
        return self._client

    def call(self, prompt: str, *, system: str | None = None, **kwargs) -> str:
        """LLM にプロンプトを送信し、応答テキストを返す。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        api_kwargs = {"model": self.model, "messages": messages}
        api_kwargs.update(kwargs)

        completion = self.client.chat.completions.create(**api_kwargs)
        return completion.choices[0].message.content

    def call_and_print(self, prompt: str, *, system: str | None = None) -> str:
        """LLM にプロンプトを送信し、プロンプトと応答を Markdown で表示する。"""
        response = self.call(prompt, system=system)
        md_print(f"**User:** {prompt}")
        md_print(f"**LLM:** {response}")
        return response


# デフォルト LLMClient インスタンス（遅延初期化）
_default_llm: LLMClient | None = None


def _get_default_llm() -> LLMClient:
    global _default_llm
    if _default_llm is None:
        _default_llm = LLMClient()
    return _default_llm


# ---------------------------------------------------------------------------
# モジュールレベル関数（後方互換）
#   内部でデフォルト LLMClient に委譲する。
#   client / model を明示的に渡すレガシー用法もサポート。
# ---------------------------------------------------------------------------

def call_llm(prompt: str, *, system: str | None = None, **kwargs) -> str:
    """
    LLM にプロンプトを送信し、応答テキストを返す。

    Args:
        prompt: ユーザープロンプト
        system: システムプロンプト（省略可）
        **kwargs: その他 chat.completions.create に渡すパラメータ
                  （temperature, max_tokens, response_format 等）

    Returns:
        LLM の応答テキスト
    """
    return _get_default_llm().call(prompt, system=system, **kwargs)


def call_llm_and_print(prompt: str, *, system: str | None = None):
    """
    LLM にプロンプトを送信し、プロンプトと応答を Markdown で表示する。

    旧 call_GPT() の置き換え用。
    """
    return _get_default_llm().call_and_print(prompt, system=system)
