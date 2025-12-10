import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import pandas as pd

st.set_page_config(page_title="AIO Readiness Checker Demo", layout="wide")

st.title("AIO Readiness Checker（デモ版）")
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

    st.subheader("自動示唆（簡易版）")
    for row in results:
        if row["ステータス"] != "OK":
            st.markdown(
                f"### {row['URL']}\n"
                "- ページ取得に失敗しました。公開設定・URLを確認してください。"
            )
            continue

    suggestions = []
    if row["回答性"] < 60:
        suggestions.append(
            "・テキスト量が不足しています。FAQやHowTo、詳細説明を追加し、ユーザーの質問に1ページで答えきれる構成にしましょう。"
        )
    if row["構造化"] < 80:
        suggestions.append(
            "・構造化データ（schema.org, FAQPage, Product等）と見出しタグ（H1/H2）を整備し、AI・検索エンジンが理解しやすいページにしましょう。"
        )
    if row["FAQ/HowTo"] < 60:
        suggestions.append(
            "・「よくある質問」「使い方」などのFAQ/HowToコンテンツを拡充し、会話型AIから引用されやすい情報を増やしましょう。"
        )
    if row["ブランド性"] < 60:
        suggestions.append(
            "・ブランド名・商品名をページ内で適切に言及し、ブランド指名検索からの評価を高めましょう。"
        )

    if not suggestions:
        suggestions.append(
            "・AIO観点で一定水準を満たしています。重要キーワードごとに同様の構成のページを増やすとさらに効果が期待できます。"
        )

    st.markdown(f"### {row['URL']}\n" + "\n".join(suggestions))
