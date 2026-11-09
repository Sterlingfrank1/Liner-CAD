# 箱体类（箱体、箱盖、泵体、阀体、轴承座）

**适用**：有内腔、轴承孔、凸台、凸缘和安装底板的铸件。几何来自 3D 模型（`model.py`），视图、剖视、尺寸按下面的规定画；不要手拼轮廓和剖面线。

## 主视图
按工作位置放，选最能反映形状特征的方向（轴承孔 / 腔的端面、油口朝向），少虚线、孔系看得见。常用主 + 俯 + 左；个别结构（凸台端面、油口）另投一个基本视图当局部视图，只标要表达的部分。

## 视图与剖视方案
- 内腔、孔系多：**全剖** `V.project(cut="full", depth=)`，剖切面过主要孔轴线或对称面（`depth` = 剖切面离原点、朝观察者的距离）；对称又要保留外形用**半剖** `cut="half"`；只有个别孔 / 凸台要看内部用**局部剖** `region=[(u, v), ...]`（波浪线自动画）。
- 外形视图和剖视图都先用 `hidden=False`，虚线能省视图时才开。3D 来源不做阶梯 / 旋转剖、移出断面，要用时走 2D 原生画法。

## 尺寸基准与标注
- 基准：长、宽方向取对称面或主要轴承孔轴线，高度方向取**底面 / 安装面**；**轴承孔中心高从底面注**，孔间距注轴线距离（`role="position"`，`datum=` 轴线中心线）。
- 先定形（壁厚、孔径、凸台径和高、腔深），再定位（孔系、凸台），最后总体 L / W / H（`role="overall"`）；同一尺寸只标一次，标在最清楚的视图；壁厚在剖视里标。
- 直径标在非圆轮廓或剖视上（轴承孔带 `tol="H7"`）；圆视图只标均布孔（`prefix="4×"`、`suffix=" EQS"`）和分布圆；半圆孔的直径标在开口线端点上；小尺寸 `side="inside"`。
- 轴承孔、结合面写粗糙度；孔轴线对底面平行度、端面对轴线垂直度用 `datum` + `gtol`。`value=` 写参数表达式（`value=A - 2 * s`），改参数时尺寸跟着走。

## 规定画法
- **肋板**：纵剖时不画剖面线，轮廓画粗实线：`ribs=[[(u, v), ...]]`（肋在剖面中的多边形，视图坐标）；横剖的肋照常画剖面线。
- **铸造圆角、过渡线**：模型里倒圆，相切边自动成 `conv` 细实线；不逐个标 R，写进技术要求；相贯线随投影出现。
- **螺孔**：模型按小径钻孔；先 `.suppress()` 投影出的小径圆，再 `thread_end(kind="int")` + `dim.hole`（代号 `4×M8-6H↧16`）。

## 3D 工作流
- `d.model("model.py")`；`model(**P)` 返回 build123d 形体，参数与 `d.params` 同名，X 长、Y 宽、Z 高。每个视图 `V.project(...)` → `E.<视图>.model.<k>`。
- 选边用 `d.q`（按几何，不靠序号）：整圆 `d.q.circles(view=, r=)`；圆被接缝或相贯截成圆弧时用 `d.q.edges(view=).where(r=).near(x, y, r=0.3).one()`，`dim.dia(circle=)` 认圆弧。
- 投影不带中心线：每个圆都要 `center_mark` / `centerline`（分布圆 `v.circle(role="center")`）。剖切面恰好过圆柱轴线时若 `IndexError`，`depth` 偏 0.01 mm。
- `lcad render` 看图；挤了用 `front.move(dx=, dy=)` 整组挪、`row=` 排尺寸，重叠按 `lcad check` 的提示换侧 / 换排。

## 常见技术要求
铸件：时效处理；不得有砂眼、气孔、裂纹；未注铸造圆角 R3~R5；结合面不平度。`d.rough_default(12.5)`；`d.general_tol("m")`。

## 常见错误
1. 手拼轮廓、手画剖面线；肋板纵剖画了剖面线。
2. 轴承孔中心高从孔上母线注；孔间距标成孔边距离。
3. 半圆孔用整圆直径线，圆视图的几条引线互相穿过。
4. 孔、凸台直径漏标（完整性对照列出 `missing`）；壁厚 / 腔宽 / 箱宽标成封闭链。
5. 配合孔没有粗糙度；基准字母没定义；外形视图满屏虚线。

## 工具
`d.model` `V.project(cut, depth, region, ribs, hidden, half)` `d.q.circles / arcs / edges` `v.centerline` `v.center_mark` `v.circle` `v.thread_end` `dim.dia / linear / hole` `v.datum` `v.gtol` `v.rough` `d.rough_default` `d.general_tol`

## 范例
`lcad init <目录> --from pump_body`（全剖 + 肋板 `ribs=` + 法兰孔、基准 A / B、平行度 / 垂直度）· `--from gear_cover`（全剖 + 俯视外形 + 左视）
