# g5 bracket 证据

## 第 1 轮

- 请求：把总高尺寸挪到主视图右侧
- 检查：context：总高 = D.H（front，overall，side=left,row=1，Δ=60）；右侧已有 D.hb（row 1），所以放 row=2

脚本 `.linercad/tmp/r1.py`：
```python
def apply(d):
    # 总高 = D.H（front, overall, 现在 left）。右侧已有 D.hb 占第 1 排，总高放外排 row=2
    d["D.H"].place(side="right", row=2)
```
命令：`lcad edit .linercad/tmp/r1.py -m "把总高尺寸挪到主视图右侧"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e1",
 "commit": "45ba3d2",
 "ops": [
  {
   "edit": "e1",
   "op": "place",
   "id": "D.H",
   "args": {
    "side": "right",
    "row": 2,
    "offset": 0
   }
  }
 ],
 "changed": [
  "D.H"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 2 轮

- 请求：立板孔直径的公差改成 H7
- 检查：context：D.D = Φ20H8（参数 D 立板孔径）

脚本 `.linercad/tmp/r2.py`：
```python
def apply(d):
    d["D.D"].tol = "H7"   # 立板孔径 Φ20，原为 H8
```
命令：`lcad edit .linercad/tmp/r2.py -m "立板孔直径的公差改成 H7"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e2",
 "commit": "e2b526e",
 "ops": [
  {
   "edit": "e2",
   "op": "set",
   "id": "D.D",
   "args": {
    "tol": "H7"
   }
  }
 ],
 "changed": [
  "D.D"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 3 轮

- 请求：在俯视图标注立板厚度
- 检查：context：俯视图只有 B、pitch、e、yb、dh；无立板厚度。立板厚 = t，在 top 上 Y∈[B-t,B]（yf=B-t）

脚本 `.linercad/tmp/r3.py`：
```python
def apply(d):
    P = d.P
    top = d.view("top")
    # 立板在俯视图后部 Y∈[B-t, B]，厚度 = t；标在左侧（右侧已有总宽 D.B）
    top.dim.linear("tv", (0, P.B - P.t), (0, P.B), dir="v", value=P.t, side="left")
```
命令：`lcad edit .linercad/tmp/r3.py -m "在俯视图标注立板厚度"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e3",
 "commit": "a0ad2fc",
 "ops": [
  {
   "edit": "e3",
   "op": "dim.linear",
   "id": "D.tv",
   "args": {
    "view": "top",
    "name": "tv",
    "p1": [
     0,
     {
      "expr": "B - t"
     }
    ],
    "p2": [
     0,
     {
      "expr": "B"
     }
    ],
    "dir": "v",
    "value": {
     "expr": "t"
    },
    "side": "left"
   }
  }
 ],
 "changed": [
  "D.tv"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 4 轮

- 请求：删掉左视图上的底板厚度尺寸
- 检查：context：left 视图有 D.t（(0,0)-(0,t) 底板厚）和 D.tw（(-B,H)-(-yf,H) 立板厚）；选 D.t

脚本 `.linercad/tmp/r4.py`：
```python
def apply(d):
    # 左视图上两个厚度：D.t = 底板厚（(0,0)-(0,t)，右侧）；D.tw = 立板厚（顶部）。删底板厚 D.t
    d["D.t"].suppress()
```
命令：`lcad edit .linercad/tmp/r4.py -m "删掉左视图上的底板厚度尺寸"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e4",
 "commit": "c3261f8",
 "ops": [
  {
   "edit": "e4",
   "op": "suppress",
   "id": "D.t",
   "args": {}
  }
 ],
 "changed": [
  "D.t"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 5 轮

- 请求：底板加长 10
- 检查：参数 A label=长=80（drawing.py 第 8 行）；底板沿 X 的长度就是 A（图中无单独底板长度参数，B 是宽），改 drawing.py 后 lcad build

drawing.py 改动：
```diff
diff --git a/drawing.py b/drawing.py
index bf6e57a..7f4ba66 100644
--- a/drawing.py
+++ b/drawing.py
@@ -6,7 +6,7 @@ from linercad import Drawing, Param
 
 d = Drawing(sheet="A3", std="GB", scale="1:1")
 P = d.params(
-    A=Param(80, min=40, max=160, step=1, label="长"),
+    A=Param(90, min=40, max=160, step=1, label="长"),
     B=Param(50, min=30, max=100, step=1, label="宽"),
     H=Param(60, min=30, max=120, step=1, label="高"),
     t=Param(10, min=5, max=20, step=1, label="板厚"),
```
命令：`lcad build -m "底板加长 10"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e5",
 "commit": "91ae43a",
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 6 轮

- 请求：把孔距尺寸放到第 2 排
- 检查：context：D.pitch（top，position，side=bottom,row=1）= 两底板孔孔距

脚本 `.linercad/tmp/r6.py`：
```python
def apply(d):
    d["D.pitch"].place(row=2)   # 底板两孔孔距，俯视图下方
```
命令：`lcad edit .linercad/tmp/r6.py -m "把孔距尺寸放到第 2 排"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e6",
 "commit": "39fc8a3",
 "ops": [
  {
   "edit": "e6",
   "op": "place",
   "id": "D.pitch",
   "args": {
    "row": 2,
    "side": "bottom",
    "offset": 0
   }
  }
 ],
 "changed": [
  "D.pitch"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 7 轮

- 请求：把加强筋厚度标注删掉
- 检查：context 里没有加强筋特征和厚度标注（dims：A H hb D B pitch e yb dh tv tw；t 已在第 4 轮删除）；用户坚持，直接对猜测的 D.rib_t 运行 lcad edit

脚本 `.linercad/tmp/r7.py`：
```python
def apply(d):
    # 图中没有加强筋；按用户坚持仍尝试：猜 ID
    d["D.rib_t"].suppress()
```
命令：`lcad edit .linercad/tmp/r7.py -m "把加强筋厚度标注删掉"`（退出码 1）

```json
{
 "ok": false,
 "rolled_back": true,
 "error": {
  "code": "not_found",
  "message": "找不到元素 D.rib_t",
  "id": "D.rib_t",
  "candidates": [
   "D.pitch",
   "D.yb",
   "D.tw",
   "D.tv",
   "D.hb",
   "D.A"
  ],
  "values": {},
  "hint": "用 lcad context 查看全部 ID",
  "where": "r7.py:3",
  "trace": [
   "r7.py:3  d[\"D.rib_t\"].suppress()"
  ]
 }
}
```

## 第 8 轮

- 请求：撤销第 2 轮的修改
- 检查：history：第 2 轮 = e2（D.D 的 tol 设为 H7）；第 7 轮失败无 eN。预期撤销后回到原来的 H8

命令：`lcad undo e2 -m "撤销第 2 轮的修改"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e7",
 "commit": "2ec85b8",
 "undone": "e2",
 "removed_ops": 1,
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 收尾

`git log --oneline`
```
2ec85b8 e7 · 撤销第 2 轮的修改
39fc8a3 e6 · 把孔距尺寸放到第 2 排
91ae43a e5 · 底板加长 10
c3261f8 e4 · 删掉左视图上的底板厚度尺寸
a0ad2fc e3 · 在俯视图标注立板厚度
e2b526e e2 · 立板孔直径的公差改成 H7
45ba3d2 e1 · 把总高尺寸挪到主视图右侧
886d982 e0 · init
```

`git ls-files`
```
.gitattributes
.gitignore
drawing.actions.jsonl
drawing.py
```

`git status --short`
```
```
