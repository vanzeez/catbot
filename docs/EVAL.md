# Laya evaluation — checkpoint checkpoints/catbot-laya

Test rows: 704 (data/finetune/test.jsonl, 20% held out by request). Latency p50 52 ms, p95 62 ms.

| question | lang | accuracy | n |
| --- | --- | --- | --- |
| confirm_reply | en | 0.950 | 60 |
| confirm_reply | hi | 0.922 | 51 |
| confirm_reply | hinglish | 1.000 | 37 |
| confirm_reply | ta | 0.862 | 58 |
| risk_tier | en | 0.985 | 335 |
| verify_call | en | 0.969 | 163 |

| question | accuracy | bar | ECE | pass |
| --- | --- | --- | --- | --- |
| risk_tier | 0.985 | 0.90 | 0.008 | yes |
| verify_call | 0.969 | 0.85 | 0.019 | yes |
| confirm_reply | 0.927 | 0.90 | 0.051 | yes |

risk_tier confusion (rows = gold, columns = predicted):

| gold \ pred | T0 | T1 | T2 | T3 |
| --- | --- | --- | --- | --- |
| T0 | 90 | 0 | 0 | 0 |
| T1 | 0 | 81 | 0 | 0 |
| T2 | 0 | 0 | 112 | 0 |
| T3 | 4 | 0 | 1 | 47 |

**Bars met.** Set `ROUTER=laya` in `.env`.
