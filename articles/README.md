# 技术文章集

首版收录九篇现有正文。文章从具体代码、数值例子和历史实验出发，各篇均可独立阅读。这里是 GitHub 收录；社区发布链接待实际发表后补充。

| 序号 | 文章 | 关联赛题 | 主要内容 |
|---|---|---|---|
| 1 | [Ascend C 算子优化入门：数据搬运、分核与 Tiling](ascend-c-optimization-beginner-v2.md) | Concat | 地址布局、分核、UB 预算与流水 |
| 2 | [Ascend C 极限调优：从 IndexAdd 看实现方案的切换](ascend-c-optimization-architecture.md) | IndexAdd | 有序来源计划、八行转置与结构切换 |
| 3 | [Concat 优化实录：UB 复用省下的空间，为什么没有换来稳定提速](ascend-c-concat-ub-reuse.md) | Concat | 跨阶段复用与未稳定胜出的性能对照 |
| 4 | [Ascend C Transpose 调优：用分块临时布局改善短片段写回](ascend-c-transpose-blocked-layout.md) | Transpose | 分块 workspace、尾部压紧与连续输出 |
| 5 | [Ascend C 同步排错：TQueBind 改造后的一次事件编号冲突](ascend-c-queue-event-lifetime.md) | Concat | 事件编号占用、查询与同步生命周期 |
| 6 | [Ascend C IndexAdd 调优：减少 Cast 之前，先确认 BF16 的舍入位置](ascend-c-indexadd-bf16-rounding.md) | IndexAdd | 逐次舍入、连续源行搬运与短 Gather |
| 7 | [Ascend C Greater 实现：用 Min/Max 与 EQ 完成精确的 INT32 比较](ascend-c-greater-int32-exact.md) | Greater | 完整整数值域、双方向广播与结果编码 |
| 8 | [Ascend C 边界排错：扩大分块后的一次 Gather 重复次数截断](ascend-c-gather-repeat-boundary.md) | Greater | repeat 缩窄、错误复现与分段修复 |
| 9 | [Ascend C 性能分析：Vector 时间降了，算子为什么没变快](ascend-c-profiler-pipeline-analysis.md) | IndexAdd | 流水计数、关键依赖与完整耗时 |

## 阅读建议

先读第 1 篇建立对数据搬运与 Tiling 的认识，再根据感兴趣的题目阅读对应案例。第 2、3、4 篇讨论结构和布局取舍，第 5、8 篇讨论排错，第 6、7 篇讨论数值与精确性，第 9 篇讨论测量的解释。

正文中的内部版本号对应当时的实验，不表示该版本是当前最终上榜包。当前版本关系以[五题方案页](../operators/README.md)为准。

## 版本与复现

正文从原写作目录导入，只统一换行，不把审稿笔记和被替代旧稿混作新文章。导入来源、原稿和当前正文的 SHA256 见 [articles.json](../data/articles.json)。旧稿和审阅记录仍留在开发工作空间；后续技术修订通过 Git 历史保留。

七个独立 Python 代码块已纳入仓库检查，均不依赖 NPU。它们验证文中的数值或布局模型；文中设备计时来自历史实验，不能通过这些 CPU 模型重现绝对性能。

AI 参与了原项目的代码实现、实验分析和文章整理。作者与团队成员的具体分工将在确认后补充。
