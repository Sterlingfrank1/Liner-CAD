# 干净 clone 验收（main 06c56be）

```
git clone https://github.com/Sterlingfrank1/Liner-CAD && uv sync --extra 3d
uv run pytest -q
848 passed in 254.27s (0:04:14)
uv run ruff check
All checks passed!
uv run python evals/run.py
{"cases": 30, "built": 30, "zero_error_rate": 1.0, "geometry_pass_rate": 1.0, "violations": 0, "first_pass_rate": null, "mean_rounds": null, "passed": 30}
```

滑块预览（服务端重建 + 检查 + SVG，见 slider-timing.json）：shaft p50 103 ms / max 182 ms；sleeve 32 / 62；flange 48 / 80；pulley 61 / 95。目标 < 500 ms。每例 30 次随机取值，其中违反 rule 的被拒绝且不应用（shaft 4、sleeve 4、flange 9、pulley 6）。
