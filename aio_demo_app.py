import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import pandas as pd

from openai import OpenAI


def analyze_page_with_llm(api_key: str, url: str, page_text: str, scores: dict) -> str:
    """ページ本文とスコアをLLMに渡して、構造化された示唆を生成する"""
    client = OpenAI(api_key=api_key)

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

--- Page Text（内容。長文のため一部のみ） ---
{page_text[:8000]}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return response.choices[0].message.content


st.set_page_config(page_title="AIO Readiness Checker Demo", layout="wide")

st.title("AIO Readiness Checker（デモ版）")

# OpenAI API Key 入力欄
openai_api_key = st.text_input(
    "OpenAI API Key を入力してください（ページ内容の詳細診断に必要）",
    type="password",
)

if not openai_api_key:
    st.info(
        "※ API Key を入れない場合は、通常のスコア診断のみ表示されます。"
        "詳細診断（どの部分をどう直すかの具体診断）は表示されません。"
    )

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
                    "本文": "",
                }
            )
            continue

        # ページ本文を抽出
        text = soup.get_text(separator=" ", strip=True)
        text_len = len(text)

        # 回答性（テキスト量）
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

        # FAQ / HowTo キーワード
        keywords = ["よくある質問", "FAQ", "Q&A", "質問", "How to", "使い方"]
        faq_score = 20
        if any(k.lower() in text.lower() for k in keywords):
            faq_score = 80

        # ブランド性（ドメイン由来のキーワード頻度）
        hostname = urlparse(url).hostname or ""
        brand_token = hostname.split(".")[0]
        brand_count = text.lower().count(brand_token.lower()) if brand_token else 0
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
                "本文": text,  # LLM用に本文も保存
            }
        )

    # 結果テーブル（本文列は隠す）
    df = pd.DataFrame(results)
    if "本文" in df.columns:
        df_display = df.drop(columns=["本文"])
    else:
        df_display = df

    st.subheader("診断結果")
    st.dataframe(df_display)

    # 指標ごとのAIO観点での意味づけ（小さめの説明）
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
    # ここから自動示唆（全部AI生成）
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

        # 1) スコアサマリー表（これはそのまま）
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
        if openai_api_key:
            llm_report = analyze_page_with_llm(
                openai_api_key, row["URL"], row.get("本文", ""), scores
            )
            st.markdown(llm_report)
        else:
            st.info(
                "OpenAI API Key を入力すると、このページ内容とスコアに基づいた詳細な改善レポートが表示されます。"
            )
