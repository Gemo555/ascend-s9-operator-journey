# Ascend S9 · 本质嘉豪

**五道算子题，一次从正确性验证到性能调优的团队实践。**

本仓库记录「本质嘉豪」参加昇腾 AI 创新大赛——算子挑战赛 S9 赛季的成果：比赛表现、代表方案的设计取舍，以及从开发中整理出的技术文章。主要开发环境为 **Ascend 910B4 / Ascend C / CANN 8.5.0**；具体实验条件见对应文章。

[比赛与成绩](docs/results.md) · [五题方案](operators/README.md) · [九篇技术文章](articles/README.md) · [证据与验证](docs/evidence.md)

## 比赛表现

<!-- scoreboard:start -->
**积分汇总并列第 7 名 · 150 分 · 五题全部进入前十**

> 截至 **2026-09-15 13:17:56+08:00** 的榜单快照。最终比赛结果待团队确认。

| 赛题 | 单题名次 | 积分 | 耗时 / μs | 上榜条目 |
|---|---:|---:|---:|---:|
| [Concat](operators/concat/README.md) | 10 | 10 | 307.27 | 272 |
| [Greater](operators/greater/README.md) | 7 | 40 | 482.57 | 274 |
| [IndexAdd](operators/indexadd/README.md) | 10 | 10 | 631.569999 | 182 |
| [Transpose](operators/transpose/README.md) | 6 | 50 | 903.47 | 174 |
| [SquareSumV1](operators/squaresumv1/README.md) | 7 | 40 | 1398.168 | 230 |

来源：[历史快照](data/leaderboards/20260915-131756+0800.json)；积分榜由五题积分汇总，同分并列。快照记载 902 支报名队伍、21 支获得积分的队伍。
<!-- scoreboard:end -->

## 从项目中能看到什么

| 技术问题 | 本次实践 | 阅读入口 |
|---|---|---|
| 短片段搬运如何组织 | Concat P07 按布局选择小面板、命令预取和直接 UB 重排；与 P06 的中转方案对照 | [Concat 方案](operators/concat/README.md) |
| 重复索引如何保持数值行为 | IndexAdd 保留更新顺序与 BF16 舍入节点；FP32 八行转置结合缓冲生命周期复用 | [IndexAdd 方案](operators/indexadd/README.md) |
| 转置的输入与输出连续方向不同 | 使用分块 GM workspace 组织连续输出，并实测核数、尾部压紧与缓存策略 | [Transpose 双方案](operators/transpose/README.md) |
| INT32 大小比较如何保持精确 | Greater 用 Min/Max 与 EQ 组合实现，比较完成后复用存储编码布尔结果 | [Greater 方案](operators/greater/README.md) |
| 多维归约如何连续读取 | SquareSumV1 R120 按保留/归约维分类，用成对压缩、连续列流和分层合并组织不同 dtype | [SquareSumV1 方案](operators/squaresumv1/README.md) |
| 如何判断一次优化是否有效 | 保留同场完整运行、失败候选和计时口径，区分 CPU 模型、真卡历史实验与榜单成绩 | [性能分析文章](articles/ascend-c-profiler-pipeline-analysis.md) |

五题方案均已有内容，其中 Concat P07 为团队确认的当前最好本地候选，SquareSumV1 R120 为团队指定的最佳展示包。最终上榜 ZIP 与榜单的对应关系继续补齐；当前方案页分别注明版本来源和已有结果。源码与安装包身份索引见 [包清单](data/packages.json)。

## 技术文章

九篇现有正文已集中收录，涵盖入门、结构优化、数值行为、同步排错与性能分析。

1. [算子优化入门：数据搬运、分核与 Tiling](articles/ascend-c-optimization-beginner-v2.md)
2. [从 IndexAdd 看实现方案的切换](articles/ascend-c-optimization-architecture.md)
3. [Concat：UB 复用为什么没有换来稳定提速](articles/ascend-c-concat-ub-reuse.md)
4. [Transpose：用分块临时布局改善短片段写回](articles/ascend-c-transpose-blocked-layout.md)
5. [同步排错：TQueBind 改造后的一次事件编号冲突](articles/ascend-c-queue-event-lifetime.md)
6. [IndexAdd：减少 Cast 之前，先确认 BF16 的舍入位置](articles/ascend-c-indexadd-bf16-rounding.md)
7. [Greater：用 Min/Max 与 EQ 完成精确的 INT32 比较](articles/ascend-c-greater-int32-exact.md)
8. [边界排错：Gather 重复次数截断](articles/ascend-c-gather-repeat-boundary.md)
9. [性能分析：Vector 时间降了，算子为什么没变快](articles/ascend-c-profiler-pipeline-analysis.md)

[文章索引](articles/README.md)包含主题、关联赛题和版本来源。已有的 [Ascend C 优化笔记仓库](https://github.com/Gemo555/ascend-c-optimization-notes)提供入门配套示例与实验复算；本仓库作为本次比赛的完整项目入口。

## 在普通电脑上验证

```bash
git clone https://github.com/Gemo555/ascend-s9-operator-journey.git
cd ascend-s9-operator-journey
python scripts/check_repository.py
```

需要 Python 3.10+，只使用标准库。检查会复算榜单积分与并列名次、核对本地文档链接和文章内容哈希，并运行正文中的七个 Python 模型。它验证材料的一致性及模型中的地址/数值关系；NPU 正确性与性能仍以各自实验记录为准。

## 持续完善

下一步补齐最终比赛结果、五题最终包及耗时接近的方案对照。之后再整理与 AI 的协作方式、开发历程和经验积累，具体内容以实际记录和团队分工为依据。当前成绩属于团队；个人贡献和简历表述会在分工确认后补充。

AI 参与了代码实现、实验分析与文章整理。详细协作复盘尚未定稿，见 [后续计划](docs/roadmap.md)。仓库更新方式见 [维护说明](CONTRIBUTING.md)。
