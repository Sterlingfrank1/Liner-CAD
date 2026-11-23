# 仅 DXF 模式分数（E6）

命令（样例目录不进仓库；M3 基线用仓库内基线图）：

    uv run python evals/dxf_only.py --sample-dir <4 个用户样例所在目录> --m3 tests/data/dxf/sample_part.dxf --out <this file>

口径：只看 DXF 图元（LINE/ARC/CIRCLE/LWPOLYLINE/TEXT/DIMENSION/HATCH …），不经过导入器、不读语义模型的 intent；与 C1 尺子（evals/dxf_import.py）并存、互不替代。

## 可判规则（进入向量）

| 规则 | 族 | benchmark 条目 | 判据 |
|---|---|---|---|
| dxf_out_of_frame | G | G.layout（出框） | 所有可见图元在图框内（图框从 DXF 图元本身探测；探测不到时该规则不适用） |
| dxf_text_overlap | G | G.layout（重叠） | 文字外框不互相重叠（DXF-only 下只判文字-文字；文字压线需要尺寸/引线语义，不判） |
| dxf_hatch_defined | G | G.conv（剖面画法） | 每个 HATCH 有实体填充或可用的图案定义（图案名 + 比例） |
| dxf_dim_text_present | D | D.place（尺寸文字可读） | 每个 DIMENSION 带文字（覆盖值或测量显示 <>） |
| dxf_dim_arrows | D | D.place（箭头大小一致） | DIMENSION 几何块里有 >=2 个箭头且面积一致（无几何块的 DIMENSION 不适用） |

## 不可判（依赖 intent / 语义模型，只列出不评分）

| 规则 | 族 | 原因 |
|---|---|---|
| G.geo | G | 需要 3D/HLR 投影作参考 |
| G.linetype | G | 可见/隐藏线语义来自视图 intent |
| G.align | G | 需要视图归属（长对正/高平齐） |
| G.section | G | 需要剖视语义 |
| G.express | G | 需要 3D 特征 |
| G.layout.view_align | G | 需要视图归属 |
| G.conv.hatch_consistency | G | 相邻零件允许不同方向/间距，需要零件/剖视归属 |
| D.complete | D | 需要 3D 特征 / expect |
| D.redundant | D | 需要尺寸语义（封闭链/重复） |
| D.value | D | 需要被标几何的实测值（intent） |
| D.fit | D | 需要资源库公差与配合语义 |
| D.chain | D | 需要尺寸链语义 |
| D.group | D | 需要特征归属 |
| D.place.dim_cross | D | 尺寸线/轮廓线需要尺寸 intent |
| D.place.row_spacing | D | 平行尺寸组需要尺寸 intent |
| D.place.nesting | D | 大小尺寸嵌套需要尺寸 intent |
| D.place.text_direction | D | 水平/垂直尺寸需要尺寸 intent |
| D.place.leader_cross | D | 引线目标需要尺寸 intent |
| D.place.dim_outline | D | 尺寸线与轮廓线需要尺寸 intent |
| D.place.ext_line | D | 尺寸界线需要尺寸 intent |
| D.place.text_overlap | D | 尺寸文字与图元重叠需要尺寸 intent |
| D.place.arrow | D | 箭头大小/朝向需要尺寸 intent |
| D.place.balloon_cross | D | 装配序号引线需要装配 intent |
| D.place.balloon_align | D | 装配序号对齐需要装配 intent |
| D.place.balloon_spacing | D | 装配序号间距需要装配 intent |
| T.syntax | T | 需要形位公差框格语义 |
| T.datum | T | 需要基准语义 |
| T.target | T | 需要被测要素语义 |
| T.hier | T | 需要公差语义 |
| T.rough | T | 需要粗糙度语义 |
| T.func | T | 需要 expect |
| T.sem | T | 需要 PMI 语义元素 |
| A.place | A | 需要装配序号 / 明细栏语义 |
| A.bom | A | 需要装配明细语义 |
| P.* | P | 过程指标（轮次/token）与图元无关 |

## 4 个用户样例 DXF + M3 基线图

| 文件 | G | D | T | A | 规则违规/机会 | 说明 |
|---|---|---|---|---|---|---|
| 平头铣刀.dxf | 1.0 | 1.0 | None | None | dxf_out_of_frame 0/54; dxf_text_overlap 0/16; dxf_hatch_defined 0/1; dxf_dim_text_present 0/6; dxf_dim_arrows 0/0 |  |
| 牛鼻铣刀.dxf | 1.0 | 1.0 | None | None | dxf_out_of_frame 0/60; dxf_text_overlap 0/19; dxf_hatch_defined 0/1; dxf_dim_text_present 0/7; dxf_dim_arrows 0/0 |  |
| 球头铣刀.dxf | 1.0 | 1.0 | None | None | dxf_out_of_frame 0/54; dxf_text_overlap 0/16; dxf_hatch_defined 0/1; dxf_dim_text_present 0/6; dxf_dim_arrows 0/0 |  |
| 钻头铣刀.dxf | 1.0 | 0.857143 | None | None | dxf_out_of_frame 0/54; dxf_text_overlap 0/16; dxf_hatch_defined 0/1; dxf_dim_text_present 1/7; dxf_dim_arrows 0/0 |  |
| sample_part.dxf | 1.0 | 1.0 | None | None | dxf_out_of_frame 0/0; dxf_text_overlap 0/2; dxf_hatch_defined 0/1; dxf_dim_text_present 0/8; dxf_dim_arrows 0/8 | no sheet frame detected in the DXF primitives |

### 汇总（按机会数加权）

- G（G.layout + G.conv 可判部分）：**1.0**（0/296 违规/机会）
- D（D.place 可判部分）：**0.97619**（1/42 违规/机会）
- T / A / P：不可判（见上表）

## 说明与局限

- 文字外框按 DXF 的字高/MTEXT 宽度/附件点近似；文字-文字重叠用 IoU>0.1 判（小于此的贴边/包含不算），不与 C1 的导入器口径混用。
- 图框从图元本身探测（最大的轴对齐闭合矩形，且面积 >= 图面 bbox 的 50%）；探测不到时 dxf_out_of_frame 不适用（记为 0 机会，不扣分）。
- DIMENSION 文字缺失、箭头检查只看 DXF 可读属性/几何块；半径/直径尺寸允许单箭头。
- 标题栏模板语义、视图归属、形位公差/装配/过程指标都不可判，明确列在不可判表。
- M3 基线图 = tests/data/dxf/sample_part.dxf（M3 验收用的 ezdxf 原生尺寸基线图例；不是用户样例，可随仓库分发）。

