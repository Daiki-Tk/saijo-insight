
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Saijo Insight", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

RECOMMENDED = [
    {"name": "総人口の推移", "category": "人口", "indicator": "総人口", "region": "西条市"},
    {"name": "世帯数の推移", "category": "人口", "indicator": "世帯数", "region": "西条市"},
    {"name": "出生数と死亡数", "category": "人口", "indicator": "出生数", "region": "西条市"},
    {"name": "事業所数の推移", "category": "産業", "indicator": "事業所数", "region": "西条市"},
    {"name": "従業者数の推移", "category": "産業", "indicator": "従業者数", "region": "西条市"},
    {"name": "製造品出荷額の推移", "category": "産業", "indicator": "製造品出荷額等", "region": "西条市"},
    {"name": "商店数の推移", "category": "産業", "indicator": "商店数", "region": "西条市"},
    {"name": "西条市民所得", "category": "産業", "indicator": "市民所得", "region": "西条市"},
    {"name": "一般会計歳入", "category": "財政", "indicator": "歳入総額", "region": "西条市"},
    {"name": "一般会計歳出", "category": "財政", "indicator": "歳出総額", "region": "西条市"},
]

@st.cache_data
def load_all_data() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        if path.name == "data_catalog.csv":
            continue
        try:
            df = pd.read_csv(path)
            if df.empty:
                continue
            df["__source_file"] = path.name
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    # normalize
    for col in ["dataset_id","category","subcategory","indicator","region","year_label",
                "fiscal_or_calendar","unit","sex","data_kind","source_title","source_table",
                "source_yearbook","source_department","notes","__source_file"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")
    if "value" not in df.columns:
        df["value"] = pd.NA
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if "year_num" not in df.columns:
        df["year_num"] = pd.NA
    df["year_num"] = pd.to_numeric(df["year_num"], errors="coerce")
    if "comparable" not in df.columns:
        df["comparable"] = True
    df["comparable"] = df["comparable"].astype(str).str.lower().isin(["true", "1", "yes"])
    if "sex" not in df.columns:
        df["sex"] = "na"
    df["sex"] = df["sex"].replace("", "na")
    if "data_kind" not in df.columns:
        df["data_kind"] = "actual"
    df["data_kind"] = df["data_kind"].replace("", "actual")
    return df.dropna(subset=["indicator", "year_num", "value"])

@st.cache_data
def load_catalog() -> pd.DataFrame:
    path = DATA_DIR / "data_catalog.csv"
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def format_value(value: float, unit: str) -> str:
    if pd.isna(value):
        return "-"
    if abs(value) >= 1000:
        return f"{value:,.0f}{unit}"
    return f"{value:.1f}{unit}" if isinstance(value, float) and not float(value).is_integer() else f"{value:.0f}{unit}"

def quick_stats(df: pd.DataFrame, indicator: str, region: str = "西条市") -> tuple[str, str, str]:
    s = df[(df["indicator"] == indicator) & (df["region"] == region)].sort_values("year_num")
    if s.empty:
        return "-", "-", "-"
    first = s.iloc[0]
    last = s.iloc[-1]
    delta = last["value"] - first["value"]
    unit = last["unit"]
    pct = f"{(delta/first['value']*100):+.1f}%" if first["value"] not in [0, pd.NA] and pd.notna(first["value"]) else "-"
    return format_value(last["value"], unit), f"{delta:,.0f}{unit}", pct

def render_reading(df: pd.DataFrame) -> None:
    if df.empty or len(df) < 2:
        st.info("読み取り補助を表示するには、2点以上の時系列データが必要です。")
        return
    ordered = df.sort_values("year_num")
    s = ordered["value"].astype(float)
    years = ordered["year_label"].tolist()
    first, last = s.iloc[0], s.iloc[-1]
    delta = last - first
    trend = "増加傾向" if delta > 0 else "減少傾向" if delta < 0 else "横ばい傾向"
    pct = None if first == 0 else delta / first * 100
    diffs = s.diff().dropna()

    lines = []
    if pct is None:
        lines.append(f"- 全期間では **{trend}** です。")
    else:
        lines.append(f"- **{years[0]} → {years[-1]}** で **{delta:,.0f}** 変化しました（{pct:+.1f}%）。")
    lines.append(f"- 全期間の大きな見え方としては **{trend}** と読めます。")

    if not diffs.empty:
        max_pos = diffs.abs().to_numpy().argmax() + 1
        lines.append(f"- 変化幅が最も大きいのは **{years[max_pos-1]} → {years[max_pos]}** です。")
        if diffs.abs().mean() > 0:
            variability = diffs.abs().std() / diffs.abs().mean() if diffs.abs().mean() != 0 else 0
            lines.append("- 変動はやや大きめです。" if variability > 1 else "- 推移は比較的なだらかです。")

    lines.append("- これは読み取り補助です。背景要因や因果関係の判断には、原資料と周辺情報の確認が必要です。")
    st.markdown("\n".join(lines))

def build_chart(df: pd.DataFrame, chart_type: str, color_col: str | None = None):
    if chart_type == "折れ線":
        fig = px.line(df, x="year_num", y="value", color=color_col, markers=True, custom_data=["year_label", "unit", "source_title"])
    elif chart_type == "棒":
        fig = px.bar(df, x="year_num", y="value", color=color_col, barmode="group", custom_data=["year_label", "unit", "source_title"])
    else:
        fig = px.area(df, x="year_num", y="value", color=color_col, custom_data=["year_label", "unit", "source_title"])
    fig.update_traces(hovertemplate="年: %{customdata[0]}<br>値: %{y:,.0f} %{customdata[1]}<br>出典: %{customdata[2]}<extra></extra>")
    fig.update_layout(legend_title_text="")
    return fig

def indicator_options(df: pd.DataFrame, categories: list[str]) -> list[str]:
    if categories:
        return sorted(df[df["category"].isin(categories)]["indicator"].dropna().unique().tolist())
    return sorted(df["indicator"].dropna().unique().tolist())

def main():
    df = load_all_data()
    catalog = load_catalog()

    st.title("Saijo Insight")
    st.caption("西条市統計の探索・比較・理解のためのダッシュボード")

    if df.empty:
        st.error("data ディレクトリにCSVがありません。")
        return

    with st.sidebar:
        st.header("全体フィルタ")
        region = st.selectbox("地域", sorted(df["region"].unique()), index=0)
        year_min = int(df["year_num"].min())
        year_max = int(df["year_num"].max())
        year_range = st.slider("対象年", min_value=year_min, max_value=year_max, value=(year_min, year_max))
        data_kind = st.multiselect("データ種別", sorted(df["data_kind"].unique()), default=sorted(df["data_kind"].unique()))
        strict_only = st.checkbox("厳密比較向けデータのみ", value=False)
        st.caption("年次/年度や単位差のあるデータは、比較前に表の注記も確認してください。")

    f = df[(df["region"] == region) & (df["year_num"].between(year_range[0], year_range[1])) & (df["data_kind"].isin(data_kind))]
    if strict_only:
        f = f[f["comparable"]]

    tab_home, tab_explore, tab_compare, tab_catalog = st.tabs(["ホーム", "探索", "比較", "データカタログ"])

    with tab_home:
        c1, c2, c3 = st.columns(3)
        pop_now, pop_delta, pop_pct = quick_stats(f, "総人口", region)
        offices_now, offices_delta, offices_pct = quick_stats(f, "事業所数", region)
        rev_now, rev_delta, rev_pct = quick_stats(f, "歳入総額", region)
        c1.metric("総人口", pop_now, pop_pct)
        c2.metric("事業所数", offices_now, offices_pct)
        c3.metric("歳入総額", rev_now, rev_pct)

        left, right = st.columns([2.2, 1])
        with left:
            st.subheader("ヒーローグラフ")
            hero = f[(f["indicator"] == "総人口") & (f["category"] == "人口") & (f["sex"].isin(["total", "na"]))].sort_values("year_num")
            if hero.empty:
                st.info("総人口データがありません。")
            else:
                fig = build_chart(hero, "折れ線", None)
                fig.update_layout(title=f"{region}｜総人口の推移", xaxis_title="年", yaxis_title=f"値（{hero['unit'].iloc[0]}）")
                st.plotly_chart(fig, use_container_width=True)
                with st.expander("このグラフの読み取り"):
                    render_reading(hero)
        with right:
            st.subheader("入口テーマ")
            st.markdown("### 👤 人口")
            st.caption("総人口・世帯数・出生死亡・人口動態")
            st.markdown("### 🏭 産業")
            st.caption("事業所・従業者・製造業・商業・市民所得")
            st.markdown("### 💰 財政")
            st.caption("歳入・歳出・税収の推移")
            st.info(f"収録データセット数: {f['dataset_id'].nunique()} / 指標数: {f['indicator'].nunique()}")

        st.subheader("おすすめ分析")
        cols = st.columns(2)
        for idx, rec in enumerate(RECOMMENDED):
            sub = f[(f["category"] == rec["category"]) & (f["indicator"] == rec["indicator"]) & (f["region"] == rec["region"])]
            with cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"**{rec['name']}**")
                    if sub.empty:
                        st.caption("データ未収録")
                    else:
                        latest = sub.sort_values("year_num").iloc[-1]
                        st.caption(f"最新値: {format_value(latest['value'], latest['unit'])}（{latest['year_label']}）")
                        mini = build_chart(sub.sort_values("year_num"), "折れ線", None)
                        mini.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), showlegend=False, title="")
                        st.plotly_chart(mini, use_container_width=True)

    with tab_explore:
        st.subheader("探索")
        top1, top2, top3 = st.columns([1.1, 1.3, 1])
        with top1:
            categories = st.multiselect("カテゴリ", sorted(f["category"].unique()), default=["人口", "産業", "財政"])
        with top2:
            options = indicator_options(f, categories)
            selected_indicator = st.selectbox("指標", options)
        with top3:
            chart_type = st.radio("グラフ形式", ["折れ線", "棒", "面"], horizontal=True)

        subset = f[(f["indicator"] == selected_indicator)]
        if categories:
            subset = subset[subset["category"].isin(categories)]
        if subset.empty:
            st.warning("この条件に合うデータがありません。")
        else:
            color_col = "sex" if subset["sex"].nunique() > 1 else None
            fig = build_chart(subset.sort_values("year_num"), chart_type, color_col)
            unit = subset["unit"].iloc[0] if subset["unit"].nunique() == 1 else "混在"
            fig.update_layout(title=f"{region}｜{selected_indicator}", xaxis_title="年", yaxis_title=f"値（{unit}）")
            st.plotly_chart(fig, use_container_width=True)

            a, b = st.columns([1.4, 1])
            with a:
                with st.expander("このグラフの読み取り", expanded=True):
                    base = subset[subset["sex"].isin(["total", "na"])] if subset["sex"].isin(["total", "na"]).any() else subset
                    render_reading(base)
            with b:
                st.markdown("**データ注記**")
                st.write(f"- データセット: `{subset['dataset_id'].iloc[0]}`")
                st.write(f"- 単位: {', '.join(sorted(subset['unit'].unique()))}")
                st.write(f"- 年の種別: {', '.join(sorted(subset['fiscal_or_calendar'].unique()))}")
                st.write(f"- 出典表: {subset['source_table'].iloc[0]}")
                st.write(f"- 比較適性: {'高' if bool(subset['comparable'].all()) else '要注意'}")

            st.dataframe(
                subset.sort_values(["year_num", "sex"])[
                    ["year_label", "value", "unit", "sex", "data_kind", "fiscal_or_calendar", "source_title", "source_table", "notes", "__source_file"]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab_compare:
        st.subheader("比較")
        st.caption("同じ地域・近い期間の2指標を並べて見るための簡易比較です。相関や因果を断定するものではありません。")
        c1, c2 = st.columns(2)
        with c1:
            indicator_a = st.selectbox("指標A", sorted(f["indicator"].unique()), index=0)
        with c2:
            indicator_b = st.selectbox("指標B", sorted(f["indicator"].unique()), index=min(1, len(sorted(f["indicator"].unique())) - 1))

        a_df = f[(f["indicator"] == indicator_a) & (f["sex"].isin(["total", "na"]))][["year_num", "year_label", "value", "unit"]].rename(columns={"value": "value_a", "unit": "unit_a"})
        b_df = f[(f["indicator"] == indicator_b) & (f["sex"].isin(["total", "na"]))][["year_num", "year_label", "value", "unit"]].rename(columns={"value": "value_b", "unit": "unit_b"})
        merged = pd.merge(a_df, b_df, on=["year_num", "year_label"], how="inner").drop_duplicates().sort_values("year_num")

        if merged.empty:
            st.warning("共通の年が見つからないため、比較できません。")
        else:
            left, right = st.columns(2)
            with left:
                fig_line = px.line(merged, x="year_num", y=["value_a", "value_b"], markers=True)
                fig_line.update_layout(title=f"{indicator_a} と {indicator_b} の並行比較", xaxis_title="年", yaxis_title="値")
                st.plotly_chart(fig_line, use_container_width=True)
            with right:
                fig_scatter = px.scatter(merged, x="value_a", y="value_b", text="year_label")
                fig_scatter.update_traces(textposition="top center")
                fig_scatter.update_layout(title="散布図", xaxis_title=f"{indicator_a}（{merged['unit_a'].iloc[0]}）", yaxis_title=f"{indicator_b}（{merged['unit_b'].iloc[0]}）")
                st.plotly_chart(fig_scatter, use_container_width=True)

            corr = merged["value_a"].corr(merged["value_b"]) if len(merged) >= 2 else None
            st.markdown(f"**相関係数（参考）**: {corr:.3f}" if corr is not None and pd.notna(corr) else "**相関係数（参考）**: 算出不可")
            st.dataframe(merged, use_container_width=True, hide_index=True)

    with tab_catalog:
        st.subheader("データカタログ")
        c1, c2, c3 = st.columns(3)
        c1.metric("CSV数", len(list(DATA_DIR.glob('*.csv'))) - (1 if (DATA_DIR / 'data_catalog.csv').exists() else 0))
        c2.metric("データセット数", f["dataset_id"].nunique())
        c3.metric("指標数", f["indicator"].nunique())

        if not catalog.empty:
            st.dataframe(catalog, use_container_width=True, hide_index=True)

        summary = (
            f.groupby(["category", "dataset_id"], as_index=False)
             .agg(指標数=("indicator", "nunique"), 開始年=("year_num", "min"), 終了年=("year_num", "max"), 地域数=("region", "nunique"))
             .sort_values(["category", "dataset_id"])
        )
        st.markdown("**収録状況一覧**")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        downloadable = f.sort_values(["category", "indicator", "year_num"])
        st.download_button(
            "現在の統合データをCSVでダウンロード",
            downloadable.to_csv(index=False).encode("utf-8-sig"),
            file_name="saijo_insight_integrated.csv",
            mime="text/csv",
        )

    st.caption("注意: 年次/年度、単位、定義が異なる場合があります。比較や解釈の際は各表の注記を確認してください。")

if __name__ == "__main__":
    main()
