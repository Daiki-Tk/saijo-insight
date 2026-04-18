
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Saijo Insight",
    page_icon="📊",
    layout="wide",
)

DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_all_data() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        if path.name == "data_catalog.csv":
            continue
        df = pd.read_csv(path)
        df["__source_file"] = path.name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

@st.cache_data
def load_catalog() -> pd.DataFrame:
    path = DATA_DIR / "data_catalog.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

def render_reading(df: pd.DataFrame, value_col: str = "value") -> None:
    if df.empty or len(df) < 2:
        st.info("読み取り補助を表示するには、2点以上の時系列データが必要です。")
        return

    s = df.sort_values("year_num")[value_col].astype(float)
    years = df.sort_values("year_num")["year_label"].tolist()

    first, last = s.iloc[0], s.iloc[-1]
    delta = last - first
    pct = (delta / first * 100) if first != 0 else None

    diffs = s.diff().dropna()
    trend = "増加傾向" if delta > 0 else "減少傾向" if delta < 0 else "横ばい傾向"

    lines = []
    if pct is None:
        lines.append(f"- 全期間では **{trend}** です。")
    else:
        lines.append(f"- **{years[0]} → {years[-1]}** で **{delta:,.0f}** 変化しました（{pct:+.1f}%）。")

    if not diffs.empty:
        max_jump_idx = diffs.abs().idxmax()
        jump_row = df.sort_values("year_num").loc[max_jump_idx]
        lines.append(
            f"- 年ごとの変化幅がもっとも大きいのは **{jump_row['year_label']}** 付近です。"
        )
        if diffs.std() > 0 and diffs.abs().mean() > 0:
            variability = diffs.abs().std() / diffs.abs().mean()
            if variability > 1:
                lines.append("- 推移は比較的なだらかではなく、変動がやや大きめです。")
            else:
                lines.append("- 推移は比較的なだらかです。")

    lines.append("- これは読み取り補助です。背景要因や因果関係の判断には原資料の確認が必要です。")
    st.markdown("\n".join(lines))

def main() -> None:
    df = load_all_data()
    catalog = load_catalog()

    st.title("Saijo Insight")
    st.caption("西条市統計の探索・比較・理解のためのスターター版")

    if df.empty:
        st.error("data ディレクトリにCSVがありません。")
        return

    left, right = st.columns([2.2, 1])
    with left:
        st.subheader("ヒーローグラフ")
        hero = df[
            (df["category"] == "人口")
            & (df["indicator"] == "総人口")
            & (df["region"] == "西条市")
            & (df["data_kind"] == "actual")
        ].sort_values("year_num")
        fig = px.line(
            hero,
            x="year_num",
            y="value",
            markers=True,
            title="西条市 総人口の推移",
            labels={"year_num": "年", "value": "人口（人）"},
            custom_data=["year_label", "source_title"],
        )
        fig.update_traces(
            hovertemplate="年: %{customdata[0]}<br>人口: %{y:,.0f}人<br>出典: %{customdata[1]}<extra></extra>"
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("入口")
        st.markdown("### 👤 人口")
        st.markdown("総人口・世帯数・年齢別人口など")
        st.markdown("### 🏭 産業")
        st.markdown("事業所・就業者・製造業・商業など")
        st.markdown("### 💰 財政")
        st.markdown("歳入歳出・財政指標・推計など")
        st.info("このスターター版では人口データを先行収録しています。")

    st.divider()

    st.subheader("分析ページ")
    col1, col2, col3, col4 = st.columns([1.2, 1.2, 1, 1])
    with col1:
        categories = st.multiselect("カテゴリ", sorted(df["category"].dropna().unique()), default=["人口"])
    with col2:
        indicators = sorted(df[df["category"].isin(categories)]["indicator"].dropna().unique()) if categories else sorted(df["indicator"].dropna().unique())
        selected_indicator = st.selectbox("指標", indicators)
    with col3:
        data_kind = st.selectbox("データ種別", ["actual", "projection", "actual + projection"])
    with col4:
        regions = sorted(df["region"].dropna().unique())
        region = st.selectbox("地域", regions)

    filtered = df[(df["indicator"] == selected_indicator) & (df["region"] == region)]
    if categories:
        filtered = filtered[filtered["category"].isin(categories)]

    if data_kind == "actual":
        filtered = filtered[filtered["data_kind"] == "actual"]
    elif data_kind == "projection":
        filtered = filtered[filtered["data_kind"] == "projection"]

    filtered = filtered.sort_values("year_num")

    if filtered.empty:
        st.warning("この条件に合うデータがありません。")
    else:
        chart_type = st.radio("グラフ形式", ["折れ線", "棒"], horizontal=True)
        if chart_type == "折れ線":
            fig2 = px.line(filtered, x="year_num", y="value", color="sex", markers=True)
        else:
            fig2 = px.bar(filtered, x="year_num", y="value", color="sex", barmode="group")
        fig2.update_layout(title=f"{region}｜{selected_indicator}")
        st.plotly_chart(fig2, use_container_width=True)

        with st.expander("このグラフの読み取り"):
            render_reading(filtered[filtered["sex"] == "total"] if "total" in filtered["sex"].unique() else filtered)

        st.dataframe(
            filtered[
                [
                    "year_label", "value", "unit", "sex", "data_kind",
                    "fiscal_or_calendar", "source_title", "source_table", "notes"
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    st.subheader("おすすめ分析（初期サンプル）")
    st.markdown(
        """
        - 総人口の推移  
        - 世帯数の推移  
        - 男女人口の差の推移  
        - 将来人口推計（今後データ追加）  
        - 人口 × 財政（今後データ追加）  
        - 事業所数 × 就業者数（今後データ追加）  
        """
    )

    st.divider()

    st.subheader("データカタログ")
    if catalog.empty:
        st.info("data_catalog.csv に定義を追加すると、ここに一覧表示されます。")
    else:
        st.dataframe(catalog, use_container_width=True, hide_index=True)

    st.caption("注意: このスターター版は厳密比較を優先し、追加データはCSV整備後に反映する前提です。")

if __name__ == "__main__":
    main()
