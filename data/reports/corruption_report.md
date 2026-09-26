# Corruption and Repair Report

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Retrieval Hit Rate | 1.000 | 0.500 | 1.000 |
| Mean Token F1 | 1.000 | 0.779 | 1.000 |
| Judge Accuracy | 1.000 | 0.800 | 1.000 |
| Mean Judge Score | 5 | 4 | 5 |
| Great Expectations Quality Gate | N/A | FAIL | PASS |
| Freshness SLA | N/A | FRESH (14.3% stale) | FRESH (4.2% stale) |

## Observed Impact
- **Retrieval Hit Rate**: corruption delta -0.500; repair delta from corrupted +0.500.
- **Mean Token F1**: corruption delta -0.221; repair delta from corrupted +0.221.
