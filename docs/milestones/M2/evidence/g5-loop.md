# G5 闭环实测：点选 → @ID → 独立 agent 修改 → Viewer 自动刷新

环境：干净 clone（main `06c56be`，之后合入 #52 的 `bd1c995`），`lcad init` 出 shaft、flange 两个范例目录，`lcad view` 分别在 127.0.0.1:8771 / 8772。浏览器操作在 Claude 内置浏览器面板里完成（真实鼠标点选、拖滑块、点按钮），截图如下。独立 agent（Sonnet，新上下文）只拿到 `lcad skill` 与用户原话，看不到浏览器。

| 轮 | 图 | 在 Viewer 里点选 | 用户原话（给 agent） | agent 做法 | 结果 | Viewer |
|---|---|---|---|---|---|---|
| A1 | shaft | 总长 `D.L`（`@D.L（200，主视图）`） | 把我选中的这个尺寸挪到图形上方。 | `context @sel` → 临时脚本 `place(side="top")` → `lcad edit` | e1，0 error、1 warn（挪上去后与退刀槽注重叠，橙色） | 自动刷新到 e1，状态栏 `e1 · 1 个警告 · …`，`shaft-r1-*.png` |
| A2 | shaft | 橙色的退刀槽注 `D.ug` | 我选中的这个标注和总长尺寸重叠了，把它挪开。 | `place(dir=…)` 两次重放失败（**harness 缺陷**：引线式尺寸的 place 记了不存在的 offset），改 drawing.py 后 `build -m` | e2，2 warn（未解决） | 自动刷新到 e2 |
| — | — | — | — | 修复：#52（place 不再给引线式尺寸记 offset；`edit` 认图纸目录相对路径），干净 clone `git pull`，重启 Viewer | — | — |
| A3 | shaft | `D.ug` | 我选中的退刀槽标注还和别的尺寸重叠，把它挪到不重叠的地方。 | 渲染看图后 `place(dir=90, length=42)`，相对路径脚本，一次成功 | e3，0 error、0 warn | 自动刷新到 e3，`shaft-r3-refreshed-e3.png` |
| B1 | flange | 螺栓孔注 `D.holes`（4×Φ12 EQS） | 把我选中的螺栓孔改成 6 个，孔径 Φ11。 | 按 `context @sel` 给的源码行改 drawing.py（n、dh、前缀）→ `build -m` | e1，0/0 | 自动刷新，滑块 dh 变 11，`flange-r1-refreshed-e1.png` |
| B2 | flange | 孔径 `D.d0`（Φ30H7） | 我选中的这个孔径公差改成 H8，代号和偏差都标出来。 | 临时脚本 `tol="H8"; tol_show="both"` → `edit` | e2，0 error、1 warn（文字变长与 Φ60 重叠，橙色） | 自动刷新，检查器显示新公差与问题，`flange-r2-refreshed-e2.png` |
| W | flange | 拖“总长 L”滑块 40 → 49 | —（用户自己） | 预览 135.5 ms（不写文件）；点[写回源码] | e3 `参数 L=49（Viewer 写回）`：只改 `L=Param(` 一行，恰好一个 commit | `flange-slider-preview-L49.png` |
| R | flange | 拖“凸台外径 Dh”到 120 | — | 违反 `Dh < pcd - dh`：滑块标红、给出原因，不应用 | 无改动 | `flange-slider-rule-violation.jpg` |

另：不带令牌的 POST（curl）返回 403。

## agent 指出的 skill / harness 问题

- 已修（#52）：引线式尺寸 `place(dir=, length=)` 重放失败；`lcad -C 目录 edit 相对路径` 找不到脚本。
- 待改：均布孔个数既在 `holes_on_circle(n=)` 又在尺寸前缀 `"4×"`，两处要一起改；`tol_show="both"` 打印哪些偏差 skill 没说；没有“只预览不提交”的布局试探（agent 只能先渲染再猜长度）；引线穿过尺寸线不报检查。
