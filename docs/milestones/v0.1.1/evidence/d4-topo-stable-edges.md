# D4 3D 投影边按拓扑稳定命名

2026-11-23 · issue #87 · 分支 `m5/d4-topo-stable-edges`（base 4e322f8）· 热点 source3d.py（hlr.py 未改）

## 改了什么

### 1. 投影边 ID 由 3D 拓扑派生（source3d.py）

- 每条投影边匹配回模型边时，`_model_index` 额外算一个 **拓扑键**：相邻面索引 + 该边在最小相邻面 `face.edges()` 中的序号，例 `f0_1_e6`；自由边用 `e<i>`。参数只改尺寸、拓扑不变时这个键不变（gear_cover 实测 54/54 边键稳定）。
- `compute()` 在合并圆弧后给每条边写显式 `name`：`E.<view>.<feature>.<topo键>`（装配再加组件前缀，如 `A_base_...`）；轮廓线 / 未匹配线 / 肋线没有模型边，用 `outline` / `unmatched` / `rib` + 规范化投影几何排序后的序号。同一条模型边被 HLR 拆成多段时按投影几何排序加确定性后缀，不依赖 HLR 返回顺序。
- 重影线（同一投影位置可见/隐藏各一条）去重从「先到先得」改为确定性排序：可见优先，其次拓扑键，再其次规范化几何；保证正/反顺序 HLR 输出得到同一条保留边。
- 缓存版本 5→6（旧缓存没有拓扑名）。

### 2. diff 只报图纸实际变化（versions.py 小改）

- 3D 边沿视线方向移动时投影几何可以完全不变，但 `src3d` 的 edge/faces/hash 会变；`compare()` 比较意图时剔除 `src3d` / `src3d_refs` 这类纯来源字段，投影曲线本身的变化仍由 intent 的 shape/p1/p2/… 与 layout 判。

### 3. 旧 ID 候选

- 旧顺序 ID（如 `E.front.model.1`）不再存在；`d["旧 ID"]` 的 `NotFound` 仍由 `_close_ids` 给出同 feature 下的当前边 ID 候选（回归测试断言 candidates 非空且指向 `E.front.model.*`）。

## 前后行为（gear_cover，改 L=150→160）

| 指标 | main 4e322f8（before） | 本分支（after） |
|---|---|---|
| 投影边 ID | 顺序 child ID `E.front.model.1`… | 拓扑 ID `E.front.model.f0_1_e0`… |
| HLR 返回顺序反转后 geometry→ID | 改变（测试失败） | **不变（测试通过）** |
| diff 中「投影几何未变的边」被上报 | **19 条误报** | **0 条** |
| diff 上报的边（intent/layout） | 44 | 24（都对应投影几何实际变化） |
| diff 新增/删除边 ID | 0 | 0 |
| 40 例评测 / 几何 | 40/40、geometry 1.0 | **40/40、geometry 1.0 不变（E3 后 198 条 expect 全过）** |
| `--baseline` | regressions [] | **regressions []（merge E3 后 D 0.986906，与当前 baseline 一致）** |
| L3 | A 1.0、D 0.99、G 1.0 | **不变** |

## 回归用例（G2 首个 commit 见 git log；`tests/test_source3d_stable.py`）

- `test_ids_do_not_depend_on_projection_order`（**G2 失败项**）：把 `hlr.project_classes` 返回列表整体反转、清投影缓存后重建；断言「规范化投影几何 → 边 ID」映射与正常顺序完全一致。
- `test_repeated_projection_keeps_the_same_ids`：同模型清缓存重复投影 ID 不变。
- `test_gear_cover_parameter_change_only_touches_actually_changed_edges`：改 L，断言投影几何未变的边 ID 不变、且不出现在 diff 的 E.* intent/layout/added/removed 中。
- `test_projected_edges_have_topological_names_and_candidates_for_old_ids`：拓扑名存在；旧顺序 ID 触发 NotFound，candidates 全部是当前存在、同 feature 的 edge ID（`_close_ids` 对 E.* 已限定到 edge scope）。
- `tests/test_source3d_naming_unit.py`（新，无需 3D，普通 CI job 会跑）：线方向规范化、同拓扑拆分后缀与输入顺序无关、组件前缀；以及 `_close_ids` 的 edge/feature 限定、`_diff_intent` 只剔除 `src3d*` 的单元断言。
- 既有 `tests/test_source3d.py`（provenance/剖切/参数重投影等 12 条）全部通过。

Codex R1 后续（无 blocker）：① 最终保留的 line intent 统一规范化为 `p1<=p2`（方向无几何意义），并把顺序反转测试加强为完整 intent / `compare()` 无 E.* 变化；② gear_cover 回归改为断言 72 条未变几何边全部保留且不被 diff 上报、24 条上报均为实际变化、added/removed=0；③ 旧 ID 候选限定同 feature 的 edge；④ 新增 `test_source3d_naming_unit.py` 让命名核心在非 3D CI job 也有覆盖（3D 集成测试仍受 `test-3d` 只跑 hlr/evals 的既有 CI 限制，改 workflow 需 workflow scope）。

## 说明 / 残余

- 拓扑键使用 build123d 的面顺序 + 面内边序号；**只改尺寸参数**时稳定；若模型编辑增删特征导致面/边重排，ID 可以变（这正是「只有真正变化的边换 ID」），旧 ID 由候选兜底。
- outline / unmatched / rib 没有模型边，仍用规范化投影几何命名；纯移动这类边可能换 ID（属实际投影变化）。
- `versions.compare` 忽略 `src3d`/`src3d_refs` 是全局语义变化：纯 3D 来源变化不再被当成图纸变化；若后续需要追踪来源变化，需要单独的 provenance diff（本卡不做）。
- 装配图投影的拓扑名带组件前缀，避免不同组件同面号撞名。
- `tests/test_source3d_stable.py` 需要 `linercad[3d]`，与既有 source3d 测试一样在非 3D CI job 跳过；`test_source3d_naming_unit.py` 与纯逻辑断言留在普通 CI。CI `test-3d` job 目前只跑 hlr/evals（同 D5 记录的限制，改 workflow 需 workflow scope）。
- 残余（minor）：同 base 的多段边 / outline 同类边仍按规范化几何排序加后缀；若其中一个 sibling 移动并跨过未变同类的排序位置，未变 sibling 也可能换后缀。当前 gear_cover 参数用例未触发；后续可用更稳定的 sub-topology 键改进。

## 门禁（最终数字见 PR/CI）

- 全量 `uv run pytest -q`（merge E3 + R2 回归后）：**1475 passed / 1 skipped（11m53s）**；`uv run ruff check .` 绿；`ruff format --check src tests` 绿（99 files）；40 例评测 40/40、geometry 1.0、`--baseline` regressions []（D 0.986906，E3 后 baseline 同值）；CI 四项绿后由 lead 合并。
- Codex R2：无 blocker/major；minor（sibling 后缀边界、纯逻辑 CI 覆盖）已补非 3D 单元测试并在证据记录残余，nit 已修。