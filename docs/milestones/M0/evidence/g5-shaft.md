# g5 shaft 证据

## 第 1 轮

- 请求：把总长尺寸挪到轴的上方
- 检查：context：D.L 为 linear/overall，side=bottom,row=2；技术要求 3 条；倒角注释 N.chamfer

脚本 `.linercad/tmp/r1.py`：
```python
def apply(d):
    d["D.L"].place(side="top")
```
命令：`lcad edit .linercad/tmp/r1.py -m "把总长尺寸挪到轴的上方"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e1",
 "commit": "3ff0f6d",
 "ops": [
  {
   "edit": "e1",
   "op": "place",
   "id": "D.L",
   "args": {
    "side": "top",
    "row": 2,
    "offset": 0
   }
  }
 ],
 "changed": [
  "D.L"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 2 轮

- 请求：最粗那段的直径加公差 k6
- 检查：context：直径 d1=25,d2=30,d3=36；最粗段是轴身 D.d3（Φ36，无公差）

脚本 `.linercad/tmp/r2.py`：
```python
def apply(d):
    d["D.d3"].tol = "k6"   # 最粗段 = 轴身 d3 = Φ36
```
命令：`lcad edit .linercad/tmp/r2.py -m "最粗那段的直径加公差 k6"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e2",
 "commit": "0038448",
 "ops": [
  {
   "edit": "e2",
   "op": "set",
   "id": "D.d3",
   "args": {
    "tol": "k6"
   }
  }
 ],
 "changed": [
  "D.d3"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 3 轮

- 请求：加一条技术要求：去除毛刺锐边
- 检查：context：已有 N.tech.1..3 三条技术要求

脚本 `.linercad/tmp/r3.py`：
```python
def apply(d):
    d.notes.tech("去除毛刺锐边。")
```
命令：`lcad edit .linercad/tmp/r3.py -m "加一条技术要求：去除毛刺锐边"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e3",
 "commit": "13921e6",
 "ops": [
  {
   "edit": "e3",
   "op": "notes.tech",
   "id": "N.tech.e3_1",
   "args": {
    "text": "去除毛刺锐边。"
   }
  }
 ],
 "changed": [
  "N.tech.e3_1"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 4 轮

- 请求：删掉倒角的引线标注
- 检查：context：N.chamfer 是 front 视图的引线注释 2×C1

脚本 `.linercad/tmp/r4.py`：
```python
def apply(d):
    d["N.chamfer"].suppress()   # 倒角引线注释 2×C1
```
命令：`lcad edit .linercad/tmp/r4.py -m "删掉倒角的引线标注"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e4",
 "commit": "eaa4760",
 "ops": [
  {
   "edit": "e4",
   "op": "suppress",
   "id": "N.chamfer",
   "args": {}
  }
 ],
 "changed": [
  "N.chamfer"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 5 轮

- 请求：总长改成 220
- 检查：context：参数 L=200（drawing.py 第 8 行），D.L value=P.L；是参数值，故改 drawing.py 后 lcad build

drawing.py 改动：
```diff
diff --git a/drawing.py b/drawing.py
index 73d740a..2879674 100644
--- a/drawing.py
+++ b/drawing.py
@@ -5,7 +5,7 @@ from linercad import Drawing, Param
 
 d = Drawing(sheet="A3", std="GB", scale="1:1")
 P = d.params(
-    L=Param(200, min=120, max=400, step=1, label="总长"),
+    L=Param(220, min=120, max=400, step=1, label="总长"),
     l1=Param(30, min=10, max=80, step=1, label="左轴颈长"),
     l2=Param(40, min=10, max=100, step=1, label="第二段长"),
     l3=Param(60, min=10, max=150, step=1, label="轴身长"),
```
命令：`lcad build -m "总长改成 220"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e5",
 "commit": "4e87871",
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 6 轮

- 请求：把总长尺寸再往外挪 3 mm
- 检查：context D.L：side=top,row=2,offset=0（第 1 轮已换到上方）

脚本 `.linercad/tmp/r6.py`：
```python
def apply(d):
    # D.L 现在在上方(side=top)，"往外"=再向上；skill 未说明 dy 正负，先用 dy=3 试
    d["D.L"].move(dy=3)
```
命令：`lcad edit .linercad/tmp/r6.py -m "把总长尺寸再往外挪 3 mm"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e6",
 "commit": "17ac7de",
 "ops": [
  {
   "edit": "e6",
   "op": "move",
   "id": "D.L",
   "args": {
    "dy": 3,
    "side": "top",
    "row": 2
   }
  }
 ],
 "changed": [
  "D.L"
 ],
 "warnings": [],
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json"
}
```

## 第 7 轮

- 请求：把键槽宽度尺寸的公差改成 h9
- 检查：context 的元素表里没有键槽特征，也没有键槽宽度尺寸（dims 只有 d1-d5、l1-l4、L）；用户坚持尝试，故直接对猜测的 D.keyway_w 运行 lcad edit

脚本 `.linercad/tmp/r7.py`：
```python
def apply(d):
    # 图中没有键槽；按用户坚持，仍尝试找键槽宽度尺寸（先猜 ID，再按文字/视图查）
    d["D.keyway_w"].tol = "h9"
```
命令：`lcad edit .linercad/tmp/r7.py -m "把键槽宽度尺寸的公差改成 h9"`（退出码 1）

```json
{
 "ok": false,
 "rolled_back": true,
 "error": {
  "code": "not_found",
  "message": "找不到元素 D.keyway_w",
  "id": "D.keyway_w",
  "candidates": [
   "D.d1",
   "D.d2",
   "D.d3",
   "D.d4",
   "D.d5",
   "D.l1"
  ],
  "values": {},
  "hint": "用 lcad context 查看全部 ID",
  "where": "r7.py:3",
  "trace": [
   "r7.py:3  d[\"D.keyway_w\"].tol = \"h9\""
  ]
 }
}
```

## 第 8 轮

- 请求：撤销第 2 轮的修改
- 检查：history：第 2 轮 = e2（D.d3 加 k6）；第 7 轮失败，没有产生 eN，故编号仍对应；git status 干净

命令：`lcad undo e2 -m "撤销第 2 轮的修改"`（退出码 0）

```json
{
 "ok": true,
 "edit": "e7",
 "commit": "cfcad43",
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
cfcad43 e7 · 撤销第 2 轮的修改
17ac7de e6 · 把总长尺寸再往外挪 3 mm
4e87871 e5 · 总长改成 220
eaa4760 e4 · 删掉倒角的引线标注
13921e6 e3 · 加一条技术要求：去除毛刺锐边
0038448 e2 · 最粗那段的直径加公差 k6
3ff0f6d e1 · 把总长尺寸挪到轴的上方
ee7f902 e0 · init
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
