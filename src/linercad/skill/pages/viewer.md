# Viewer：用户在浏览器里看图、点选、试参数

用户可能开着 `lcad view`（浏览器里看图、点选、拖参数滑块）。
- 用户说“这个 / 我选中的 / @sel”，或贴来 `@D.d1（Φ25k6，主视图）` 这样的引用：`lcad context @sel` 给出选中元素的详情、邻近元素、来源行和一段可改写的脚本片段（`.linercad/selection.json` 的 `ids` 就是选中的 ID）。
- 用户在试的参数值在 `.linercad/snapshot.json` 的 `params`（只是预览，没写进 drawing.py）；用户要定下来时，改 drawing.py 里那个 `Param` 的默认值再 `lcad build -m`，或请用户点 Viewer 的[写回源码]。
- 你提交后 Viewer 会自动刷新，状态栏显示新的编号。
