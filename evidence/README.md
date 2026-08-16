# Evidence index

Only sanitized, genuine experiment outputs belong here. The collection scripts
write raw text and CSV files under `evidence/raw/`, which remains ignored until
the files have been reviewed for secrets. Approved screenshots will be indexed
by environment, run, timestamp, and the claim they demonstrate.

## Validated Minikube results

Three experiments were executed on 16 August 2026 with 180 seconds of load and
300 seconds of recovery. Every run started at one replica, reached the configured
maximum of six replicas, and returned to one replica. The sanitized measurements
are stored in `minikube-summary.csv`; raw samples remain excluded until the final
evidence review.

| Run | First scale-up | Peak CPU | Maximum | Return to one |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 49 s | 378% | 6 pods | 192 s |
| 2 | 85 s | 476% | 6 pods | 203 s |
| 3 | 65 s | 344% | 6 pods | 143 s |
