# RQ3 Grill Diagnostics

Missed / mismatched attacks: **90**

Do not hide low recall. This file explains failure modes.

| id | gold target | pred target | gold type | pred type | reason |
|----|-------------|-------------|-----------|-----------|--------|
| RQ3-002 | REQUIREMENT | ['ASSUMPTION'] | LATENCY | ['LATENCY'] | target_mismatch |
| RQ3-003 | CLAIM | ['REQUIREMENT'] | EVALUATION | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-004 | CONSTRAINT | ['ASSUMPTION'] | SCOPE | ['SCOPE'] | target_mismatch |
| RQ3-007 | DECISION | ['ASSUMPTION'] | DEPLOYMENT | ['DEPLOYMENT'] | target_mismatch |
| RQ3-008 | ARCHITECTURE | ['ASSUMPTION'] | RELIABILITY | ['RELIABILITY'] | target_mismatch |
| RQ3-009 | DECISION | ['ASSUMPTION'] | TECHNOLOGY_JUSTIFICATION | ['TECHNOLOGY_JUSTIFICATION'] | target_mismatch |
| RQ3-010 | ARCHITECTURE | ['ASSUMPTION'] | ARCHITECTURE_MISMATCH | ['ARCHITECTURE_MISMATCH', 'LATENCY'] | target_mismatch |
| RQ3-011 | CONSTRAINT | ['REQUIREMENT'] | TIMELINE | ['EvaluationAttackGenerator'] | attack_not_detected |
| RQ3-012 | REQUIREMENT | ['REQUIREMENT'] | SECURITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-014 | CONSTRAINT | ['ASSUMPTION'] | COST | ['COST', 'TECHNOLOGY_JUSTIFICATION'] | target_mismatch; severity_mismatch |
| RQ3-015 | REQUIREMENT | ['ASSUMPTION'] | REQUIREMENT_AMBIGUITY | ['REQUIREMENT_AMBIGUITY'] | target_mismatch |
| RQ3-016 | DECISION | ['ASSUMPTION'] | DEPENDENCY | ['DEPENDENCY'] | target_mismatch; severity_mismatch |
| RQ3-017 | CLAIM | ['REQUIREMENT'] | RESOURCE_FEASIBILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-018 | REQUIREMENT | ['ASSUMPTION'] | CONTRADICTION | ['CONTRADICTION'] | target_mismatch; severity_mismatch |
| RQ3-020 | ASSUMPTION | ['REQUIREMENT'] | DATA_AVAILABILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-022 | REQUIREMENT | ['ASSUMPTION'] | LATENCY | ['LATENCY'] | target_mismatch |
| RQ3-023 | CLAIM | ['REQUIREMENT'] | EVALUATION | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-024 | CONSTRAINT | ['ASSUMPTION'] | SCOPE | ['SCOPE'] | target_mismatch |
| RQ3-027 | DECISION | ['ASSUMPTION'] | DEPLOYMENT | ['DEPLOYMENT'] | target_mismatch |
| RQ3-028 | ARCHITECTURE | ['ASSUMPTION'] | RELIABILITY | ['RELIABILITY'] | target_mismatch |
| RQ3-029 | DECISION | ['ASSUMPTION'] | TECHNOLOGY_JUSTIFICATION | ['TECHNOLOGY_JUSTIFICATION'] | target_mismatch |
| RQ3-030 | ARCHITECTURE | ['ASSUMPTION'] | ARCHITECTURE_MISMATCH | ['ARCHITECTURE_MISMATCH', 'LATENCY'] | target_mismatch |
| RQ3-031 | CONSTRAINT | ['REQUIREMENT'] | TIMELINE | ['EvaluationAttackGenerator'] | attack_not_detected |
| RQ3-032 | REQUIREMENT | ['REQUIREMENT'] | SECURITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-034 | CONSTRAINT | ['ASSUMPTION'] | COST | ['COST', 'TECHNOLOGY_JUSTIFICATION'] | target_mismatch; severity_mismatch |
| RQ3-035 | REQUIREMENT | ['ASSUMPTION'] | REQUIREMENT_AMBIGUITY | ['REQUIREMENT_AMBIGUITY'] | target_mismatch |
| RQ3-036 | DECISION | ['ASSUMPTION'] | DEPENDENCY | ['DEPENDENCY'] | target_mismatch; severity_mismatch |
| RQ3-037 | CLAIM | ['REQUIREMENT'] | RESOURCE_FEASIBILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-038 | REQUIREMENT | ['ASSUMPTION'] | CONTRADICTION | ['CONTRADICTION'] | target_mismatch; severity_mismatch |
| RQ3-040 | ASSUMPTION | ['REQUIREMENT'] | DATA_AVAILABILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-042 | REQUIREMENT | ['ASSUMPTION'] | LATENCY | ['LATENCY'] | target_mismatch |
| RQ3-043 | CLAIM | ['REQUIREMENT'] | EVALUATION | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-044 | CONSTRAINT | ['ASSUMPTION'] | SCOPE | ['SCOPE'] | target_mismatch |
| RQ3-047 | DECISION | ['ASSUMPTION'] | DEPLOYMENT | ['DEPLOYMENT'] | target_mismatch |
| RQ3-048 | ARCHITECTURE | ['ASSUMPTION'] | RELIABILITY | ['RELIABILITY'] | target_mismatch |
| RQ3-049 | DECISION | ['ASSUMPTION'] | TECHNOLOGY_JUSTIFICATION | ['TECHNOLOGY_JUSTIFICATION'] | target_mismatch |
| RQ3-050 | ARCHITECTURE | ['ASSUMPTION'] | ARCHITECTURE_MISMATCH | ['ARCHITECTURE_MISMATCH', 'LATENCY'] | target_mismatch |
| RQ3-051 | CONSTRAINT | ['REQUIREMENT'] | TIMELINE | ['EvaluationAttackGenerator'] | attack_not_detected |
| RQ3-052 | REQUIREMENT | ['REQUIREMENT'] | SECURITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-054 | CONSTRAINT | ['ASSUMPTION'] | COST | ['COST', 'TECHNOLOGY_JUSTIFICATION'] | target_mismatch; severity_mismatch |
| RQ3-055 | REQUIREMENT | ['ASSUMPTION'] | REQUIREMENT_AMBIGUITY | ['REQUIREMENT_AMBIGUITY'] | target_mismatch |
| RQ3-056 | DECISION | ['ASSUMPTION'] | DEPENDENCY | ['DEPENDENCY'] | target_mismatch; severity_mismatch |
| RQ3-057 | CLAIM | ['REQUIREMENT'] | RESOURCE_FEASIBILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-058 | REQUIREMENT | ['ASSUMPTION'] | CONTRADICTION | ['CONTRADICTION'] | target_mismatch; severity_mismatch |
| RQ3-060 | ASSUMPTION | ['REQUIREMENT'] | DATA_AVAILABILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-062 | REQUIREMENT | ['ASSUMPTION'] | LATENCY | ['LATENCY'] | target_mismatch |
| RQ3-063 | CLAIM | ['REQUIREMENT'] | EVALUATION | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-064 | CONSTRAINT | ['ASSUMPTION'] | SCOPE | ['SCOPE'] | target_mismatch |
| RQ3-067 | DECISION | ['ASSUMPTION'] | DEPLOYMENT | ['DEPLOYMENT'] | target_mismatch |
| RQ3-068 | ARCHITECTURE | ['ASSUMPTION'] | RELIABILITY | ['RELIABILITY'] | target_mismatch |
| RQ3-069 | DECISION | ['ASSUMPTION'] | TECHNOLOGY_JUSTIFICATION | ['TECHNOLOGY_JUSTIFICATION'] | target_mismatch |
| RQ3-070 | ARCHITECTURE | ['ASSUMPTION'] | ARCHITECTURE_MISMATCH | ['ARCHITECTURE_MISMATCH', 'LATENCY'] | target_mismatch |
| RQ3-071 | CONSTRAINT | ['REQUIREMENT'] | TIMELINE | ['EvaluationAttackGenerator'] | attack_not_detected |
| RQ3-072 | REQUIREMENT | ['REQUIREMENT'] | SECURITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-074 | CONSTRAINT | ['ASSUMPTION'] | COST | ['COST', 'TECHNOLOGY_JUSTIFICATION'] | target_mismatch; severity_mismatch |
| RQ3-075 | REQUIREMENT | ['ASSUMPTION'] | REQUIREMENT_AMBIGUITY | ['REQUIREMENT_AMBIGUITY'] | target_mismatch |
| RQ3-076 | DECISION | ['ASSUMPTION'] | DEPENDENCY | ['DEPENDENCY'] | target_mismatch; severity_mismatch |
| RQ3-077 | CLAIM | ['REQUIREMENT'] | RESOURCE_FEASIBILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-078 | REQUIREMENT | ['ASSUMPTION'] | CONTRADICTION | ['CONTRADICTION'] | target_mismatch; severity_mismatch |
| RQ3-080 | ASSUMPTION | ['REQUIREMENT'] | DATA_AVAILABILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-082 | REQUIREMENT | ['ASSUMPTION'] | LATENCY | ['LATENCY'] | target_mismatch |
| RQ3-083 | CLAIM | ['REQUIREMENT'] | EVALUATION | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-084 | CONSTRAINT | ['ASSUMPTION'] | SCOPE | ['SCOPE'] | target_mismatch |
| RQ3-087 | DECISION | ['ASSUMPTION'] | DEPLOYMENT | ['DEPLOYMENT'] | target_mismatch |
| RQ3-088 | ARCHITECTURE | ['ASSUMPTION'] | RELIABILITY | ['RELIABILITY'] | target_mismatch |
| RQ3-089 | DECISION | ['ASSUMPTION'] | TECHNOLOGY_JUSTIFICATION | ['TECHNOLOGY_JUSTIFICATION'] | target_mismatch |
| RQ3-090 | ARCHITECTURE | ['ASSUMPTION'] | ARCHITECTURE_MISMATCH | ['ARCHITECTURE_MISMATCH', 'LATENCY'] | target_mismatch |
| RQ3-091 | CONSTRAINT | ['REQUIREMENT'] | TIMELINE | ['EvaluationAttackGenerator'] | attack_not_detected |
| RQ3-092 | REQUIREMENT | ['REQUIREMENT'] | SECURITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-094 | CONSTRAINT | ['ASSUMPTION'] | COST | ['COST', 'TECHNOLOGY_JUSTIFICATION'] | target_mismatch; severity_mismatch |
| RQ3-095 | REQUIREMENT | ['ASSUMPTION'] | REQUIREMENT_AMBIGUITY | ['REQUIREMENT_AMBIGUITY'] | target_mismatch |
| RQ3-096 | DECISION | ['ASSUMPTION'] | DEPENDENCY | ['DEPENDENCY'] | target_mismatch; severity_mismatch |
| RQ3-097 | CLAIM | ['REQUIREMENT'] | RESOURCE_FEASIBILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-098 | REQUIREMENT | ['ASSUMPTION'] | CONTRADICTION | ['CONTRADICTION'] | target_mismatch; severity_mismatch |
| RQ3-100 | ASSUMPTION | ['REQUIREMENT'] | DATA_AVAILABILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-102 | REQUIREMENT | ['ASSUMPTION'] | LATENCY | ['LATENCY'] | target_mismatch |
| RQ3-103 | CLAIM | ['REQUIREMENT'] | EVALUATION | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-104 | CONSTRAINT | ['ASSUMPTION'] | SCOPE | ['SCOPE'] | target_mismatch |
| RQ3-107 | DECISION | ['ASSUMPTION'] | DEPLOYMENT | ['DEPLOYMENT'] | target_mismatch |
| RQ3-108 | ARCHITECTURE | ['ASSUMPTION'] | RELIABILITY | ['RELIABILITY'] | target_mismatch |
| RQ3-109 | DECISION | ['ASSUMPTION'] | TECHNOLOGY_JUSTIFICATION | ['TECHNOLOGY_JUSTIFICATION'] | target_mismatch |
| RQ3-110 | ARCHITECTURE | ['ASSUMPTION'] | ARCHITECTURE_MISMATCH | ['ARCHITECTURE_MISMATCH', 'LATENCY'] | target_mismatch |
| RQ3-111 | CONSTRAINT | ['REQUIREMENT'] | TIMELINE | ['EvaluationAttackGenerator'] | attack_not_detected |
| RQ3-112 | REQUIREMENT | ['REQUIREMENT'] | SECURITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-114 | CONSTRAINT | ['ASSUMPTION'] | COST | ['COST', 'TECHNOLOGY_JUSTIFICATION'] | target_mismatch; severity_mismatch |
| RQ3-115 | REQUIREMENT | ['ASSUMPTION'] | REQUIREMENT_AMBIGUITY | ['REQUIREMENT_AMBIGUITY'] | target_mismatch |
| RQ3-116 | DECISION | ['ASSUMPTION'] | DEPENDENCY | ['DEPENDENCY'] | target_mismatch; severity_mismatch |
| RQ3-117 | CLAIM | ['REQUIREMENT'] | RESOURCE_FEASIBILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |
| RQ3-118 | REQUIREMENT | ['ASSUMPTION'] | CONTRADICTION | ['CONTRADICTION'] | target_mismatch; severity_mismatch |
| RQ3-120 | ASSUMPTION | ['REQUIREMENT'] | DATA_AVAILABILITY | ['EvaluationAttackGenerator', 'TimelineAttackGenerator'] | attack_not_detected |

## Failure mode counts

- `target_mismatch`: 42
- `attack_not_detected`: 30
- `target_mismatch; severity_mismatch`: 18
