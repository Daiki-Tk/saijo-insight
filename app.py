
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Saijo Insight", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_all_data() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        if path.name == "data_catalog.csv":
            continue
        try:
            df = pd.read_csv(path)
            df["__source_file"] = path.name
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    # 型の最低限の補正
    if "year_num" in df.columns:
        df["year_num"] = pd.to_numeric(df["year_num"], errors="coerce")
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df

@st.cache_data
def load_catalog() -> pd.DataFrame:
    path = DATA_DIR / "data_catalog.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

def format_value(value, unit="") -> str:
    if pd.isna(value):
        return "-"
    try:
        value = float(value)
    except Exception:
        return f"{value}{unit}"
    return f"{value:.1f}{unit}" if not value.is_integer() else f"{value:.0f}{unit}"

def quick_stats(df: pd.DataFrame, indicator: str, region: str = "西条市") -> tuple[str, str, str]:
    s = df[(df["indicator"] == indicator) & (df["region"] == region)].copy()
    s = s.dropna(subset=["year_num", "value"]).sort_values("year_num")
    if s.empty:
        return "-", "-", "-"
    first = s.iloc[0]
    last = s.iloc[-1]
    delta = last["value"] - first["value"]
    unit = last.get("unit", "")
    first_value = first["value"]
    if pd.notna(first_value) and first_value != 0:
        pct = f"{(delta / first_value * 100):+.1f}%"
    else:
        pct = "-"
    return format_value(last["value"], unit), f"{delta:,.0f}{unit}", pct

def render_reading(df: pd.DataFrame) -> None:
    if df.empty or len(df) < 2:
        st.info("読み取り補助を表示するには、2点以上の時系列データが必要です。")
        return

    ordered = df.dropna(subset=["year_num", "value"]).sort_values("year_num")
    if len(ordered) < 2:
        st.info("有効な時系列データが不足しています。")
        return

    s = ordered["value"].astype(float)
    years = ordered["year_label"].astype(str).tolist()
    first, last = s.iloc[0], s.iloc[-1]
    delta = last - first
    trend = "増加傾向" if delta > 0 else "減少傾向" if delta < 0 else "横ばい傾向"
    pct = None if first == 0 else delta / first * 100
    diffs = s.diff().dropna()

    lines = [f"- 全体として **{trend}** です。"]
    if pct is None:
        lines.append(f"- **{years[0]} → {years[-1]}** で **{delta:,.0f}** 変化しました。")
    else:
        lines.append(f"- **{years[0]} → {years[-1]}** で **{delta:,.0f}** 変化しました（{pct:+.1f}%）。")

    if not diffs.empty:
        max_jump_idx = diffs.abs().idxmax()
        jump_year = ordered.loc[max_jump_idx, "year_label"]
        lines.append(f"- 変化幅が大きい時点は **{jump_year}** 付近です。")
        if diffs.abs().mean() > 0:
            variability = diffs.abs().std() / diffs.abs().mean() if diffs.abs().mean() != 0 else 0
            lines.append("- 推移は比較的なだらかです。" if variability <= 1 else "- 推移の変動はやや大きめです。")

    lines.append("- これは読み取り補助です。背景要因や因果関係の判断には原資料の確認が必要です。")
    st.markdown("\n".join(lines))

def get_series(df: pd.DataFrame, indicator: str, region: str = "西条市") -> pd.DataFrame:
    out = df[(df["indicator"] == indicator) & (df["region"] == region)].copy()
    out = out.dropna(subset=["year_num", "value"]).sort_values("year_num")
    return out

