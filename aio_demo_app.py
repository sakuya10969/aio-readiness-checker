import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import pandas as pd

from openai import OpenAI

def analyze_page_with_llm(api_key, url, page_text):
    client = OpenAI(api_key=api_key)

    prompt = f"""
あなたはプロのWebコンサルタントです。
以下のURLとページ内容を読み、AIO観点から具体的に改善点を出してください。

【出す内容】
1. ページ全体の総評（100字）
2. 具体的な改善すべき箇所（ページ内のどの部分を直すか、箇条書きで5つ）
3. セクション別改善案（ファーストビュー / 見出し / 本文 / 事例 / FAQ / CTA）
4. 最優先で直すべき3点（理由つき）

--- URL ---
{url}

--- Page Text（内容） ---
{page_text[:8000]}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    return response.choices[0].message["content"]

st.set_page_config(page_title="AIO Readiness Checker Demo", layout="wide")

st.title("AIO Readiness Checker（デモ版）")
# OpenAI API Key 入力欄
openai_api_key = st.text_input("OpenAI API Key を入力してください（ページ内容の詳細診断に必要）", type="password")
if not openai_api_key:
    st.info("OpenAI API Key を入力すると、ページ内容を読んだ高度な診断が表示されます。")

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
                }
            )
            continue

        text = soup.get_text(separator=" ", strip=True)
        text_len = len(text)

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

        has_ld = bool(soup.find("script", {"type": "application/ld+json"}))
        has_h1 = bool(soup.find("h1"))
        struct_score = 50
        if has_ld:
            struct_score += 30
        if has_h1:
            struct_score += 20

        keywords = ["よくある質問", "FAQ", "Q&A", "質問", "How to", "使い方"]
        faq_score = 20
        if any(k.lower() in text.lower() for k in keywords):
            faq_score = 80

        hostname = urlparse(url).hostname or ""
        brand_token = hostname.split(".")[0]
        brand_count = (
            text.lower().count(brand_token.lower()) if brand_token else 0
        )
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
            }
        )

    df = pd.DataFrame(results)
    st.subheader("診断結果")
    st.dataframe(df)

    # ここから下を差し替え

    st.subheader("自動示唆（詳細版）")
    for row in results:
        if row["ステータス"] != "OK":
            st.markdown(
                f"### {row['URL']}\n"
                "- ページ取得に失敗しました。公開設定・URLを確認してください。"
            )
            continue

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

        st.markdown(f"### {row['URL']}")
        table_lines = ["| 観点 | スコア | 評価 | 優先度 |", "| --- | --- | --- | --- |"]
        for k, v in scores.items():
            table_lines.append(f"| {k} | {v} | {level(v)} | {priority(v)} |")
        st.markdown("\n".join(table_lines))

        # 2) 観点別の詳細示唆
        blocks = []

        # 回答性
        if row["回答性"] < 80:
            text_block = [
                "#### 1. 回答性（ユーザーの質問にどこまで答えられているか）",
                "",
                "- 主要な検索ニーズ（「◯◯とは」「◯◯ やり方」「◯◯ 比較」など）に対して、1ページ内で完結して答えられる構成にする。",
                "- 導入文 → 結論 → 詳細解説 → 具体例 → FAQ の順で、情報の深さを段階的に追加する。",
                "- 重要キーワードごとに見出し（H2/H3）を立て、各見出し内で1テーマ1メッセージに絞って解説する。",
            ]
            blocks.append("\n".join(text_block))

        # 構造化
        if row["構造化"] < 80:
            text_block = [
                "#### 2. 構造化・技術的な分かりやすさ",
                "",
                "- schema.org の構造化データ（FAQPage, Article, Product など）を追加し、AI・検索エンジンが情報を機械的に読み取りやすい状態にする。",
                "- H1 はページ全体のテーマを端的に表す1文にし、H2/H3 で論点を階層的に整理する。",
                "- 箇条書き・番号リスト・表などを使い、長文が続かないように視認性を高める。",
            ]
            blocks.append("\n".join(text_block))

        # FAQ / HowTo
        if row["FAQ/HowTo"] < 80:
            text_block = [
                "#### 3. FAQ / HowTo コンテンツ",
                "",
                "- 実際に問い合わせが来ている内容や、営業現場でよく聞かれる質問を洗い出し、そのまま Q&A 化する。",
                "- 「初めての人がつまずくポイント」を想像し、ステップ付きの手順（HowTo）として整理する。",
                "- 1質問1回答で、結論→理由→補足 の順に書くことで、会話型AIから引用されやすい形にする。",
            ]
            blocks.append("\n".join(text_block))

        # ブランド性
        if row["ブランド性"] < 80:
            text_block = [
                "#### 4. ブランド性・信頼性",
                "",
                "- ページ上部でブランド名・サービス名を明示し、「誰が」「何を提供しているページか」をはっきりさせる。",
                "- 受賞歴・導入実績・お客様の声など、信頼を補強する情報を一箇所にまとめて掲載する。",
                "- 会社概要や運営者情報への導線をフッターや本文内に設置し、安心して問い合わせできる状態にする。",
            ]
            blocks.append("\n".join(text_block))

        if not blocks:
            blocks.append(
                "#### 総評\n\n"
                "AIO 観点で一定水準を満たしています。重要キーワードごとに同様の構成のページを増やし、"
                "FAQ・事例・比較コンテンツを横展開すると、AI検索からの評価をさらに高められます。"
            )

        st.markdown("\n\n".join(blocks))
