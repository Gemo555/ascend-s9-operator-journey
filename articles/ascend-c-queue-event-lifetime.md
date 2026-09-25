# Ascend C 同步排错：TQueBind 改造后的一次事件编号冲突

本文记录一次 Concat 搬运路径改造中的正确性问题。案例来自[昇腾 AI 创新大赛——算子挑战赛 S9 赛季](https://www.hiascend.com/developer/contests/details/41ffbad2024e4ccfa43520c57ffa7b9e)：赛题要求将多路输入张量沿指定轴依次拼接，输出保持元素值和排列顺序。开发环境为 Ascend 910B4、CANN 8.5.0。

当时的一条实现先把输入打包到核私有 workspace，再读回 UB，通过 Gather 组成输出行。我们尝试使用 TQueBind 消除打包阶段的一次 UB 内复制。地址公式没有变化，前四项正确性检查也通过了，第五项却出现了数据不一致。

最后的修复很小：将一个手动事件从 `FetchEventID` 改为 `AllocEventID`，并在使用结束后释放。理解这个修改，需要同时看缓冲区和事件编号各自的生命周期。

## 1. 省掉一次复制后，队列的依赖也变了

原来的打包阶段没有数值计算，只经过以下路径：

```text
输入 GM → 输入 UB → 输出 UB → workspace
```

输入、输出分别由队列管理。中间的 UB 复制完成后，输入槽可以按原队列的依赖关系复用；输出槽继续服务于搬出。

候选将打包阶段改成绑定队列，让同一个 LocalTensor 完成读入和写出：

```text
输入 GM → 同一个 UB 槽 → workspace
```

[昇腾官方 API 使用优化文章](https://www.hiascend.com/developer/techArticles/20241107-1)介绍了用 TQueBind 处理这种纯搬运路径的方式。我们的改动限定在 Pack 阶段；随后 Regroup 中的 Gather 仍然承担实际重排，不能一起删除。

候选使用四个绑定槽，并让 Pack 与 Regroup 的缓冲池分阶段复用空间。Pack 中的调用关系可简化为以下片段，省略了搬运参数和地址计算：

```cpp
auto local = packQueue_.AllocTensor<uint32_t>();
DataCopyPad(local, sourceGm, inParams, padParams);
packQueue_.EnQue(local);
local = packQueue_.DeQue<uint32_t>();
DataCopyPad(workspaceGm, local, outParams);
packQueue_.FreeTensor(local);
```

省掉中间复制后，同一槽要一直保留到 GM 写出结束，下一次输入搬入才能覆盖它。这条复用关系涉及搬出与搬入单元，绑定队列需要管理相应的同步资源。

与此同时，Kernel 自己还有一条跨阶段依赖：一个行带的 Pack 写完 workspace 后，Regroup 才能读取它。这个依赖使用手动的 `MTE3_MTE2` 事件。

两种同步的目的不同，却可能使用同一种 HardEvent 资源。代码审查如果只看数据地址和 `SetFlag/WaitFlag` 是否成对，就会漏掉事件编号是否仍然可用的问题。

## 2. FetchEventID 返回可用编号，不占用编号

有问题的版本在进入行带循环前取得编号，然后调用 PackOwn，最后设置并等待跨阶段事件：

```cpp
const event_t packed = static_cast<event_t>(
    pipe_.FetchEventID(HardEvent::MTE3_MTE2));

// 随后的行带循环中：
PackOwn(own);  // 内部执行多次绑定队列操作
SetFlag<HardEvent::MTE3_MTE2>(packed);
WaitFlag<HardEvent::MTE3_MTE2>(packed);
// 然后读取 workspace，执行 Regroup。
```

问题在于取得编号与实际使用之间跨越了队列操作。根据 [CANN 8.5.0 FetchEventID 文档](https://www.hiascend.com/document/detail/en/canncommercial/850/API/ascendcopapi/atlasascendc_api_07_0116.html)，该接口查询当前可用的编号，并不会占用它。把结果保存到 C++ 变量中，也不会改变这个状态。

若后续队列操作分配了同一类事件的同一个编号，手动同步与队列同步就可能同时操作它。下面是用于说明风险的资源关系，不是设备事件轨迹：

```text
手动同步：Fetch 得到 E ─────────────── Set(E) / Wait(E)
队列内部：              分配并使用 E ────────────────
                      ↑
              Fetch 没有保留这个编号
```

不能仅比较两个事件的数字部分。分析冲突时，要把 HardEvent 类型、编号和使用区间放在一起看。不同类型恰好采用同一个数字，并不自动表示它们冲突。

这也解释了为什么原实现里没有观察到同样的问题，并不能证明原来的写法在新队列下仍然正确。更换队列后，资源使用方式已经变了。

## 3. 在跨队列操作期间独立持有完成事件

修复版在进入循环之前申请并占用完成事件，所有行带处理结束后再释放。冻结源码的差分只有申请方式与末尾释放两处；Pack 地址、Gather 映射和输出计算均未修改。

```cpp
const event_t packed = static_cast<event_t>(
    pipe_.AllocEventID<HardEvent::MTE3_MTE2>());

// 原有行带循环：
// PackOwn(own);
// SetFlag<HardEvent::MTE3_MTE2>(packed);
// WaitFlag<HardEvent::MTE3_MTE2>(packed);
// Regroup，并完成本行带的读取后再处理下一行带。

pipe_.ReleaseEventID<HardEvent::MTE3_MTE2>(packed);
```

这段代码展示的是修改位置，不是可以单独运行的完整 Kernel。实际释放发生在所有行带及相关同步完成之后。

[AllocEventID 文档](https://www.hiascend.com/document/detail/en/canncommercial/850/API/ascendcopapi/atlasascendc_api_07_0114.html)说明，申请到的编号会保持占用，直到调用 ReleaseEventID。这样一来，队列内部申请资源时可以识别该编号已被持有。

申请事件并不等于完成硬件同步。真正建立先后关系的仍然是正确位置上的 SetFlag 和 WaitFlag；ReleaseEventID 也不能代替等待尚未完成的使用。资源数量有限，使用结束后应及时释放。

因此，不能机械地把全部 FetchEventID 改成 AllocEventID。临时使用且使用区间内没有冲突的事件，可以按对应 API 的规则安排；跨越队列操作、需要持续持有的事件，则需要明确占用和释放范围。

## 4. 修复证据到哪一步，结论就写到哪一步

问题出现在第五个本地输入：137 路 FP32 张量沿轴 1 拼接，输出为 `[2012,8811]`，其中包含两路零长度输入。检查使用字节视图比较，验证的是搬运后的元素位模式。

| 版本 | 本地检查结果 |
|---|---|
| 绑定队列初版 | 前四项通过，第五项断言失败，没有进入性能测试 |
| 独立持有完成事件的修复版 | 五项原输入及两项边界检查全部通过 |

两项边界检查覆盖了奇数数据块、空片段、尾部处理及负轴等组合。它们补充了目标输入之外的覆盖，但七项检查当然不等于证明所有形状都正确。

同一份地址计算，仅改变事件管理方式后通过检查，加上 API 对编号占用的明确说明，支持将这次问题定位到事件资源的生命周期。保存的日志没有逐指令事件轨迹，因此不能进一步断言某一条具体 Wait 消费了哪一个错误信号。

修复版随后完成了五例性能测量，总耗时为 324.1265 μs，目标第五例为 196.3840 μs，没有形成稳定替换原实现的收益。这个结果应分成两部分理解：观察到的正确性问题得到修复；消除 UB 复制的整套设计，仍未通过当时的性能筛选。

纯搬运路径中的一次复制有成本，新的队列与事件管理也有成本。只有完成正确性检查后，完整计时才有比较意义，不能用一个结果错误的快版本评价 TQueBind 的收益。

## 5. 从缓冲区的最后一次使用反推同步

后续审查类似代码时，我们会先从会被覆盖的地址出发，列出最后的读者和下一个写者，再检查连接这两个阶段的同步。本文至少有三条不同的关系：

| 对象 | 必须先完成的操作 | 后续操作 |
|---|---|---|
| Pack 绑定槽 | MTE3 从 UB 读取并写入 workspace | MTE2 向同一槽搬入下一批数据 |
| 当前行带的 workspace | Pack 的写入 | Regroup 的读取 |
| 将被下一行带复用的 workspace | 当前 Regroup 的读取 | 下一次 Pack 覆盖 |

第二条依赖成立，不代表第三条自然成立。冻结代码还保留了行带末尾的完成屏障，避免下一个行带覆盖仍在被读取的 workspace。

随后再看事件的申请、设置、等待和释放范围，检查队列是否也会使用同类资源。不能从 `FreeTensor` 这个函数名，直接推断所有无关流水都已经结束；同样，增加一个局部向量屏障，也无法替代另一类执行单元之间缺失的依赖。

测试则应让槽位真正经历复用。只有一个 tile 的输入，即使通过，也覆盖不到第二次搬入覆盖旧槽的时刻。多个行带、多次槽位轮转和尾块组合，更容易暴露这类问题。定位时可以使用更强的同步作为对照，但保留哪些屏障，最终仍应依据实际读写关系和设备验证决定。

本例中，修改从“一次 UB 复制”开始，最终需要重新检查的是数据与同步资源的两套使用区间。队列替换、缓冲池复用和预取调度，都可能改变这两套区间；它们应当和地址推导一起进入代码审查。

文中失败日志、源码差分和计时来自 2026 年 9 月的本地历史实验。性能统计沿用原 30 轮调用及第 11–30 条目标记录的整数中位数规则；本文整理期间未新增 NPU 实验，片段不构成完整可编译工程。AI 参与了代码实现、实验分析和文章整理。
