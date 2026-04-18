
from pathlib import Path
import math
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
    "population_total_official": "総人口（住民基本台帳）",
    "households_official": "世帯数（住民基本台帳）",
    "population_by_sex_official": "男女別人口（住民基本台帳）",
    "population_by_age_official": "年齢別人口",
    "population_dynamics_official": "人口動態",
    "census_population_households_official": "国勢調査人口・世帯数",
    "labor_force_status_official": "労働力状態別15歳以上人口",
    "day_night_population_official": "昼間人口・流入流出",
    "industry_offices_official": "事業所・従業者数",
    "employment_by_industry_official": "産業大分類別就業者数",
    "manufacturing_trend_official": "製造業の推移",
    "manufacturing_overview_official": "製造業の概況（中分類）",
    "commerce_overview_official": "卸売業・小売業の概況",
    "agriculture_crops_official": "主要農作物",
    "farm_households_official": "農家数の推移",
    "agri_workers_official": "農業従事者数等",
    "fishery_entities_official": "漁業経営体数",
    "gdp_city_official": "西条市内総生産",
    "income_city_official": "西条市民所得",
    "finance_revenue_official": "一般会計歳入",
    "finance_expenditure_official": "一般会計歳出",
    "tax_revenue_official": "市税収入状況",
    "vehicle_ownership_official": "自動車等保有台数",
    "traffic_ic_official": "インターチェンジ出入交通量",
    "jr_usage_official": "JR利用状況",
    "employment_official": "一般職業紹介状況",
    "child_welfare_official": "児童福祉",
    "education_schools_official": "学校数・児童数・教員数",
    "education_career_official": "学校卒業後の状況",
    "waste_management_official": "ごみ処理状況",
}

DIMENSION_LABELS = {
    "sex_label": "区分",
    "item": "項目",
    "group": "区分",
    "industry": "産業分類",
    "age": "年齢",
    "region_sub": "内訳",
}

THEMES = {
    "人口減少の構造": {
        "description": "人口の減少、出生死亡、国勢調査ベースの長期推移をまとめて確認します。",
        "series": [
            ("総人口", "population_total_official"),
            ("人口総数", "census_population_households_official"),
            ("出生", "population_dynamics_official"),
            ("死亡", "population_dynamics_official"),
            ("人口増加", "population_dynamics_official"),
        ],
    },
    "若者・教育・流出": {
        "description": "学校在籍数、進路、昼間人口・流入流出から若者の流れを読みます。",
        "series": [
            ("児童数", "education_schools_official", {"subcategory": "小学校"}),
            ("生徒数", "education_schools_official", {"subcategory": "中学校"}),
            ("大学進学者数", "education_career_official", {"subcategory": "高校卒業後"}),
            ("就職者数", "education_career_official", {"subcategory": "高校卒業後"}),
            ("流出_総数", "day_night_population_official"),
        ],
    },
    "産業と雇用": {
        "description": "就業者、製造業、求人の動きを並べて、雇用のミスマッチと産業の強みを確認します。",
        "series": [
            ("就業者数", "employment_by_industry_official"),
            ("製造品出荷額", "manufacturing_trend_official"),
            ("有効求人数", "employment_official"),
            ("有効求職者数", "employment_official"),
            ("求人倍率_有効", "employment_official"),
        ],
    },
    "暮らしと交通": {
        "description": "自動車、JR、高速道路、ごみから西条の暮らし方を可視化します。",
        "series": [
            ("総数", "vehicle_ownership_official"),
            ("総交通量", "traffic_ic_official"),
            ("伊予西条_定期", "jr_usage_official"),
            ("総量", "waste_management_official", {"region": "家庭系"}),
        ],
    },
    "財政と税": {
        "description": "歳入・歳出・税収構造を確認し、財政の特徴をつかみます。",
        "series": [
            ("合計", "finance_revenue_official"),
            ("合計", "finance_expenditure_official"),
            ("総額", "tax_revenue_official"),
            ("市税", "finance_revenue_official"),
            ("地方交付税", "finance_revenue_official"),
        ],
    },
    "農業・一次産業": {
        "description": "農作物、農家数、農業従事者、漁業経営体をまとめて確認します。",
        "series": [
            ("水稲_作付面積", "agriculture_crops_official"),
            ("水稲_収穫量", "agriculture_crops_official"),
            ("総農家数", "farm_households_official"),
            ("農業従事者", "agri_workers_official"),
            ("総数", "fishery_entities_official"),
        ],
    },
}

