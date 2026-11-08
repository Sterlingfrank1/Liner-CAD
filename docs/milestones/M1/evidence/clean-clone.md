# 干净 clone 验收（main d724d02）

```
git clone https://github.com/Sterlingfrank1/Liner-CAD && uv sync --extra 3d
uv run pytest -q
822 passed in 270.62s (0:04:30)
uv run python evals/run.py
{"cases": 30, "built": 30, "zero_error_rate": 1.0, "geometry_pass_rate": 1.0, "violations": 0, "first_pass_rate": null, "mean_rounds": null, "passed": 30}
```
