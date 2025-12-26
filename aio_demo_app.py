import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import pandas as pd

import os
from openai import AzureOpenAI, RateLimitError
from dotenv import load_dotenv

# Azure OpenAI のキーとエンドポイントを .env から取得
load_dotenv()
endpoint = os.getenv("AZ_OPENAI_ENDPOINT")
deployment = os.getenv("AZ_OPENAI_DEPLOYMENT")
subscription_key = os.getenv("AZ_OPENAI_KEY")
api_version = os.getenv("AZ_OPENAI_API_VERSION", "2025-04-01-preview")

# ===== 重要部分だけ抽出する関数（方法1） =====
def extract_important_sections(soup: BeautifulSoup) -> str:
    """
    ページの重要部分（見出しとその直後の段落）だけを抽出して返す。
    AIO観点で意味のある情報だけに絞ることで、トークン数とコストを削減する。
    """
    parts = []

    # H1
    h1 = soup.find("h1")
    if h1:
        parts.append(f"[H1] {h1.get_text(strip=True)}")
        p = h1.find_next_sibling("p")
        if p:
            parts.append(f"- {p.get_text(strip=True)}")

    # H2 / H3
    for tag in soup.find_all(["h2", "h3"]):
        heading = tag.get_text(strip=True)
        parts.append(f"[{tag.name.upper()}] {heading}")

        # 見出し直後の段落を取得
        p = tag.find_next_sibling("p")
        if p:
            parts.append(f"- {p.get_text(strip=True)}")

    # 何も取れなかった場合のフォールバック
    if not parts:
        body_text = soup.get_text(separator=" ", strip=True)
        return body_text[:3000]

    # まとめて返す（最後に長さを制限）
    return "\n".join(parts)[:3000]


# ===== LLM による詳細診断 =====
def analyze_page_with_llm(url: str, page_text: str, scores: dict) -> str:
    """
    重要部分とスコアをAzure OpenAIに渡して、構造化された示唆レポートを生成する
    """
    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=subscription_key,
    )

    # 念のためダブルで長さ制限
    short_text = page_text[:3000]

    prompt = f"""
あなたはプロのWebマーケティングコンサルタントです。
以下のURLとページ内容、診断スコアをもとに、AIO（AI検索・エージェント時代）の観点から
構造化された改善提案レポートを日本語で作成してください。

【診断スコア】
- 回答性: {scores.get("回答性")}
- 構造化: {scores.get("構造化")}
- FAQ/HowTo: {scores.get("FAQ/HowTo")}
- ブランド性: {scores.get("ブランド性")}

【レポート構成（必ずこの順・見出しで）】
### 1. 回答性（ユーザーの質問にどこまで答えられているか）
- 現状評価（2〜3行）
- 改善すべき具体的なポイントを箇条書きで3〜5個
- 特にAIO時代に重要になる理由を1〜2行でコメント

### 2. 構造化・技術的な分かりやすさ
（同じく：現状評価 → 箇条書き改善案 → なぜ重要か）

### 3. FAQ / HowTo コンテンツ
（同じ構成）

### 4. ブランド性・信頼性
（同じ構成）

### 5. 最優先で着手すべき改善3つ
- 箇条書きで「施策名：理由」の形式で3つ

【出力フォーマットの条件】
- Markdownで出力する
- 箇条書きは - を使う
- 1つ1つの指摘は「どの部分をどう直すか」が分かるレベルまで具体的に書く
- 文体は「です・ます調」で簡潔に

--- URL ---
{url}

--- Page Text（重要部分のみ） ---
{short_text}
"""

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=16384,
            model=deployment,
        )
        return response.choices[0].message.content

    except RateLimitError:
        # レートリミットに当たってもアプリを落とさずメッセージを返す
        return (
            "#### ※API利用上限に達しました\n\n"
            "- Azure OpenAI API のレート制限／利用上限に達している可能性があります。\n"
            "- しばらく時間をおいて再度お試しください。\n"
            "- 継続利用する場合は、Azureポータルの Usage / Billing からクレジット残高をご確認ください。"
        )
    except Exception as e:
        return (
            "#### ※AI詳細診断でエラーが発生しました\n\n"
            f"- エラー内容: {e}\n"
            "- プロンプトや入力内容を見直すか、時間をおいて再度お試しください。"
        )


# ===== Streamlit アプリ本体 =====
st.set_page_config(page_title="AIO Readiness Checker Demo", layout="wide")

st.title("AIO Readiness Checker（デモ版）")

# OpenAI API Key 入力欄の削除

st.write("URLを入力すると、AI検索時代のコンテンツ適性を簡易スコアリングします。")

urls_text = st.text_area(
    "診断したいURL（1行に1つ）",
    "https://example.com",
    height=120,
)

