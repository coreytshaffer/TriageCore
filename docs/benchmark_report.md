# Benchmark Report

## Overall

| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 16 | 31.2% | 68.8% | 8 | 0 | 1.27 | 943 | 44.81 |

## By Model

| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/deepseek-r1:latest | 2 | 50.0% | 50.0% | 0 | 0 | 4.18 | 418 | 50.01 |
| ollama/qwen2.5-coder:7b | 1 | 0.0% | 100.0% | 0 | 0 | 0.00 | 0 | 0.00 |
| ollama/qwen2.5-coder:7b-triagecore | 5 | 80.0% | 20.0% | 0 | 0 | 2.41 | 525 | 43.51 |
| unknown-backend/unknown-model | 8 | 0.0% | 100.0% | 8 | 0 | 0.00 | 0 | 0.00 |

## By Category

| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| log_summary | 3 | 66.7% | 33.3% | 1 | 0 | 3.74 | 601 | 56.92 |
| python_generation | 4 | 25.0% | 75.0% | 3 | 0 | 0.71 | 79 | 27.74 |
| python_repair | 3 | 33.3% | 66.7% | 2 | 0 | 0.97 | 106 | 36.58 |
| safety_handoff | 3 | 0.0% | 100.0% | 0 | 0 | 0.00 | 0 | 0.00 |
| structured_extraction | 3 | 33.3% | 66.7% | 2 | 0 | 1.14 | 157 | 45.88 |
