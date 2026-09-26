# Phase 1 Baseline Report

## Source
- **source_api**: Crossref REST API
- **query**: agentic retrieval augmented generation large language model
- **filter**: from-pub-date:2026-03-30,has-abstract:true
- **record_count**: 24
- **raw_response_path**: C:\Users\hyo\K4-L3B-DAY10-Optics-DataPipelineDataObservability\data\raw\crossref_response.json
- **raw_records_path**: C:\Users\hyo\K4-L3B-DAY10-Optics-DataPipelineDataObservability\data\raw\crossref_records.json

## RAG Evaluation
- **samples**: 10
- **retrieval_hit_rate**: 1.0
- **mean_token_f1**: 1.0
- **judge_accuracy**: 1.0
- **mean_judge_score**: 5
- **ragas**: {"skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."}

## Great Expectations Quality Gate
- **Overall success**: True
- **Expectations**: 4/4 passed
- `expect_table_row_count_to_be_between`: PASS
- `expect_column_values_to_not_be_null`: PASS
- `expect_column_values_to_be_unique`: PASS
- `expect_column_value_lengths_to_be_between`: PASS

## Freshness SLA
- **is_fresh**: True
- **freshness_threshold_days**: 180
- **max_stale_ratio**: 0.25
- **stale_rows**: 1
- **missing_age_rows**: 0
- **total_rows**: 24
- **stale_ratio**: 0.041666666666666664
