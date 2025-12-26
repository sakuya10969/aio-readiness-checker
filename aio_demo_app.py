import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

from config import endpoint, deployment, subscription_key
from extractor import extract_important_sections
from scorer import calculate_scores
from analyzer import analyze_page_with_llm, analyze_domain_with_llm, get_llm_scores


# ===== Streamlit アプリ本体 =====
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
                    "Crawl/Index健全性": 0,
                    "回答性": 0,
                    "FAQ/HowTo": 0,
                    "E-E-A-T": 0,
                    "構造化データ": 0,
                    "コンテンツ一貫性": 0,
                    "本文要約": "",
                }
            )
            continue

        # ページ本文（全文）
        full_text = soup.get_text(separator=" ", strip=True)

        # AIO観点で重要な部分だけ抽出（見出し＋直後の段落）
        important_text = extract_important_sections(soup)

        # LLMによるスコア判定（オプション）
        llm_scores = {}
        if subscription_key and endpoint and deployment:
            try:
                llm_scores = get_llm_scores(url, important_text)
            except Exception:
                # LLMエラー時はルールベースのみで継続
                pass

        # スコア計算（ルールベース70% + LLM判定30%）
        scores = calculate_scores(url, soup, full_text, llm_scores)

        results.append(
            {
                "URL": url,
                "ステータス": "OK",
                "総合スコア": scores["総合スコア"],
                "Crawl/Index健全性": scores["Crawl/Index健全性"],
                "回答性": scores["回答性"],
                "FAQ/HowTo": scores["FAQ/HowTo"],
                "E-E-A-T": scores["E-E-A-T"],
                "構造化データ": scores["構造化データ"],
                "コンテンツ一貫性": scores["コンテンツ一貫性"],
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

- **総合スコア**：下記6つの観点を総合した「AI検索時代にどれだけ対応できているか」の目安です。
- **Crawl/Index健全性**：title/description、noindex、canonical、重複など、検索エンジンがページを正しく認識・インデックスできるかを評価します。
- **回答性**：見出し構造（H1/H2）、要点サマリ、定義文、箇条書きなど、AIが引用しやすい構造になっているかを評価します。会話型AIが引用する際の"答えの質"に直結します。
- **FAQ/HowTo**：Q&Aや手順コンテンツの充実度。LLMが回答生成時に最も参照しやすい形式であり、AI推奨に乗りやすい領域です。
- **E-E-A-T**：著者/運営者情報、問い合わせ、会社情報、更新日、参照リンクなど、信頼性を示す要素の充実度。AIが「信頼できる情報源」と判断するかどうかに関わる指標です。
- **構造化データ**：Schema.org（FAQPage/HowTo/Product/Article/Breadcrumb等）の有無。AIや検索エンジンがページ内容を機械的に理解できるかを左右します。
- **コンテンツ一貫性**：同一テーマでの網羅性、コンテンツの厚み。AIが包括的な回答を生成できるかを評価します。
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
        scores_dict = {
            "Crawl/Index健全性": row.get("Crawl/Index健全性", 0),
            "回答性": row["回答性"],
            "FAQ/HowTo": row["FAQ/HowTo"],
            "E-E-A-T": row.get("E-E-A-T", 0),
            "構造化データ": row.get("構造化データ", 0),
            "コンテンツ一貫性": row.get("コンテンツ一貫性", 0),
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
        for k, v in scores_dict.items():
            table_lines.append(f"| {k} | {v} | {level(v)} | {priority(v)} |")
        st.markdown("\n".join(table_lines))

        # 2) このURL専用の改善レポートをLLMに書かせる
        # Azure OpenAI連携、APIキー欄なしで必ず実施
        if subscription_key and endpoint and deployment:
            llm_report = analyze_page_with_llm(
                row["URL"], row.get("本文要約", ""), scores_dict
            )
            st.markdown(llm_report)
        else:
            st.info(
                "Azure OpenAI のAPI情報が環境変数に設定されていません。正しいAPIキー情報(.env)をセットしてください。"
            )

    # -------------------------
    # ドメイン全体の分析（複数URLの場合）
    # -------------------------
    if len(results) > 1:
        st.subheader("ドメイン全体の分析")
        if subscription_key and endpoint and deployment:
            domain_report = analyze_domain_with_llm(results)
            st.markdown(domain_report)
        else:
            st.info(
                "Azure OpenAI のAPI情報が設定されていないため、ドメイン全体の分析はスキップされます。"
            )
