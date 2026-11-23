# 错误与检查

`error.code`：`not_found`（看 candidates）、`count_mismatch`、`invalid_arg`、`duplicate_id`、`param`、`script`（看 `where` / `trace`）、`stale`、`no_ops`、`dirty`、`undo`、`build`、`git`。

输出里 `errors` 是 error 级问题数，`warnings[]` 列出全部问题（E1 finding）：`rule`、`pack`、`severity`（`error` 必须改；`warn` 改或 accept）、`id`、`message`、`std`（依据的标准号）、`clause`（条款 / 依据说明：读到的标准条款给「标准号：条款号 / 表号」，design 类规则引 DESIGN 节，pending 规则只给标准号、不编造条款号）、`measured`（实测值）、`expected`（要求 / 期望）、`candidates`（候选修法）、`violations` / `corridors`（布局类问题的定位与可动方向）。没有内容的字段是空容器（`{}` / `[]`），Viewer 检查器里显示为「无」。`lcad check` 按规则包列出全部，并返回 `opportunities`（每条规则实际检查的机会数，评测通过率 = 1 − violations / opportunities）。

- drafting：`line_width` `text_height` `scale` `sheet` `conv_dim`（螺纹、花键、键槽、退刀槽缺代号或尺寸）`section_ref` `center_mark`（圆缺中心线）
- dimensioning：`duplicate` `closed_loop`（封闭尺寸链：删一个或 `reference=True`）`missing`（轴向台阶没全部定位）`param_cover`
- tolerancing：`gtol_syntax`（基准没定义）`datum_letter` `general_tol`（缺未注公差说明）`chain_limit` `dev_order`
- surface：`rough_syntax`（数值不在 GB/T 1031 系列）`rough_default`（缺通用符号）`rough_fit`（IT≤7 配合面没标粗糙度）
- layout：`overlap`（看 violations / corridors，换侧、换排、微调）`out_of_frame` `view_align` `stale_op`（`lcad undo <那一轮>` 或 accept）