# ---------- load ----------
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

    string_cols = [
        "dataset_id", "category", "subcategory", "indicator", "region", "year_label",
        "fiscal_or_calendar", "unit", "source_table", "source_title", "notes",
        "item", "group", "industry", "age", "sex"
    ]
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    if "sex" not in df.columns:
        df["sex"] = "na"
    df["sex_label"] = df["sex"].map(lambda x: SEX_LABELS.get(x, x))

    return df


def format_dataset_label(x: str) -> str:
    return DATASET_LABELS.get(x, x)


def format_num(value, unit="", digits=0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    try:
        value = float(value)
    except Exception:
        return f"{value}{unit}"
    if digits == 0 and value.is_integer():
        return f"{int(value):,}{unit}"
    return f"{value:,.{digits}f}{unit}"


def normalize_values(df: pd.DataFrame):
    out = df.copy()
    unit = out["unit"].iloc[0] if "unit" in out.columns and not out.empty else ""
    if unit == "千円":
        out["display_value"] = out["value"] / 1000
        return out, "百万円"
    if unit == "万円":
        out["display_value"] = out["value"] / 100
        return out, "百万円"
    out["display_value"] = out["value"]
    return out, unit


def preferred_series(df: pd.DataFrame, indicator: str, dataset_id: str | None = None, extra_filters: dict | None = None):
    s = df[df["indicator"] == indicator].copy()
    if dataset_id:
        s = s[s["dataset_id"] == dataset_id].copy()
    if extra_filters:
        for k, v in extra_filters.items():
            if k in s.columns:
                s = s[s[k] == v].copy()

    if "sex_label" in s.columns and "総数" in s["sex_label"].values:
        s = s[s["sex_label"] == "総数"].copy()

    s = s.dropna(subset=["year_num", "value"]).sort_values("year_num")
    s = s.drop_duplicates(subset=["year_num"], keep="last")
    return s


def latest_kpi(df: pd.DataFrame, indicator: str, dataset_id: str | None = None, extra_filters: dict | None = None):
    s = preferred_series(df, indicator, dataset_id, extra_filters)
    if s.empty:
        return "-", "-"
    latest = s.iloc[-1]["value"]
    if len(s) >= 2:
        prev = s.iloc[-2]["value"]
        diff = latest - prev
        if prev not in [0, None] and not pd.isna(prev):
            pct = diff / prev * 100
            delta = f"{diff:+,.0f} / {pct:+.1f}%"
        else:
            delta = f"{diff:+,.0f}"
    else:
        delta = "-"
    unit = s.iloc[-1]["unit"] if "unit" in s.columns else ""
    digits = 1 if unit == "倍" else 0
    return format_num(latest, unit, digits=digits), delta


def trend_sentence(s: pd.DataFrame, label: str):
    if s.empty or len(s) < 2:
        return f"・{label}は十分な時系列データがありません。"
    latest = float(s.iloc[-1]["value"])
    first = float(s.iloc[0]["value"])
    unit = s.iloc[-1]["unit"] if "unit" in s.columns else ""
    diff = latest - first
    pct = None if first == 0 else diff / first * 100
    direction = "増加" if diff > 0 else "減少" if diff < 0 else "横ばい"
    if pct is None:
        return f"・{label}は {s.iloc[0]['year_label']} から {s.iloc[-1]['year_label']} にかけて {direction}しました。"
    return f"・{label}は {s.iloc[0]['year_label']} から {s.iloc[-1]['year_label']} にかけて {direction}（{pct:+.1f}%）しました。"


def discover_dimension_columns(df: pd.DataFrame):
    candidates = []
    for col in ["sex_label", "item", "group", "industry", "age"]:
        if col in df.columns and df[col].nunique(dropna=True) > 1:
            candidates.append(col)
    return candidates


def apply_dimension_filter(s: pd.DataFrame, dimension_col: str | None, dimension_value: str | None):
    out = s.copy()
    if dimension_col and dimension_col in out.columns and dimension_value is not None:
        out = out[out[dimension_col].astype(str) == str(dimension_value)].copy()
    return out


def make_timeseries_chart(df: pd.DataFrame, chart_type: str, title: str, color_col: str | None = None):
    work, display_unit = normalize_values(df)
    ycol = "display_value"
    if chart_type == "折れ線":
        fig = px.line(work, x="year_num", y=ycol, color=color_col, markers=True)
    elif chart_type == "棒":
        fig = px.bar(work, x="year_num", y=ycol, color=color_col, barmode="group")
    elif chart_type == "積み上げ棒":
        fig = px.bar(work, x="year_num", y=ycol, color=color_col, barmode="stack")
    elif chart_type == "面":
        fig = px.area(work, x="year_num", y=ycol, color=color_col)
    else:
        fig = px.line(work, x="year_num", y=ycol, color=color_col, markers=True)

    fig.update_layout(
        title=title,
        xaxis_title="年",
        yaxis_title=f"値（{display_unit}）" if display_unit else "値",
        legend_title=""
    )
    fig.update_xaxes(tickmode="linear", dtick=1)
    return fig


def make_latest_pie(df: pd.DataFrame, names_col: str, title: str):
    if df.empty:
        return None
    latest_year = df["year_num"].max()
    work = df[df["year_num"] == latest_year].copy()
    if work.empty:
        return None
    work, unit = normalize_values(work)
    fig = px.pie(work, names=names_col, values="display_value", title=title)
    return fig


def theme_block(df: pd.DataFrame, theme_name: str):
    theme = THEMES[theme_name]
    st.subheader(theme_name)
    st.caption(theme["description"])

    cards = st.columns(min(4, len(theme["series"])))
    for idx, spec in enumerate(theme["series"][:4]):
        indicator = spec[0]
        dataset_id = spec[1]
        extra = spec[2] if len(spec) >= 3 else None
        val, delta = latest_kpi(df, indicator, dataset_id, extra)
        cards[idx].metric(indicator, val, delta)

    for spec in theme["series"]:
        indicator = spec[0]
        dataset_id = spec[1]
        extra = spec[2] if len(spec) >= 3 else None
        s = preferred_series(df, indicator, dataset_id, extra)
        if not s.empty:
            fig = make_timeseries_chart(s, "折れ線", f"{indicator} の推移")
            st.plotly_chart(fig, use_container_width=True)

    # auto commentary
    st.markdown("#### 自動インサイト")
    for spec in theme["series"][:4]:
        indicator = spec[0]
        dataset_id = spec[1]
        extra = spec[2] if len(spec) >= 3 else None
        s = preferred_series(df, indicator, dataset_id, extra)
        st.write(trend_sentence(s, indicator))


def data_manifest(df: pd.DataFrame):
    rows = []
    for dataset_id, g in df.groupby("dataset_id"):
        rows.append({
            "データセット": format_dataset_label(dataset_id),
            "dataset_id": dataset_id,
            "大項目": " / ".join(sorted(g["category"].dropna().unique().tolist())),
            "中項目": " / ".join(sorted(g["subcategory"].dropna().unique().tolist())) if "subcategory" in g.columns else "",
            "指標数": int(g["indicator"].nunique()) if "indicator" in g.columns else 0,
            "収録期間": f"{int(g['year_num'].min())}〜{int(g['year_num'].max())}" if g["year_num"].notna().any() else "-",
            "単位": " / ".join(sorted(g["unit"].dropna().unique().tolist())) if "unit" in g.columns else "",
        })
    return pd.DataFrame(rows).sort_values(["大項目", "データセット"])


# ---------- main ----------
df = load_all_data()

st.title("Saijo Insight")
st.caption("西条市統計ダッシュボード｜データ探索・比較・テーマ分析・自動インサイト")

if df.empty:
    st.error("data フォルダにCSVがありません。")
    st.stop()

if "page" not in st.session_state:
    st.session_state["page"] = "ホーム"
if "selected_theme" not in st.session_state:
    st.session_state["selected_theme"] = "人口減少の構造"

with st.sidebar:
    st.header("ナビゲーション")
    page = st.radio(
        "画面",
        ["ホーム", "ダッシュボード", "比較分析", "テーマ分析", "データ一覧"],
        index=["ホーム", "ダッシュボード", "比較分析", "テーマ分析", "データ一覧"].index(st.session_state["page"]),
    )
    st.session_state["page"] = page
    st.markdown("---")
    st.caption("データフォルダ内のCSVを自動読込しています。")

page = st.session_state["page"]

if page == "ホーム":
    c1, c2, c3, c4 = st.columns(4)
    kpis = [
        ("総人口", "population_total_official", None),
        ("世帯数", "households_official", None),
        ("事業所数", "industry_offices_official", None),
        ("出生", "population_dynamics_official", None),
    ]
    for col, (ind, ds, extra) in zip([c1, c2, c3, c4], kpis):
        val, delta = latest_kpi(df, ind, ds, extra)
        col.metric(ind, val, delta)

    st.markdown("### 注目グラフ")
    hero = preferred_series(df, "総人口", "population_total_official")
    if hero.empty:
        hero = preferred_series(df, "人口総数", "census_population_households_official")
    if not hero.empty:
        fig = make_timeseries_chart(hero, "折れ線", "西条市の人口推移")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 自動インサイト")
    insight_specs = [
        ("総人口", "population_total_official"),
        ("出生", "population_dynamics_official"),
        ("製造品出荷額", "manufacturing_trend_official"),
        ("総量", "waste_management_official"),
        ("有効求人数", "employment_official"),
    ]
    for indicator, dataset_id in insight_specs:
        s = preferred_series(df, indicator, dataset_id)
        if not s.empty:
            st.write(trend_sentence(s, indicator))

    st.markdown("### おすすめ分析")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("人口減少の原因を探る", use_container_width=True):
            st.session_state["selected_theme"] = "人口減少の構造"
            st.session_state["page"] = "テーマ分析"
            st.rerun()
        if st.button("若者流出と教育を見る", use_container_width=True):
            st.session_state["selected_theme"] = "若者・教育・流出"
            st.session_state["page"] = "テーマ分析"
            st.rerun()
        if st.button("産業と雇用の関係を見る", use_container_width=True):
            st.session_state["selected_theme"] = "産業と雇用"
            st.session_state["page"] = "テーマ分析"
            st.rerun()
    with b2:
        if st.button("暮らしと交通を見る", use_container_width=True):
            st.session_state["selected_theme"] = "暮らしと交通"
            st.session_state["page"] = "テーマ分析"
            st.rerun()
        if st.button("財政と税の構造を見る", use_container_width=True):
            st.session_state["selected_theme"] = "財政と税"
            st.session_state["page"] = "テーマ分析"
            st.rerun()
        if st.button("農業・一次産業を見る", use_container_width=True):
            st.session_state["selected_theme"] = "農業・一次産業"
            st.session_state["page"] = "テーマ分析"
            st.rerun()

elif page == "ダッシュボード":
    st.subheader("データ探索")

    c1, c2, c3, c4, c5 = st.columns([1.2, 1.3, 1.6, 1.0, 1.0])

    with c1:
        categories = sorted(df["category"].dropna().unique().tolist())
        selected_category = st.selectbox("大項目", categories)

    filtered = df[df["category"] == selected_category].copy()

    with c2:
        subcategories = sorted(filtered["subcategory"].dropna().unique().tolist()) if "subcategory" in filtered.columns else []
        selected_subcategory = st.selectbox("中項目", ["（すべて）"] + subcategories)

    if selected_subcategory != "（すべて）":
        filtered = filtered[filtered["subcategory"] == selected_subcategory].copy()

    with c3:
        dataset_options = sorted(filtered["dataset_id"].dropna().unique().tolist())
        selected_dataset = st.selectbox("データセット", dataset_options, format_func=format_dataset_label)

    filtered = filtered[filtered["dataset_id"] == selected_dataset].copy()

    with c4:
        indicator_options = sorted(filtered["indicator"].dropna().unique().tolist())
        selected_indicator = st.selectbox("指標", indicator_options)

    filtered = filtered[filtered["indicator"] == selected_indicator].copy()

    dimension_cols = discover_dimension_columns(filtered)
    dimension_col = None
    dimension_value = None
    if dimension_cols:
        with c5:
            dimension_col = st.selectbox("内訳軸", ["なし"] + dimension_cols, format_func=lambda x: DIMENSION_LABELS.get(x, x))
        if dimension_col == "なし":
            dimension_col = None

    if dimension_col:
        d1, d2 = st.columns([1, 3])
        with d1:
            options = sorted(filtered[dimension_col].dropna().astype(str).unique().tolist())
            dimension_value = st.selectbox(DIMENSION_LABELS.get(dimension_col, dimension_col), ["（すべて）"] + options)
        if dimension_value != "（すべて）":
            filtered = apply_dimension_filter(filtered, dimension_col, dimension_value)
            dimension_value = dimension_value
        else:
            dimension_value = None

    chart_col1, chart_col2 = st.columns([1,1])
    with chart_col1:
        chart_type = st.selectbox("グラフ種類", ["折れ線", "棒", "積み上げ棒", "面"])
    with chart_col2:
        show_table = st.toggle("表データも表示", value=True)

    if filtered.empty:
        st.warning("この条件に合うデータがありません。")
    else:
        if dimension_col and dimension_value is None:
            plot_df = filtered.copy()
            color_col = dimension_col
        else:
            plot_df = filtered.copy()
            if "sex_label" in plot_df.columns and "総数" in plot_df["sex_label"].values:
                plot_df = plot_df[plot_df["sex_label"] == "総数"].copy()
            plot_df = plot_df.drop_duplicates(subset=["year_num"], keep="last")
            color_col = None

        fig = make_timeseries_chart(plot_df, chart_type, f"{selected_indicator}", color_col=color_col)
        st.plotly_chart(fig, use_container_width=True)

        # composition chart if useful
        if dimension_col:
            pie = make_latest_pie(filtered, dimension_col, f"最新年の構成比：{selected_indicator}")
            if pie is not None:
                st.plotly_chart(pie, use_container_width=True)

        st.markdown("#### 読み取り補助")
        if dimension_col and dimension_value is None:
            st.info("内訳軸を複数表示しています。特定の内訳を選ぶと、より詳しい読み取り補助を表示できます。")
        else:
            s = plot_df.sort_values("year_num")
            st.write(trend_sentence(s, selected_indicator))

        if show_table:
            cols = [c for c in ["year_label", "year_num", "value", "unit", "sex_label", "item", "group", "industry", "age", "source_table"] if c in filtered.columns]
            st.dataframe(filtered[cols], use_container_width=True, hide_index=True)

elif page == "比較分析":
    st.subheader("比較分析")

    top = st.columns(2)
    available_datasets = sorted(df["dataset_id"].dropna().unique().tolist())

    with top[0]:
        ds_a = st.selectbox("系列A データセット", available_datasets, format_func=format_dataset_label, key="cmp_ds_a")
    a_df = df[df["dataset_id"] == ds_a].copy()
    with top[1]:
        ds_b = st.selectbox("系列B データセット", available_datasets, format_func=format_dataset_label, key="cmp_ds_b")

    b_df = df[df["dataset_id"] == ds_b].copy()

    c1, c2 = st.columns(2)
    with c1:
        ind_a = st.selectbox("系列A 指標", sorted(a_df["indicator"].dropna().unique().tolist()), key="cmp_ind_a")
    with c2:
        ind_b = st.selectbox("系列B 指標", sorted(b_df["indicator"].dropna().unique().tolist()), key="cmp_ind_b")

    a = a_df[a_df["indicator"] == ind_a].copy()
    b = b_df[b_df["indicator"] == ind_b].copy()

    # prefer total if exists
    if "sex_label" in a.columns and "総数" in a["sex_label"].values:
        a = a[a["sex_label"] == "総数"].copy()
    if "sex_label" in b.columns and "総数" in b["sex_label"].values:
        b = b[b["sex_label"] == "総数"].copy()

    a = a.drop_duplicates(subset=["year_num"], keep="last")
    b = b.drop_duplicates(subset=["year_num"], keep="last")

    merged = pd.merge(
        a[["year_num", "year_label", "value", "unit"]],
        b[["year_num", "year_label", "value", "unit"]],
        on="year_num",
        how="inner",
        suffixes=("_a", "_b")
    ).dropna(subset=["value_a", "value_b"]).sort_values("year_num")

    if merged.empty:
        st.warning("共通年のデータがありません。")
    else:
        left, right = st.columns(2)

        with left:
            long = merged.melt(
                id_vars=["year_num"],
                value_vars=["value_a", "value_b"],
                var_name="series",
                value_name="value"
            )
            long["series"] = long["series"].map({"value_a": ind_a, "value_b": ind_b})
            fig_line = px.line(long, x="year_num", y="value", color="series", markers=True, title="共通年の並行比較")
            fig_line.update_xaxes(tickmode="linear", dtick=1)
            st.plotly_chart(fig_line, use_container_width=True)

        with right:
            fig_scatter = px.scatter(merged, x="value_a", y="value_b", text="year_num", title="散布図（共通年）")
            fig_scatter.update_traces(textposition="top center")
            st.plotly_chart(fig_scatter, use_container_width=True)

        corr = merged["value_a"].corr(merged["value_b"]) if len(merged) >= 2 else None
        c1, c2, c3 = st.columns(3)
        c1.metric("共通年数", len(merged))
        c2.metric("相関係数", f"{corr:.3f}" if corr is not None and not pd.isna(corr) else "-")
        if corr is None or pd.isna(corr):
            c3.metric("判定", "算出不可")
        elif abs(corr) >= 0.7:
            c3.metric("判定", "強い相関")
        elif abs(corr) >= 0.4:
            c3.metric("判定", "中程度")
        else:
            c3.metric("判定", "弱い相関")

        st.dataframe(merged, use_container_width=True, hide_index=True)

elif page == "テーマ分析":
    st.subheader("テーマ分析")
    theme_names = list(THEMES.keys())
    current_theme = st.selectbox("テーマを選ぶ", theme_names, index=theme_names.index(st.session_state["selected_theme"]))
    st.session_state["selected_theme"] = current_theme
    theme_block(df, current_theme)

elif page == "データ一覧":
    st.subheader("データ一覧")
    manifest = data_manifest(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("CSV数", int(df["dataset_id"].nunique()))
    c2.metric("大項目数", int(df["category"].nunique()))
    c3.metric("指標数", int(df["indicator"].nunique()))
    st.dataframe(manifest, use_container_width=True, hide_index=True)

    st.markdown("#### 使い方の提案")
    st.write("・ホームで全体像をつかむ")
    st.write("・テーマ分析でストーリーを読む")
    st.write("・ダッシュボードで個別指標を掘る")
    st.write("・比較分析で指標同士の関係を見る")
