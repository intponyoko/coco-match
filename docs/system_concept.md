# Systemコンセプト
業務を支援するために, システムはLLMと共に実施する業務&稟議パイプラインを, BI画面から制御する方式をとることにしました. 


まず, 全体として求められていた機能要件は以下の二つになります
1. 仮想PJ作成: 今年の売り上げ目標(SalesPlan)と過去事例を元に今年受注できそうな仮想的なPJ(Opportunity)を作成する. また, 仮想的なPJの内容から, 案件内容や必要ロール人数規模を算出してポートフォリオを作成する
2. 擬似的なアサインの実施: ポートフォリオの内容を元に, 個人は自身のキャリア目標を元に, アサインされたいPJや研修内容を指定する. この個人希望を無理ない範囲で守りながら, 会社として機会平等と安定的なデリバリーを担保したアサイン計画案をシフトスケジューリングの要領で導出する.


これを実装するために, 複数のPipelineを作成することとしました
1. `propose_theme_solutions`: SalesPlanと過去案件ナレッジを元に, 今年狙うべきTheme / Solutionのポートフォリオ案を生成する. Inputは `sales_plans`, `accounts`, `roles`, `fiscal_periods`, `past_cases`, `past_case_roles`, `past_case_links` で, Outputは `knowledge_nodes`, `knowledge_edges`, `theme_candidates`, `theme_recommendations`
2. `propose_project_requests`: 承認済みTheme / Solution案を元に, どのAccountに対してどの規模のPJを作るべきか, また必要ロールRequestをどう分解するかを生成する. Inputは承認済み `theme_recommendations` と sample/master tables で, Outputは `account_recommendations`, `project_sizing_recommendations`, `request_recommendations`
3. `materialize_opportunities`: 承認済みのPJ規模案とRequest案を, 実際のOpportunityとOpportunityRequestに具体化する. Inputは承認済み `project_sizing_recommendations`, `request_recommendations` で, Outputは `opportunities`, `opportunity_requests`, `opportunity_recommendations`, `allocation_trace`
4. `propose_assignment_options`: 個人が選択できる参画候補や育成枠候補を生成する. Inputは `opportunities`, `opportunity_requests`, `staffs`, `role_skills`, `staff_career`, `fiscal_periods` で, Outputは `staff_preference_options`
5. `propose_assignments`: 個人希望, 現有スキル, 稼働率, 育成可能性を元にアサイン案を生成する. Inputは `opportunity_requests`, `role_skills`, `staff_career`, `staffs`, `titles`, `fiscal_periods`, 任意で `staff_preference_options` で, Outputは `assignment_recommendations`, `matching_trace`, `staff_utilization`
6. `finalize_assignments`: 承認済みアサイン案を最終的なアサイン計画に変換する. Inputは承認済み `assignment_recommendations` で, Outputは `opportunity_assignments`


このPipelineを元に, バックエンド側ではFastAPIを用いてPipelineをステートレスなAPIとして提供し, フロントエンド側ではAstroを用いてステートを管理してPipelineの実行を管理するWebApplicationを開発することとしました

<Architecture図>

#### AIAgentの活用の部分について
AIAgentは, 「人が最終承認を持ちつつ, 高度な仮説生成や説明生成はLLMに委譲する」という思想で使う方針で設計しました.
具体的には, 一般的に使われがちなUI/UXの会話機能を先に作るのではなく, まずはPipeline内部の仮説生成をLLMが担えるようにI/Oを揃え, Offline環境ではDeterministicなMock, Online環境ではLLM本体が同じ入出力契約で置き換わる構造を目指しています.

Pipelineの一連の処理のうち, 特に知能処理として重視しているのは以下です
- `propose_theme_solutions`: 過去案件からTheme / Solutionの候補を抽出し, どの業界にどのテーマが妥当かを仮説生成する
- `propose_project_requests`: テーマ案を元に, Account, PJ規模, 期間, 必要ロール構成を仮説生成する
- `propose_assignment_options`: 個人ごとの参加可能案件や育成枠候補を生成する
- `propose_assignments`: 個人希望と会社都合を両立するアサイン案を生成する

この4段は, 将来的にはLLM / Agentによる提案生成を担わせる対象であり, 現在は同一I/OのMock実装を通じて, Online/Offlineで中身を差し替えられる構造にしています.

今回最も力を入れた場所は, 過去PJを元に来年PJを予測する機能でした.
一般的に過去の販売量をもとに未来の販売計画を作る際には需要予測などのソリューションが使用されます
しかし, 今回のように必要人材を見積もるために, 販売量を超えて受注PJまで分解する場合は, 需要予測を使用できませんでした
そこで, 過去の受注履歴からその時期その業界で取れそうなPJを推測し, 案件種や人数を見積もる方法を新しく開発し, 需要予測よりも高解像な予測に成功しました.
これはナレッジグラフを参考に制作したもので, RAGで収集した情報を元にランタイムでPJを表現するグラフ構造を作成するというものです

<RAGシステム概要図 / 以下を入れる
過去のPJ情報としてそのPJの規模や必要だったロール, どう言った顧客課題出会ったかといった細かな内容をグラフ構造のMeta情報としてをRAGのデータベースに格納します
PJを作成するときはこのMeta情報で検索をして行った上で, 複数のPJ情報を抽出し, 妥当なPJのグラフを生成する方法を撮りました.
>