if st.button("診断する"):
    urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
    results = []

    for url in urls:
        try:
            resp = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            results.append(
                {
                    "URL": url,
                    "ステータス": f"取得失敗: {e}",
                    "総合スコア": 0,
                    "回答性": 0,
                    "構造化": 0,
                    "FAQ/HowTo": 0,
                    "ブランド性": 0,
                    "本文要約": "",
                }
            )
            continue

        # ページ本文（全文）
        full_text = soup.get_text(separator=" ", strip=True)
        text_len = len(full_text)

        # AIO観点で重要な部分だけ抽出（見出し＋直後の段落）
        important_text = extract_important_sections(soup)

        # 回答性（テキスト量）は全文ベースで判定
        if text_len > 8000:
            ans_score = 100
        elif text_len > 4000:
            ans_score = 80
        elif text_len > 2000:
            ans_score = 60
        elif text_len > 1000:
            ans_score = 40
        else:
            ans_score = 20

        # 構造化データ / 見出し
        has_ld = bool(soup.find("script", {"type": "application/ld+json"}))
        has_h1 = bool(soup.find("h1"))
        struct_score = 50
        if has_ld:
            struct_score += 30
        if has_h1:
            struct_score += 20

        # FAQ / HowTo キーワード（これも全文で判定）
        keywords = ["よくある質問", "FAQ", "Q&A", "質問", "How to", "使い方"]
        faq_score = 20
        if any(k.lower() in full_text.lower() for k in keywords):
            faq_score = 80

        # ブランド性（ドメイン由来のキーワード頻度）
        hostname = urlparse(url).hostname or ""
        brand_token = hostname.split(".")[0]
        brand_count = full_text.lower().count(brand_token.lower()) if brand_token else 0
        if brand_count > 30:
            brand_score = 100
        elif brand_count > 10:
            brand_score = 80
        elif brand_count > 3:
            brand_score = 60
        elif brand_count > 0:
            brand_score = 40
        else:
            brand_score = 20

        # 総合スコア
        total = round(
            0.35 * ans_score
            + 0.25 * struct_score
            + 0.25 * faq_score
            + 0.15 * brand_score
        )

        results.append(
            {
                "URL": url,
                "ステータス": "OK",
                "総合スコア": total,
                "回答性": ans_score,
                "構造化": struct_score,
                "FAQ/HowTo": faq_score,
                "ブランド性": brand_score,
                "本文要約": important_text,  # LLM にはこちらを渡す
            }
        )

    # 結果テーブル（本文要約列は隠す）
    df = pd.DataFrame(results)
    if "本文要約" in df.columns:
        df_display = df.drop(columns=["本文要約"])
    else:
        df_display = df

    st.subheader("診断結果")
    st.dataframe(df_display)

    # 指標ごとのAIO観点での意味づけ
    st.markdown(
        """
##### 各指標の意味（AIO時代における重要性）

- **総合スコア**：下記4つの観点を総合した「AI検索時代にどれだけ対応できているか」の目安です。
- **回答性**：ユーザーの質問に1ページで答え切れているか。会話型AIが引用する際の“答えの質”に直結します。
- **構造化**：見出し構造や構造化データの整備度。AIや検索エンジンがページ内容を機械的に理解できるかを左右します。
- **FAQ/HowTo**：Q&Aや手順コンテンツの充実度。LLMが回答生成時に最も参照しやすい形式であり、AI推奨に乗りやすい領域です。
- **ブランド性**：ブランド名・実績・運営情報などの明示度。AIが「信頼できる情報源」と判断するかどうかに関わる指標です。
"""
    )

    # -------------------------
    # ここから自動示唆（スコア＋AIレポート）
    # -------------------------
    st.subheader("自動示唆（AI生成レポート）")
    for row in results:
        if row["ステータス"] != "OK":
            st.markdown(
                f"### {row['URL']}\n"
                "- ページ取得に失敗しました。公開設定・URLを確認してください。"
            )
            continue

        st.markdown(f"### {row['URL']}")

        # 1) スコアサマリー表
        scores = {
            "回答性": row["回答性"],
            "構造化": row["構造化"],
            "FAQ/HowTo": row["FAQ/HowTo"],
            "ブランド性": row["ブランド性"],
        }

        def level(score: int) -> str:
            if score >= 80:
                return "良好"
            if score >= 60:
                return "要改善"
            return "優先改善"

        def priority(score: int) -> str:
            if score >= 80:
                return "低"
            if score >= 60:
                return "中"
            return "高"

        table_lines = ["| 観点 | スコア | 評価 | 優先度 |", "| --- | --- | --- | --- |"]
        for k, v in scores.items():
            table_lines.append(f"| {k} | {v} | {level(v)} | {priority(v)} |")
        st.markdown("\n".join(table_lines))

        # 2) このURL専用の改善レポートをLLMに書かせる
        # Azure OpenAI連携、APIキー欄なしで必ず実施
        if subscription_key and endpoint and deployment:
            llm_report = analyze_page_with_llm(
                row["URL"], row.get("本文要約", ""), scores
            )
            st.markdown(llm_report)
        else:
            st.info(
                "Azure OpenAI のAPI情報が環境変数に設定されていません。正しいAPIキー情報(.env)をセットしてください。"
            )
