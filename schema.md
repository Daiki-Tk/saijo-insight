# Saijo Insight データスキーマ（初版）

1行 = 1観測値

## 必須列
- dataset_id
- category
- subcategory
- indicator
- region
- year_label
- year_num
- fiscal_or_calendar
- value
- unit
- sex
- data_kind
- comparable
- source_title
- source_table
- source_yearbook
- source_department
- notes

## 値の考え方
- `fiscal_or_calendar`: `calendar` / `fiscal`
- `data_kind`: `actual` / `projection`
- `comparable`: `true` / `false`
- `sex`: `total` / `male` / `female` / `na`

## 今後の拡張
- 愛媛県平均
- 全国平均
- 市町比較
- 推計シナリオ
