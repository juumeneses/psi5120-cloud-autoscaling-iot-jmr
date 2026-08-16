# TA1 article

The final submission PDF is `output/psi5120-ta1-julia-meneses-roberto.pdf`.
It uses an IEEE-inspired two-column layout, is written in English, and contains
six visually reviewed pages.

Rebuild it with the workspace Python runtime after installing ReportLab:

```bash
python -m pip install reportlab==4.4.3
python articles/build_ta1_article.py
```

The tables in the article reproduce the sanitized values in
`evidence/minikube-summary.csv` and `evidence/eks-summary.csv`. Do not replace
them with estimated or unvalidated measurements.