def main() -> None:
    f = load_all_data()
    catalog = load_catalog()

    st.title("Saijo Insight")
    st.caption("西条市統計の探索・比較・理解のためのダッシュボード")

    if f.empty:
        st.error("data ディレクトリにCSVがありません。")
        return

    region = "西条市"
    tab_home, tab_explore, tab_compare, tab_catalog = st.tabs(["ホーム", "探索", "比較", "データカタログ"])

    with tab_home:
        c1, c2, c3 = st.columns(3)
        pop_now, pop_delta, pop_pct = quick_stats(f, "総人口", region)
        offices_now, offices_delta, offices_pct = quick_stats(f, "事業所数", region)
        revenue_now, revenue_delta, revenue_pct = quick_stats(f, "歳入総額", region)

        c1.metric("総人口", pop_now, f"{pop_delta} / {pop_pct}")
        c2.metric("事業所数", offices_now, f"{offices_delta} / {offices_pct}")
        c3.metric("歳入総額", revenue_now, f"{revenue_delta} / {revenue_pct}")

        st.subheader("ヒーローグラフ")
        hero = get_series(f, "総人口", region)
        if not hero.empty:
            fig = px.line(
                hero,
                x="year_num",
                y="value",
                markers=True,
                title="西条市 総人口の推移",
                labels={"year_num": "年", "value": "人口"},
                custom_data=["year_label", "source_title"],
            )
            fig.update_traces(
                hovertemplate="年: %{customdata[0]}<br>値: %{y:,.0f}<br>出典: %{customdata[1]}<extra></extra>"
            )
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("このグラフの読み取り"):
                render_reading(hero)

        st.subheader("おすすめ分析")
        rec1, rec2 = st.columns(2)
        with rec1:
            st.info("人口の推移")
            st.write("総人口、世帯数、人口動態をたどる入口です。")
        with rec2:
            st.info("産業と人口の比較")
            st.write("事業所数や従業者数と人口の関係を確認できます。")

    with tab_explore:
        st.subheader("探索")
        categories = sorted(f["category"].dropna().astype(str).unique())
        col1, col2, col3, col4 = st.columns([1.1, 1.4, 1, 1])
        with col1:
            selected_category = st.selectbox("カテゴリ", categories)
        with col2:
            indicators = sorted(f[f["category"] == selected_category]["indicator"].dropna().astype(str).unique())
            selected_indicator = st.selectbox("指標", indicators)
        with col3:
            chart_type = st.selectbox("グラフ形式", ["折れ線", "棒"])
        with col4:
            sex_options = sorted(f[(f["category"] == selected_category) & (f["indicator"] == selected_indicator)]["sex"].dropna().astype(str).unique())
            selected_sex = st.selectbox("区分", sex_options if sex_options else ["na"])

        filtered = f[(f["category"] == selected_category) & (f["indicator"] == selected_indicator)].copy()
        if "sex" in filtered.columns:
            filtered = filtered[filtered["sex"].astype(str) == selected_sex]
        filtered = filtered.dropna(subset=["year_num", "value"]).sort_values("year_num")

        if filtered.empty:
            st.warning("この条件に合うデータがありません。")
        else:
            if chart_type == "折れ線":
                fig2 = px.line(filtered, x="year_num", y="value", markers=True)
            else:
                fig2 = px.bar(filtered, x="year_num", y="value")
            unit = filtered["unit"].iloc[0] if "unit" in filtered.columns and not filtered.empty else ""
            fig2.update_layout(title=f"{selected_indicator}", xaxis_title="年", yaxis_title=f"値（{unit}）")
            st.plotly_chart(fig2, use_container_width=True)

            with st.expander("このグラフの読み取り"):
                render_reading(filtered)

            show_cols = [c for c in ["year_label", "value", "unit", "sex", "data_kind", "fiscal_or_calendar", "source_title", "source_table", "notes"] if c in filtered.columns]
            st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

    with tab_compare:
        st.subheader("比較")
        indicators = sorted(f["indicator"].dropna().astype(str).unique())
        left_sel, right_sel = st.columns(2)
        with left_sel:
            indicator_a = st.selectbox("指標A", indicators, index=0)
        with right_sel:
            default_b = 1 if len(indicators) > 1 else 0
            indicator_b = st.selectbox("指標B", indicators, index=default_b)

        df1 = get_series(f, indicator_a, region)[["year_num", "year_label", "value", "unit"]].copy()
        df2 = get_series(f, indicator_b, region)[["year_num", "year_label", "value", "unit"]].copy()

        if df1.empty or df2.empty:
            st.warning("比較できるデータが不足しています。")
        else:
            merged = pd.merge(
                df1,
                df2,
                on="year_num",
                how="inner",
                suffixes=("_a", "_b"),
            )
            if "year_label_a" not in merged.columns and "year_label" in merged.columns:
                merged["year_label_a"] = merged["year_label"]
            if "year_label_b" not in merged.columns and "year_label" in merged.columns:
                merged["year_label_b"] = merged["year_label"]

            merged = merged.dropna(subset=["value_a", "value_b"]).sort_values("year_num")

            if merged.empty:
                st.warning("共通年のデータがありません。")
            else:
                left, right = st.columns(2)

                with left:
                    line_df = merged[["year_num", "year_label_a", "value_a", "value_b"]].copy()
                    line_df = line_df.rename(columns={"year_label_a": "year_label"})
                    line_long = line_df.melt(
                        id_vars=["year_num", "year_label"],
                        value_vars=["value_a", "value_b"],
                        var_name="series",
                        value_name="value",
                    )
                    line_long["series"] = line_long["series"].map({"value_a": indicator_a, "value_b": indicator_b})

                    fig_line = px.line(
                        line_long,
                        x="year_num",
                        y="value",
                        color="series",
                        markers=True,
                        hover_data=["year_label"],
                    )
                    fig_line.update_layout(
                        title=f"{indicator_a} と {indicator_b} の並行比較",
                        xaxis_title="年",
                        yaxis_title="値",
                    )
                    st.plotly_chart(fig_line, use_container_width=True)

                with right:
                    fig_scatter = px.scatter(
                        merged,
                        x="value_a",
                        y="value_b",
                        text="year_label_a",
                        trendline="ols" if len(merged) >= 2 else None,
                    )
                    fig_scatter.update_traces(textposition="top center")
                    unit_a = merged["unit_a"].iloc[0] if "unit_a" in merged.columns and len(merged) else ""
                    unit_b = merged["unit_b"].iloc[0] if "unit_b" in merged.columns and len(merged) else ""
                    fig_scatter.update_layout(
                        title="散布図",
                        xaxis_title=f"{indicator_a}（{unit_a}）",
                        yaxis_title=f"{indicator_b}（{unit_b}）",
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)

                corr = merged["value_a"].corr(merged["value_b"]) if len(merged) >= 2 else None
                if corr is not None and pd.notna(corr):
                    st.markdown(f"**相関係数（参考）**: {corr:.3f}")
                else:
                    st.markdown("**相関係数（参考）**: -")

                if len(merged) < 3:
                    st.warning("データ点が少ないため、相関は参考値です。")

                st.dataframe(merged, use_container_width=True, hide_index=True)

    with tab_catalog:
        st.subheader("データカタログ")
        c1, c2, c3 = st.columns(3)
        csv_count = len(list(DATA_DIR.glob("*.csv"))) - (1 if (DATA_DIR / "data_catalog.csv").exists() else 0)
        c1.metric("CSV数", csv_count)
        c2.metric("データセット数", int(f["dataset_id"].nunique()) if "dataset_id" in f.columns else 0)
        c3.metric("指標数", int(f["indicator"].nunique()) if "indicator" in f.columns else 0)

        if catalog.empty:
            st.info("data_catalog.csv がまだ整っていません。")
        else:
            st.dataframe(catalog, use_container_width=True, hide_index=True)

        st.subheader("収録ファイル一覧")
        files_df = pd.DataFrame({
            "file_name": [p.name for p in sorted(DATA_DIR.glob("*.csv")) if p.name != "data_catalog.csv"]
        })
        st.dataframe(files_df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
