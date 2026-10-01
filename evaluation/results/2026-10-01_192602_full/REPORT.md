# VibePrompt Evaluation Report

Run directory: `evaluation/results/2026-10-01_192602_full`

## Experiments

### rq1

- status: `COMPLETED`
```json
{
  "baseline_a": {
    "requirement_f1": {
      "n": 60,
      "mean": 0.3055555555555555,
      "std": 0.27498597046143514,
      "ci95_low": 0.23597450473175108,
      "ci95_high": 0.37513660637935997,
      "median": 0.25
    },
    "rejected_leakage": {
      "n": 60,
      "mean": 0.3333333333333333,
      "std": 0.4714045207910317,
      "ci95_low": 0.21405153192109716,
      "ci95_high": 0.45261513474556947,
      "median": 0.0
    },
    "n_scenarios": 60
  },
  "baseline_b": {
    "requirement_f1": {
      "n": 60,
      "mean": 0.4666666666666667,
      "std": 0.4109609335312651,
      "ci95_low": 0.36267920303478174,
      "ci95_high": 0.5706541302985516,
      "median": 0.4
    },
    "rejected_leakage": {
      "n": 60,
      "mean": 0.3333333333333333,
      "std": 0.4714045207910317,
      "ci95_low": 0.21405153192109716,
      "ci95_high": 0.45261513474556947,
      "median": 0.0
    },
    "n_scenarios": 60
  },
  "vibeprompt": {
    "requirement_f1": {
      "n": 60,
      "mean": 1.0,
      "std": 0.0,
      "ci95_low": 1.0,
      "ci95_high": 1.0,
      "median": 1.0
    },
    "rejected_leakage": {
      "n": 60,
      "mean": 0.0,
      "std": 0.0,
      "ci95_low": 0.0,
      "ci95_high": 0.0,
      "median": 0.0
    },
    "n_scenarios": 60
  }
}
```

### rq2

- status: `COMPLETED`
```json
{
  "impact_f1": {
    "n": 50,
    "mean": 0.21904761904761905,
    "std": 0.33819582675361337,
    "ci95_low": 0.1253045185607625,
    "ci95_high": 0.31279071953447557,
    "median": 0.0
  },
  "broken_traceability_rate": {
    "n": 50,
    "mean": 0.0,
    "std": 0.0,
    "ci95_low": 0.0,
    "ci95_high": 0.0,
    "median": 0.0
  },
  "n_scenarios": 50
}
```

### rq3

- status: `COMPLETED`
```json
{
  "no_grill": {
    "critical_issue_detection_rate": {
      "n": 50,
      "mean": 0.0,
      "std": 0.0,
      "ci95_low": 0.0,
      "ci95_high": 0.0,
      "median": 0.0
    },
    "attack_precision": {
      "n": 50,
      "mean": 1.0,
      "std": 0.0,
      "ci95_low": 1.0,
      "ci95_high": 1.0,
      "median": 1.0
    },
    "false_positive_attack_rate": {
      "n": 50,
      "mean": 0.0,
      "std": 0.0,
      "ci95_low": 0.0,
      "ci95_high": 0.0,
      "median": 0.0
    },
    "n_scenarios": 50
  },
  "checklist_grill": {
    "critical_issue_detection_rate": {
      "n": 50,
      "mean": 0.62,
      "std": 0.2135415650406262,
      "ci95_low": 0.5608092980274774,
      "ci95_high": 0.6791907019725226,
      "median": 0.5
    },
    "attack_precision": {
      "n": 50,
      "mean": 1.0,
      "std": 0.0,
      "ci95_low": 1.0,
      "ci95_high": 1.0,
      "median": 1.0
    },
    "false_positive_attack_rate": {
      "n": 50,
      "mean": 0.0,
      "std": 0.0,
      "ci95_low": 0.0,
      "ci95_high": 0.0,
      "median": 0.0
    },
    "n_scenarios": 50
  },
  "adversarial_grill": {
    "critical_issue_detection_rate": {
      "n": 50,
      "mean": 0.12,
      "std": 0.32496153618543844,
      "ci95_low": 0.0299252577022837,
      "ci95_high": 0.21007474229771628,
      "median": 0.0
    },
    "attack_precision": {
      "n": 50,
      "mean": 1.0,
      "std": 0.0,
      "ci95_low": 1.0,
      "ci95_high": 1.0,
      "median": 1.0
    },
    "false_positive_attack_rate": {
      "n": 50,
      "mean": 0.0,
      "std": 0.0,
      "ci95_low": 0.0,
      "ci95_high": 0.0,
      "median": 0.0
    },
    "n_scenarios": 50
  }
}
```

### rq4

- status: `COMPLETED`
```json
{
  "label_accuracy": {
    "n": 50,
    "mean": 1.0,
    "std": 0.0,
    "ci95_low": 1.0,
    "ci95_high": 1.0,
    "median": 1.0
  },
  "unsupported_decision_rate": {
    "n": 50,
    "mean": 0.2,
    "std": 0.4,
    "ci95_low": 0.08912565670994936,
    "ci95_high": 0.31087434329005065,
    "median": 0.0
  },
  "contradicted_decision_rate": {
    "n": 50,
    "mean": 0.2,
    "std": 0.4,
    "ci95_low": 0.08912565670994936,
    "ci95_high": 0.31087434329005065,
    "median": 0.0
  },
  "unverified_decision_rate": {
    "n": 50,
    "mean": 0.2,
    "std": 0.4,
    "ci95_low": 0.08912565670994936,
    "ci95_high": 0.31087434329005065,
    "median": 0.0
  },
  "evidence_backed_agreement": {
    "n": 50,
    "mean": 1.0,
    "std": 0.0,
    "ci95_low": 1.0,
    "ci95_high": 1.0,
    "median": 1.0
  },
  "n_scenarios": 50,
  "provenance_note": "URL alone never counts as verified"
}
```

### rq5

- status: `NOT EXECUTED`
- reason: agent integration unavailable (set VIBEPROMPT_AGENT_CMD)
```json
{
  "n_tasks": 12,
  "requirement_coverage": null,
  "acceptance_test_pass_rate": null,
  "build_success": null,
  "test_success": null,
  "note": "Metrics populated only when an agent executes tasks"
}
```

## Limitations

- Synthetic datasets — not real-world generalization.
- RQ1 vibeprompt column is gold-state compile upper bound.
- RQ5 agent metrics are null until an agent is configured.
- Small-N CIs use normal approximation; interpret cautiously.

## Fabrication policy

This report is generated only from written `metrics.json` / `summary.json` files.
