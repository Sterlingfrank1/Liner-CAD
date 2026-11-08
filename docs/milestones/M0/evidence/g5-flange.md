# g5 flange 证据

## 第 1 轮

- 请求：把凸台外径尺寸挪到主视图另一侧
- 检查：context：凸台外径是 D.Dh（Φ60, front, side=right,row=2）；左侧已有 D.D（Φ120,row 1）

脚本 `.linercad/tmp/r1.py`：
```python
def apply(d):
    # 凸台外径 = D.Dh，现在在主视图右侧，换到左侧
    d["D.Dh"].place(side="left")
```
命令：`lcad edit .linercad/tmp/r1.py -m "把凸台外径尺寸挪到主视图另一侧"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e1",
 "commit": "aca65a9",
 "ops": [
  {
   "edit": "e1",
   "op": "place",
   "id": "D.Dh",
   "args": {
    "side": "left",
    "row": 1,
    "offset": 0
   }
  }
 ],
 "changed": [
  "D.Dh"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 2 轮

- 请求：外径加公差 h11
- 检查：参数 D label=外径=120 -> D.D(Φ120)；Dh label=凸台外径，用户没说凸台，故取 D.D

脚本 `.linercad/tmp/r2.py`：
```python
def apply(d):
    # 参数 D 的 label 就是"外径"（Φ120）；凸台外径是 Dh，用户这里没说"凸台"
    d["D.D"].tol = "h11"
```
命令：`lcad edit .linercad/tmp/r2.py -m "外径加公差 h11"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e2",
 "commit": "c82bcf6",
 "ops": [
  {
   "edit": "e2",
   "op": "set",
   "id": "D.D",
   "args": {
    "tol": "h11"
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

- 请求：在主视图标注凸台长度
- 检查：context：无凸台长度尺寸；参数 T=15 盘厚，L=40 总长，凸台长 = L-T = 25，在 front 上 x∈[T,L]、半径 Dh/2

脚本 `.linercad/tmp/r3.py`：
```python
def apply(d):
    P = d.P
    front = d.view("front")
    Rh = P.Dh / 2
    # 凸台长度 = L - T，沿轴向 x 从 T 到 L；取凸台上外圆母线
    front.dim.linear("Lb", (P.T, Rh), (P.L, Rh), dir="h", value=P.L - P.T, side="top")
```
命令：`lcad edit .linercad/tmp/r3.py -m "在主视图标注凸台长度"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e3",
 "commit": "5e4449a",
 "ops": [
  {
   "edit": "e3",
   "op": "dim.linear",
   "id": "D.Lb",
   "args": {
    "view": "front",
    "name": "Lb",
    "p1": [
     {
      "expr": "T"
     },
     {
      "expr": "Dh / 2"
     }
    ],
    "p2": [
     {
      "expr": "L"
     },
     {
      "expr": "Dh / 2"
     }
    ],
    "dir": "h",
    "value": {
     "expr": "L - T"
    },
    "side": "top"
   }
  }
 ],
 "changed": [
  "D.Lb"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 4 轮

- 请求：删掉第 3 条技术要求
- 检查：context：N.tech.1..3，第 3 条是 N.tech.3（文字在 context 里因 stdout 编码显示乱码，以 drawing.py 为准：未注尺寸公差按 GB/T 1804-m）

脚本 `.linercad/tmp/r4.py`：
```python
def apply(d):
    d["N.tech.3"].suppress()   # 第 3 条：未注尺寸公差按 GB/T 1804-m。
```
命令：`lcad edit .linercad/tmp/r4.py -m "删掉第 3 条技术要求"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e4",
 "commit": "480cc6f",
 "ops": [
  {
   "edit": "e4",
   "op": "suppress",
   "id": "N.tech.3",
   "args": {}
  }
 ],
 "changed": [
  "N.tech.3"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 5 轮

- 请求：外径加大 10
- 检查：参数 D=120（label 外径，drawing.py 第 8 行），是参数值，改 drawing.py 后 lcad build；rule pcd+dh<D 130 仍满足

drawing.py 改动：
```diff
diff --git a/drawing.py b/drawing.py
index ddf88b4..f2a384c 100644
--- a/drawing.py
+++ b/drawing.py
@@ -5,7 +5,7 @@ from linercad import Drawing, Param
 
 d = Drawing(sheet="A3", std="GB", scale="1:1")
 P = d.params(
-    D=Param(120, min=80, max=200, step=1, label="外径"),
+    D=Param(130, min=80, max=200, step=1, label="外径"),
     Dh=Param(60, min=30, max=120, step=1, label="凸台外径", rule="Dh < pcd - dh"),
     d0=Param(30, min=10, max=60, step=0.5, label="中心孔径", tol="H7", rule="d0 < Dh"),
     T=Param(15, min=8, max=40, step=1, label="盘厚"),
```
命令：`lcad build -m "外径加大 10"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e5",
 "commit": "fd22878",
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 6 轮

- 请求：把节圆直径的引出角度换到左上方
- 检查：context D.pcd：circle 视图 left，placement.at=null，自动解析为 45°（右上）；左上方取 135°

脚本 `.linercad/tmp/r6.py`：
```python
def apply(d):
    # 节圆直径 D.pcd 当前自动 at=45（右上）；左上 = 135°
    d["D.pcd"].place(at=135)
```
命令：`lcad edit .linercad/tmp/r6.py -m "把节圆直径的引出角度换到左上方"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e6",
 "commit": "d0c138d",
 "ops": [
  {
   "edit": "e6",
   "op": "place",
   "id": "D.pcd",
   "args": {
    "at": 135
   }
  }
 ],
 "changed": [
  "D.pcd"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 7 轮

- 请求：把槽宽尺寸改成 8
- 检查：context 里没有槽特征，也没有槽宽尺寸（dims：T L D Dh d0 holes pcd Lb）；用户坚持，直接对猜测的 D.slot_w 运行 lcad edit

脚本 `.linercad/tmp/r7.py`：
```python
def apply(d):
    # 图中没有槽；按用户坚持仍尝试：先猜 ID
    d["D.slot_w"].text = "8"
```
命令：`lcad edit .linercad/tmp/r7.py -m "把槽宽尺寸改成 8"`（退出码 1）

```json
{
 "ok": false,
 "rolled_back": true,
 "error": {
  "code": "not_found",
  "message": "找不到元素 D.slot_w",
  "id": "D.slot_w",
  "candidates": [
   "D.T",
   "D.L",
   "D.D",
   "D.Dh",
   "D.d0",
   "D.holes"
  ],
  "values": {},
  "hint": "用 lcad context 查看全部 ID",
  "where": "r7.py:3",
  "trace": [
   "r7.py:3  d[\"D.slot_w\"].text = \"8\""
  ]
 }
}
```

## 第 8 轮

- 请求：撤销第 3 轮的修改
- 检查：history：第 3 轮 = e3（加 D.Lb 凸台长度）；第 7 轮失败无 eN

命令：`lcad undo e3 -m "撤销第 3 轮的修改"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e7",
 "commit": "094bc53",
 "undone": "e3",
 "removed_ops": 1,
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 收尾

`git log --oneline`
```
094bc53 e7 · 撤销第 3 轮的修改
d0c138d e6 · 把节圆直径的引出角度换到左上方
fd22878 e5 · 外径加大 10
480cc6f e4 · 删掉第 3 条技术要求
5e4449a e3 · 在主视图标注凸台长度
c82bcf6 e2 · 外径加公差 h11
aca65a9 e1 · 把凸台外径尺寸挪到主视图另一侧
96aae83 e0 · init
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
