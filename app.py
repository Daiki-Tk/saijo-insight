
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Saijo Insight", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

SEX_LABELS = {
    "total": "総数",
    "male": "男性",
    "female": "女性",
    "na": "区分なし",
    "総数": "総数",
    "男性": "男性",
    "女性": "女性",
    "区分なし": "区分なし",
}

DATASET_LABELS = {
    "population_total_official": "総人口（公式）",
    "households_official": "世帯数（公式）",
    "population_by_sex_official": "男女別人口（公式）",
    "industry_offices_official": "事業所・従業者数（公式）",
    "industry_offices_private_official": "事業所・従業者数（民営・公式）",
    "industry_offices_public_official": "事業所・従業者数（公務・公式）",
}

PREFERRED_DATASETS = {
    "総人口": ["population_total_official", "population_by_sex_official"],
    "世帯数": ["households_official"],
    "事業所数": ["industry_offices_official"],
    "従業者数": ["industry_offices_official"],
}

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

    if "dataset_id" not in df.columns:
        df["dataset_id"] = df["__source_file"].str.replace(".csv", "", regex=False)

    for col in ["year_num", "value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "sex" not in df.columns:
        df["sex"] = "na"
    df["sex"] = df["sex"].astype(str)
    df["sex_label"] = df["sex"].map(lambda x: SEX_LABELS.get(x, x))

    for col in ["indicator", "category", "region", "dataset_id", "year_label", "unit", "fiscal_or_calendar", "source_table", "source_title", "notes"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def format_dataset_label(dataset_id: str) -> str:
    return DATASET_LABELS.get(dataset_id, dataset_id)


def format_value(value, unit="") -> str:
    if pd.isna(value):
        return "-"
    try:
        value = float(value)
    except Exception:
        return f"{value}{unit}"
    return f"{value:,.1f}{unit}" if not value.is_integer() else f"{value:,.0f}{unit}"


def normalize_unit(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    if out.empty:
        out["display_value"] = pd.Series(dtype=float)
        return out, ""

    unit = str(out["unit"].iloc[0]) if "unit" in out.columns else ""

    if unit == "千円":
        out["display_value"] = out["value"] / 1000
        display_unit = "百万円"
    elif unit == "万円":
        out["display_value"] = out["value"] / 100
        display_unit = "百万円"
    else:
        out["display_value"] = out["value"]
        display_unit = unit

    return out, display_unit


def pick_dataset_id(df: pd.DataFrame, indicator: str) -> str | None:
    available = df[df["indicator"] == indicator]["dataset_id"].dropna().astype(str).unique().tolist()
    if not available:
        return None
    for candidate in PREFERRED_DATASETS.get(indicator, []):
        if candidate in available:
            return candidate
    # official を優先
    for x in available:
        if "official" in x:
            return x
    return sorted(available)[0]


def clean_series_for_trend(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.dropna(subset=["year_num", "value"]).sort_values("year_num")

    if out.empty:
        return out

    if "sex_label" in out.columns and "総数" in out["sex_label"].values:
        out = out[out["sex_label"] == "総数"].copy()

    out = out.sort_values(["year_num"]).drop_duplicates(subset=["year_num"], keep="last")
    return out


def get_series(df: pd.DataFrame, indicator: str, region: str = "西条市", dataset_id: str | None = None) -> pd.DataFrame:
    out = df[(df["indicator"] == indicator) & (df["region"] == region)].copy()
    if dataset_id:
        out = out[out["dataset_id"] == dataset_id].copy()
    return clean_series_for_trend(out)


def quick_stats(df: pd.DataFrame, indicator: str, region: str = "西条市") -> tuple[str, str, str, str | None]:
    dataset_id = pick_dataset_id(df[df["region"] == region], indicator)
    if not dataset_id:
        return "-", "-", "-", None
    s = get_series(df, indicator, region=region, dataset_id=dataset_id)
    if s.empty:
        return "-", "-", "-", dataset_id
    first = s.iloc[0]
    last = s.iloc[-1]
    delta = last["value"] - first["value"]
    unit = last.get("unit", "")
    first_value = first["value"]
    pct = f"{(delta / first_value * 100):+.1f}%" if pd.notna(first_value) and first_value != 0 else "-"
    return format_value(last["value"], unit), f"{delta:,.0f}{unit}", pct, dataset_id


def render_reading(df: pd.DataFrame) -> None:
    ordered = clean_series_for_trend(df)
    if len(ordered) < 2:
        st.info("読み取り補助を表示するには、2点以上の時系列データが必要です。")
        return

    if "display_value" in ordered.columns:
        s = ordered["display_value"].astype(float)
    else:
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
        jump_year = ordered.loc[diffs.abs().idxmax(), "year_label"]
        lines.append(f"- 変化幅が大きい時点は **{jump_year}** 付近です。")
    lines.append("- これは読み取り補助です。背景要因や因果関係の判断には原資料の確認が必要です。")
    st.markdown("\n".join(lines))


def manifest_from_data(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dataset_id, g in df.groupby("dataset_id"):
        rows.append({
            "データセット": format_dataset_label(dataset_id),
            "dataset_id": dataset_id,
            "カテゴリ": " / ".join(sorted(g["category"].dropna().unique().tolist())),
            "指標": " / ".join(sorted(g["indicator"].dropna().unique().tolist())),
            "収録期間": f"{int(g['year_num'].min())}〜{int(g['year_num'].max())}" if g["year_num"].notna().any() else "-",
            "年種別": " / ".join(sorted(g["fiscal_or_calendar"].dropna().unique().tolist())),
            "出典表": " / ".join(sorted(g["source_table"].dropna().unique().tolist())),
        })
    return pd.DataFrame(rows).sort_values(["データセット"])


def main() -> None:
    f = load_all_data()

    st.title("Saijo Insight")
    st.caption("正式採用データセット版｜西条市統計の探索・比較・理解のためのダッシュボード")

    if f.empty:
        st.error("data フォルダにCSVがありません。")
        return

    region = "西条市"
    tab_home, tab_explore, tab_compare, tab_catalog = st.tabs(["ホーム", "探索", "比較", "正式データ一覧"])

    with tab_home:
        c1, c2, c3 = st.columns(3)

        pop_now, pop_delta, pop_pct, pop_ds = quick_stats(f, "総人口", region)
        hh_now, hh_delta, hh_pct, hh_ds = quick_stats(f, "世帯数", region)
        offices_now, offices_delta, offices_pct, offices_ds = quick_stats(f, "事業所数", region)

        c1.metric("総人口", pop_now, f"{pop_delta} / {pop_pct}")
        c2.metric("世帯数", hh_now, f"{hh_delta} / {hh_pct}")
        c3.metric("事業所数", offices_now, f"{offices_delta} / {offices_pct}")

        st.subheader("ヒーローグラフ")
        hero_dataset = pop_ds or pick_dataset_id(f, "総人口")
        hero = get_series(f, "総人口", region=region, dataset_id=hero_dataset) if hero_dataset else pd.DataFrame()
        if not hero.empty:
            hero = hero.copy()
            hero["display_value"] = hero["value"]
            fig = px.line(
                hero,
                x="year_num",
                y="display_value",
                markers=True,
                title="西条市 総人口の推移",
                labels={"year_num": "年", "display_value": "人口（人）"},
                custom_data=["year_label"],
            )
            fig.update_traces(hovertemplate="年: %{customdata[0]}<br>人口: %{y:,.0f}人<extra></extra>")
            fig.update_xaxes(tickmode="linear", dtick=1)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                f"データセット: {format_dataset_label(hero_dataset)} ｜ "
                f"収録期間: {int(hero['year_num'].min())}年〜{int(hero['year_num'].max())}年"
            )
            with st.expander("このグラフの読み取り"):
                render_reading(hero)
        else:
            st.info("総人口の時系列データが見つかりません。")

        st.subheader("おすすめ分析")
        a, b = st.columns(2)
        with a:
            st.info("人口の基本動向")
            st.write("総人口と世帯数を見比べると、人口減少と世帯数の動きの違いが分かります。")
        with b:
            st.info("人口と事業所数の比較")
            st.write("総人口と事業所数を比較すると、西条市の規模変化を俯瞰できます。")

    with tab_explore:
        st.subheader("探索")

        categories = sorted(f["category"].dropna().astype(str).unique())
        col1, col2, col3, col4, col5 = st.columns([1.1, 1.4, 1.6, 1.0, 1.0])

        with col1:
            selected_category = st.selectbox("カテゴリ", categories)

        with col2:
            indicators = sorted(f[f["category"] == selected_category]["indicator"].dropna().astype(str).unique())
            selected_indicator = st.selectbox("指標", indicators)

        with col3:
            dataset_options = sorted(
                f[(f["category"] == selected_category) & (f["indicator"] == selected_indicator)]["dataset_id"].dropna().astype(str).unique()
            )
            selected_dataset = st.selectbox("データセット", dataset_options, format_func=format_dataset_label)

        with col4:
            chart_type = st.selectbox("グラフ形式", ["折れ線", "棒"])

        filtered = f[
            (f["category"] == selected_category) &
            (f["indicator"] == selected_indicator) &
            (f["dataset_id"] == selected_dataset)
        ].copy()

        with col5:
            sex_options = sorted(filtered["sex_label"].dropna().astype(str).unique()) if not filtered.empty else ["区分なし"]
            default_idx = sex_options.index("総数") if "総数" in sex_options else 0
            selected_sex = st.selectbox("区分", sex_options, index=default_idx)

        if "sex_label" in filtered.columns and selected_sex in filtered["sex_label"].values:
            filtered = filtered[filtered["sex_label"] == selected_sex].copy()

        filtered = clean_series_for_trend(filtered)

        if filtered.empty:
            st.warning("この条件に合うデータがありません。")
        else:
            filtered, display_unit = normalize_unit(filtered)
            ycol = "display_value"

            if chart_type == "折れ線":
                fig2 = px.line(filtered, x="year_num", y=ycol, markers=True)
            else:
                fig2 = px.bar(filtered, x="year_num", y=ycol)

            fig2.update_layout(
                title=f"{selected_indicator}",
                xaxis_title="年",
                yaxis_title=f"値（{display_unit}）" if display_unit else "値",
            )
            fig2.update_xaxes(tickmode="linear", dtick=1)
            st.plotly_chart(fig2, use_container_width=True)

            st.caption(
                f"データセット: {format_dataset_label(selected_dataset)} ｜ "
                f"収録期間: {int(filtered['year_num'].min())}年〜{int(filtered['year_num'].max())}年"
            )

            with st.expander("このグラフの読み取り"):
                render_reading(filtered)

            show_cols = [c for c in ["year_label", "value", "unit", "sex_label", "fiscal_or_calendar", "source_title", "source_table", "notes"] if c in filtered.columns]
            st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

    with tab_compare:
        st.subheader("比較")

        compare_rows = []
        for label, indicator in [("総人口（公式）", "総人口"), ("世帯数（公式）", "世帯数"), ("事業所数（公式）", "事業所数"), ("従業者数（公式）", "従業者数")]:
            ds = pick_dataset_id(f, indicator)
            if ds:
                compare_rows.append((label, indicator, ds))

        if len(compare_rows) < 2:
            st.warning("比較に使える正式データセットが不足しています。")
        else:
            labels = [x[0] for x in compare_rows]
            mapping = {label: (indicator, dataset_id) for label, indicator, dataset_id in compare_rows}

            left_sel, right_sel = st.columns(2)
            with left_sel:
                label_a = st.selectbox("指標A", labels, index=0)
            with right_sel:
                label_b = st.selectbox("指標B", labels, index=1 if len(labels) > 1 else 0)

            indicator_a, dataset_a = mapping[label_a]
            indicator_b, dataset_b = mapping[label_b]

            df1 = get_series(f, indicator_a, region=region, dataset_id=dataset_a)[["year_num", "year_label", "value", "unit"]].copy()
            df2 = get_series(f, indicator_b, region=region, dataset_id=dataset_b)[["year_num", "year_label", "value", "unit"]].copy()

            merged = pd.merge(df1, df2, on="year_num", how="inner", suffixes=("_a", "_b")).dropna(subset=["value_a", "value_b"]).sort_values("year_num")

            if merged.empty:
                st.warning("共通年のデータがありません。")
            else:
                merged["year_label_view"] = merged["year_label_a"] if "year_label_a" in merged.columns else merged["year_num"].astype(int).astype(str)

                left, right = st.columns(2)
                with left:
                    line_df = merged[["year_num", "year_label_view", "value_a", "value_b"]].copy()
                    line_long = line_df.melt(
                        id_vars=["year_num", "year_label_view"],
                        value_vars=["value_a", "value_b"],
                        var_name="series",
                        value_name="value",
                    )
                    line_long["series"] = line_long["series"].map({"value_a": label_a, "value_b": label_b})
                    fig_line = px.line(line_long, x="year_num", y="value", color="series", markers=True, hover_data=["year_label_view"])
                    fig_line.update_layout(title=f"{label_a} と {label_b} の並行比較", xaxis_title="年", yaxis_title="値")
                    fig_line.update_xaxes(tickmode="linear", dtick=1)
                    st.plotly_chart(fig_line, use_container_width=True)

                with right:
                    fig_scatter = px.scatter(merged, x="value_a", y="value_b", text="year_label_view")
                    fig_scatter.update_traces(textposition="top center")
                    unit_a = merged["unit_a"].iloc[0] if "unit_a" in merged.columns and len(merged) else ""
                    unit_b = merged["unit_b"].iloc[0] if "unit_b" in merged.columns and len(merged) else ""
                    fig_scatter.update_layout(title="散布図", xaxis_title=f"{label_a}（{unit_a}）", yaxis_title=f"{label_b}（{unit_b}）")
                    st.plotly_chart(fig_scatter, use_container_width=True)

                corr = merged["value_a"].corr(merged["value_b"]) if len(merged) >= 2 else None
                st.markdown(f"**相関係数（参考）**: {corr:.3f}" if corr is not None and pd.notna(corr) else "**相関係数（参考）**: -")
                if corr is not None and pd.notna(corr):
                    if abs(corr) > 0.7:
                        st.success("強い相関があります。")
                    elif abs(corr) > 0.4:
                        st.info("中程度の相関があります。")
                    else:
                        st.warning("相関は弱めです。")
                if len(merged) < 3:
                    st.warning("データ点が少ないため、相関は参考値です。")

                st.dataframe(merged, use_container_width=True, hide_index=True)

    with tab_catalog:
        st.subheader("正式データ一覧")
        manifest = manifest_from_data(f)

        c1, c2, c3 = st.columns(3)
        c1.metric("正式採用CSV数", int(f["dataset_id"].nunique()))
        c2.metric("指標数", int(f["indicator"].nunique()))
        c3.metric("カテゴリ数", int(f["category"].nunique()))

        st.dataframe(manifest, use_container_width=True, hide_index=True)
        st.caption("この app は、現在 data フォルダに存在する正式採用データセットを自動検出して表示します。")

if __name__ == "__main__":
    main()
