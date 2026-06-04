# Benchmark Report

Study ID: `study_002`

## Overall

| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 20 | 50.0% | 50.0% | 6 | 3 | 4.84 | 3082 | 38.63 |

## By Backend

| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| custom | 7 | 57.1% | 42.9% | 1 | 1 | 5.15 | 665 | 34.56 |
| ollama | 10 | 60.0% | 40.0% | 2 | 2 | 6.07 | 2417 | 41.18 |
| unknown-backend | 3 | 0.0% | 100.0% | 3 | 0 | 0.00 | 0 | 0.00 |

## By Model

| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| custom/deepseek/deepseek-r1-0528-qwen3-8b | 2 | 0.0% | 100.0% | 1 | 1 | 10.56 | 122 | 5.78 |
| custom/qwen2.5-coder-7b-instruct | 5 | 80.0% | 20.0% | 0 | 0 | 2.99 | 543 | 41.76 |
| ollama/deepseek-r1:latest | 5 | 40.0% | 60.0% | 2 | 2 | 9.44 | 1874 | 38.82 |
| ollama/qwen2.5-coder:7b-triagecore | 5 | 80.0% | 20.0% | 0 | 0 | 2.70 | 543 | 43.53 |
| unknown-backend/unknown-model | 3 | 0.0% | 100.0% | 3 | 0 | 0.00 | 0 | 0.00 |

## By Category

| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| log_summary | 4 | 75.0% | 25.0% | 1 | 0 | 3.48 | 796 | 61.68 |
| python_generation | 4 | 50.0% | 50.0% | 2 | 2 | 10.48 | 475 | 13.82 |
| python_repair | 4 | 50.0% | 50.0% | 2 | 1 | 3.30 | 520 | 38.78 |
| safety_handoff | 4 | 0.0% | 100.0% | 0 | 0 | 0.00 | 0 | 0.00 |
| structured_extraction | 4 | 75.0% | 25.0% | 1 | 0 | 6.94 | 1291 | 48.52 |
