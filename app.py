
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Saijo Insight", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

MONEY_UNITS = {"円": 1, "千円": 1_000, "万円": 10_000, "百万円": 1_000_000}
SEX_PRIORITY = ["total", "na", "male", "female"]

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

    for col in ["year_num", "value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["category", "subcategory", "indicator", "region", "unit", "sex", "data_kind", "year_label"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    return df

@st.cache_data
def load_catalog() -> pd.DataFrame:
    path = DATA_DIR / "data_catalog.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

def select_default_sex(values: list[str]) -> str:
    for candidate in SEX_PRIORITY:
        if candidate in values:
            return candidate
    return values[0] if values else "na"

def sex_label(value: str) -> str:
    mapping = {
        "total": "総数",
        "na": "区分なし",
        "male": "男性",
        "female": "女性",
    }
    return mapping.get(value, value)

def to_japanese_data_kind(value: str) -> str:
    return {"actual": "実績", "projection": "推計"}.get(value, value)

def normalize_unit(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    if out.empty or "unit" not in out.columns:
        out["display_value"] = out.get("value", pd.Series(dtype=float))
        out["display_unit"] = ""
        return out, ""

    units = [u for u in out["unit"].dropna().unique().tolist() if u]
    if len(units) != 1:
        out["display_value"] = out["value"]
        out["display_unit"] = out["unit"]
        return out, ""

    unit = units[0]
    out["display_value"] = out["value"]
    out["display_unit"] = unit

    if unit in MONEY_UNITS:
        yen = out["value"] * MONEY_UNITS[unit]
        max_abs = yen.abs().max() if len(yen) else 0

        if max_abs >= 100_000_000:
            out["display_value"] = yen / 100_000_000
            out["display_unit"] = "億円"
        elif max_abs >= 10_000:
            out["display_value"] = yen / 10_000
            out["display_unit"] = "万円"
        else:
            out["display_value"] = yen
            out["display_unit"] = "円"

    return out, out["display_unit"].iloc[0] if len(out) else ""

def format_value(value, unit="") -> str:
    if pd.isna(value):
        return "-"
    try:
        value = float(value)
    except Exception:
        return f"{value}{unit}"
    if abs(value) >= 1000:
        return f"{value:,.0f}{unit}" if value.is_integer() else f"{value:,.1f}{unit}"
    return f"{value:.0f}{unit}" if value.is_integer() else f"{value:.1f}{unit}"

def get_series(df: pd.DataFrame, indicator: str, region: str = "西条市", sex: str | None = None) -> pd.DataFrame:
    out = df[(df["indicator"] == indicator) & (df["region"] == region)].copy()
    out = out.dropna(subset=["year_num", "value"])
    if out.empty:
        return out

    if sex is None and "sex" in out.columns:
        sex_values = [v for v in out["sex"].dropna().astype(str).unique().tolist() if v]
        sex = select_default_sex(sex_values)

    if sex is not None and "sex" in out.columns:
        out = out[out["sex"].astype(str) == sex]

    return out.sort_values("year_num")

def quick_stats(df: pd.DataFrame, indicator: str, region: str = "西条市") -> tuple[str, str, str]:
    s = get_series(df, indicator, region)
    if s.empty:
        return "-", "-", "-"

    s, unit = normalize_unit(s)
    first = s.iloc[0]
    last = s.iloc[-1]
    delta = last["display_value"] - first["display_value"]
    first_value = first["display_value"]

    if pd.notna(first_value) and first_value != 0:
        pct = f"{(delta / first_value * 100):+.1f}%"
    else:
        pct = "-"

    return format_value(last["display_value"], unit), f"{delta:,.1f}{unit}" if not float(delta).is_integer() else f"{delta:,.0f}{unit}", pct

def render_reading(df: pd.DataFrame) -> None:
    if df.empty or len(df) < 2:
        st.info("読み取り補助を表示するには、2点以上の時系列データが必要です。")
        return

    ordered = df.dropna(subset=["year_num", "value"]).sort_values("year_num")
    if len(ordered) < 2:
        st.info("有効な時系列データが不足しています。")
        return

    ordered, unit = normalize_unit(ordered)

    s = ordered["display_value"].astype(float)
    years = ordered["year_label"].astype(str).tolist()
    first, last = s.iloc[0], s.iloc[-1]
    delta = last - first
    trend = "増加傾向" if delta > 0 else "減少傾向" if delta < 0 else "横ばい傾向"
    pct = None if first == 0 else delta / first * 100
    diffs = s.diff().dropna()

    lines = [f"- 全体として **{trend}** です。"]
    if pct is None:
        lines.append(f"- **{years[0]} → {years[-1]}** で **{format_value(delta, unit)}** 変化しました。")
    else:
        lines.append(f"- **{years[0]} → {years[-1]}** で **{format_value(delta, unit)}** 変化しました（{pct:+.1f}%）。")

    if not diffs.empty:
        max_jump_idx = diffs.abs().idxmax()
        jump_year = ordered.loc[max_jump_idx, "year_label"]
        lines.append(f"- 変化幅が大きい時点は **{jump_year}** 付近です。")
        if diffs.abs().mean() > 0:
            variability = diffs.abs().std() / diffs.abs().mean() if diffs.abs().mean() != 0 else 0
            lines.append("- 推移は比較的なだらかです。" if variability <= 1 else "- 推移の変動はやや大きめです。")

    min_year = int(ordered["year_num"].min())
    max_year = int(ordered["year_num"].max())
    lines.append(f"- このグラフで使っている収録範囲は **{min_year}年〜{max_year}年** です。")
    lines.append("- これは読み取り補助です。背景要因や因果関係の判断には原資料の確認が必要です。")
    st.markdown("\n".join(lines))

def apply_axis_style(fig, y_title: str = "値"):
    fig.update_xaxes(tickmode="linear", dtick=1, tickformat="d", title="年")
    fig.update_yaxes(title=y_title)
    return fig

def series_period_text(df: pd.DataFrame) -> str:
    if df.empty:
        return "収録期間: -"
    min_year = int(df["year_num"].min())
    max_year = int(df["year_num"].max())
    return f"収録期間: {min_year}年〜{max_year}年"

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
        revenue_now, revenue_delta, revenue_pct = quick_stats(f, "一般会計歳入合計", region)

        c1.metric("総人口", pop_now, f"{pop_delta} / {pop_pct}")
        c2.metric("事業所数", offices_now, f"{offices_delta} / {offices_pct}")
        c3.metric("一般会計歳入合計", revenue_now, f"{revenue_delta} / {revenue_pct}")

        st.subheader("ヒーローグラフ")
        hero = get_series(f, "総人口", region, sex="total")
        if hero.empty:
            hero = get_series(f, "総人口", region)
        if not hero.empty:
            hero, display_unit = normalize_unit(hero)
            fig = px.line(
                hero,
                x="year_num",
                y="display_value",
                markers=True,
                title="西条市 総人口の推移",
                labels={"display_value": f"人口（{display_unit or '人'}）"},
                custom_data=["year_label", "source_title", "value", "unit"],
            )
            fig.update_traces(
                hovertemplate="年: %{customdata[0]}<br>値: %{customdata[2]:,.0f}%{customdata[3]}<br>出典: %{customdata[1]}<extra></extra>"
            )
            apply_axis_style(fig, f"人口（{display_unit or '人'}）")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(series_period_text(hero))
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
        categories = sorted([c for c in f["category"].dropna().astype(str).unique().tolist() if c])
        col1, col2, col3, col4 = st.columns([1.1, 1.6, 1, 1.1])

        with col1:
            selected_category = st.selectbox("カテゴリ", categories)

        with col2:
            indicators = sorted([i for i in f[f["category"] == selected_category]["indicator"].dropna().astype(str).unique().tolist() if i])
            selected_indicator = st.selectbox("指標", indicators)

        dataset_options = sorted(
            f[(f["category"] == selected_category) & (f["indicator"] == selected_indicator) & (f["dataset_id"] == selected_dataset)]["dataset_id"].dropna().unique()
        )

        selected_dataset = st.selectbox("データセット", dataset_options)
        
        base_filtered = f[(f["category"] == selected_category) & (f["indicator"] == selected_indicator)].copy()
        sex_options = [s for s in base_filtered["sex"].dropna().astype(str).unique().tolist() if s]
        default_sex = select_default_sex(sex_options)

        with col3:
            chart_type = st.selectbox("グラフ形式", ["折れ線", "棒"])

        with col4:
            selected_sex = st.selectbox("区分", [sex_label(s) for s in sex_options], index=[sex_label(s) for s in sex_options].index(sex_label(default_sex)) if sex_options else 0)

        reverse_sex_map = {sex_label(s): s for s in sex_options}
        selected_sex_raw = reverse_sex_map.get(selected_sex, default_sex)

        filtered = get_series(base_filtered, selected_indicator, region, sex=selected_sex_raw)
        filtered, display_unit = normalize_unit(filtered)

        if filtered.empty:
            st.warning("この条件に合うデータがありません。")
        else:
            if chart_type == "折れ線":
                fig2 = px.line(
                    filtered,
                    x="year_num",
                    y="display_value",
                    markers=True,
                    hover_data=["year_label", "value", "unit", "source_title"],
                )
            else:
                fig2 = px.bar(
                    filtered,
                    x="year_num",
                    y="display_value",
                    hover_data=["year_label", "value", "unit", "source_title"],
                )

            fig2.update_layout(title=f"{selected_indicator}")
            apply_axis_style(fig2, f"値（{display_unit or filtered['unit'].iloc[0]}）")
            st.plotly_chart(fig2, use_container_width=True)
            st.caption(f"{series_period_text(filtered)} / 区分: {sex_label(selected_sex_raw)}")

            with st.expander("このグラフの読み取り"):
                render_reading(filtered)

            view = filtered.copy()
            view["区分"] = view["sex"].map(sex_label)
            view["データ種別"] = view["data_kind"].map(to_japanese_data_kind)
            show_cols = {
                "year_label": "年表示",
                "value": "原値",
                "unit": "原単位",
                "display_value": "表示値",
                "display_unit": "表示単位",
                "区分": "区分",
                "データ種別": "データ種別",
                "fiscal_or_calendar": "年種別",
                "source_title": "出典",
                "source_table": "表",
                "notes": "備考",
            }
            use_cols = [c for c in show_cols.keys() if c in view.columns]
            st.dataframe(view[use_cols].rename(columns=show_cols), use_container_width=True, hide_index=True)

    with tab_compare:
        st.subheader("比較")
        indicators = sorted([i for i in f["indicator"].dropna().astype(str).unique().tolist() if i])
        left_sel, right_sel = st.columns(2)

        with left_sel:
            indicator_a = st.selectbox("指標A", indicators, index=0)

        with right_sel:
            default_b = 1 if len(indicators) > 1 else 0
            indicator_b = st.selectbox("指標B", indicators, index=default_b)

        df1 = get_series(f, indicator_a, region)
        df2 = get_series(f, indicator_b, region)

        if df1.empty or df2.empty:
            st.warning("比較できるデータが不足しています。")
        else:
            merged = pd.merge(
                df1[["year_num", "year_label", "value", "unit"]],
                df2[["year_num", "year_label", "value", "unit"]],
                on="year_num",
                how="inner",
                suffixes=("_a", "_b"),
            ).dropna(subset=["value_a", "value_b"]).sort_values("year_num")

            if merged.empty:
                st.warning("共通年のデータがありません。")
            else:
                merged["display_value_a"] = merged["value_a"]
                merged["display_value_b"] = merged["value_b"]
                unit_a = merged["unit_a"].iloc[0]
                unit_b = merged["unit_b"].iloc[0]

                if unit_a in MONEY_UNITS:
                    yen_a = merged["value_a"] * MONEY_UNITS[unit_a]
                    if yen_a.abs().max() >= 100_000_000:
                        merged["display_value_a"] = yen_a / 100_000_000
                        unit_a = "億円"
                    elif yen_a.abs().max() >= 10_000:
                        merged["display_value_a"] = yen_a / 10_000
                        unit_a = "万円"

                if unit_b in MONEY_UNITS:
                    yen_b = merged["value_b"] * MONEY_UNITS[unit_b]
                    if yen_b.abs().max() >= 100_000_000:
                        merged["display_value_b"] = yen_b / 100_000_000
                        unit_b = "億円"
                    elif yen_b.abs().max() >= 10_000:
                        merged["display_value_b"] = yen_b / 10_000
                        unit_b = "万円"

                left, right = st.columns(2)

                with left:
                    line_df = merged[["year_num", "year_label_a", "display_value_a", "display_value_b"]].copy()
                    line_df = line_df.rename(columns={"year_label_a": "year_label"})
                    line_long = line_df.melt(
                        id_vars=["year_num", "year_label"],
                        value_vars=["display_value_a", "display_value_b"],
                        var_name="series",
                        value_name="value",
                    )
                    line_long["series"] = line_long["series"].map({"display_value_a": indicator_a, "display_value_b": indicator_b})

                    fig_line = px.line(
                        line_long,
                        x="year_num",
                        y="value",
                        color="series",
                        markers=True,
                        hover_data=["year_label"],
                    )
                    fig_line.update_layout(title=f"{indicator_a} と {indicator_b} の並行比較")
                    apply_axis_style(fig_line, "値")
                    st.plotly_chart(fig_line, use_container_width=True)

                with right:
                    trendline_arg = "ols" if len(merged) >= 3 else None
                    fig_scatter = px.scatter(
                        merged,
                        x="display_value_a",
                        y="display_value_b",
                        text="year_label_a",
                        trendline=trendline_arg,
                        hover_data=["year_num", "value_a", "unit_a", "value_b", "unit_b"],
                    )
                    fig_scatter.update_traces(textposition="top center")
                    fig_scatter.update_layout(
                        title="散布図",
                        xaxis_title=f"{indicator_a}（{unit_a}）",
                        yaxis_title=f"{indicator_b}（{unit_b}）",
                    )
                    fig_scatter.update_xaxes(tickformat=",.0f")
                    fig_scatter.update_yaxes(tickformat=",.0f")
                    st.plotly_chart(fig_scatter, use_container_width=True)

                corr = merged["value_a"].corr(merged["value_b"]) if len(merged) >= 2 else None
                if corr is not None and pd.notna(corr):
                    st.markdown(f"**相関係数（参考）**: {corr:.3f}")
                    if abs(corr) >= 0.7:
                        st.success("強い相関があります。")
                    elif abs(corr) >= 0.4:
                        st.info("中程度の相関があります。")
                    else:
                        st.warning("相関は弱めです。")
                else:
                    st.markdown("**相関係数（参考）**: -")

                if len(merged) < 3:
                    st.warning("データ点が少ないため、相関は参考値です。")

                st.caption(f"共通年の収録範囲: {int(merged['year_num'].min())}年〜{int(merged['year_num'].max())}年")
                st.dataframe(merged, use_container_width=True, hide_index=True)

    with tab_catalog:
        st.subheader("データカタログ")
        c1, c2, c3 = st.columns(3)
        csv_count = len(list(DATA_DIR.glob("*.csv"))) - (1 if (DATA_DIR / "data_catalog.csv").exists() else 0)
        c1.metric("CSV数", csv_count)
        c2.metric("データセット数", int(f["dataset_id"].nunique()) if "dataset_id" in f.columns else 0)
        c3.metric("指標数", int(f["indicator"].nunique()) if "indicator" in f.columns else 0)

        st.info("注: 指標ごとに収録期間が異なります。比較や相関は共通年のみに絞って解釈してください。")

        if catalog.empty:
            st.info("data_catalog.csv がまだ整っていません。")
        else:
            st.dataframe(catalog, use_container_width=True, hide_index=True)

        st.subheader("収録ファイル一覧")
        files_df = pd.DataFrame({
            "ファイル名": [p.name for p in sorted(DATA_DIR.glob("*.csv")) if p.name != "data_catalog.csv"]
        })
        st.dataframe(files_df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
