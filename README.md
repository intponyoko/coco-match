# Coco Matching Mock

成長戦略の売上目標から仮想PJを導き、人材の保有スキル・キャリア目標と突き合わせてアサインを確認する Streamlit モックです。

## セットアップ

```bash
uv sync --python 3.12
```

## 起動

```bash
uv run streamlit run app.py
```

## 実装方針

- 正規化済みテーブルを `pandera` で検証します。
- 画面で表示する `成長戦略 / キャリア計画 / スキルシート / 仮想PJ / アサイン計画` は、正規化テーブルの JOIN ビューとして構成します。
- ダミーデータは `data/*.csv` を編集することで差し替えできます。

## 主要画面

0. モック概要
   正規化モデルの概要、現在のテーブル件数、JOIN ビューの確認、エクスポートを行います。
1. 成長戦略の入力
   `時期 / お金` のCSVを投入します。`お金` は売上目標額として扱います。
2. キャリア計画の入力
   `ID / 時期 / スキル / スキルのLv` のCSVを投入します。
3. スキルシートの入力
   `ID / スキル / スキルのLv` のCSVを投入します。
4. 仮想PJの出力
   正規化テーブルから生成した案件テーブルを JOIN 表示します。
5. アサイン計画の出力
   正規化テーブルから生成したアサインテーブルを JOIN 表示します。
6. シフト最適化デモ
   既存の制約最適化デモです。

## マスタ管理

`(開発者用)マスタ管理` セクションでは、以下の全テーブルを個別ページで編集できます。

- `sales_strategy`
- `fiscal_period`
- `sales_target`
- `skill`
- `employee`
- `employee_skill`
- `career_goal`
- `project`
- `project_required_skill`
- `assignment`

セクション先頭の `マスタ管理ガイド` には ER 図と各テーブルの役割を載せています。

## ダミーデータ

ダミーデータは `data/` 配下のCSVから読み込みます。

- `data/sales_strategy.csv`
- `data/fiscal_period.csv`
- `data/sales_target.csv`
- `data/skill.csv`
- `data/employee.csv`
- `data/employee_skill.csv`
- `data/career_goal.csv`
- `data/project.csv`
- `data/project_required_skill.csv`
- `data/assignment.csv`

## 出力ファイル

トップページの `ER図とデータを書き出す` から以下を出力します。

- `exports/normalized_state/data/*.csv`
- `exports/normalized_state/data/*.json`
- `exports/normalized_state/schema/database_schema.json`
- `docs/master_data_er.mmd`
- `docs/master_data_wiki.md`
