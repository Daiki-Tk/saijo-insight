# Saijo Insight Starter

西条市統計ダッシュボード **Saijo Insight** のスタータープロジェクトです。

## 同梱内容
- `app.py` : Streamlit ダッシュボード本体
- `data/population_trend.csv` : 人口推移のサンプルデータ
- `data/data_catalog.csv` : 今後追加する指標の管理台帳
- `requirements.txt` : 必要ライブラリ
- `schema.md` : データ設計メモ

## 起動方法
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 想定フロー
1. PDFから各統計表をCSV化
2. `data_catalog.csv` に指標定義を登録
3. `data/*.csv` を追加
4. Streamlit Cloud などにデプロイしてURL共有

## データの基本ルール
- 年次 / 年度を必ず分ける
- 単位を必ず保持する
- 比較可能フラグを持たせる
- 推計値は `data_kind = projection` で明示する
