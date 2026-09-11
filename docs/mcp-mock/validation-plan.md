# MCP 模拟环境验证计划

日期：2026-09-10。本文规定未来验收实验，**本阶段没有实现 mock，也没有执行真实服务写入、完整 benchmark 或以下运行实验**。本次已完成的文档/源码核验另记总体报告。门槛是设计建议 D，不是观测结果。

## 1. 证据来源和判定层级

契约源优先固定 MCP 提交/发布包的注册及 handler、运行时 `initialize/tools/list` 全分页快照、原始请求响应与真实后端记录。静态源码能核对工具名和程序路径，但不能证明部署版本、权限或后端接受范围。官方服务规范能解释语义，不能证明当前 MCP 暴露了它。动态 HF/远程 Notion 未拿到账户 snapshot 的能力标 U。

MCP 2025-06-18 规范分别定义工具协议错误与工具执行错误，并支持 text/image/audio/resource 等内容和可选结构化输出；具体服务仍以协商版本与实现为准。[Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)、[Resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)（查阅 2026-09-10）。当前 harness 只序列化 content，见 `utils/openai_agents_monkey_patch/custom_mcp_util.py:176-229`，因此原始 MCP 与模型可见结果各自保存/检查，不用后者冒充完整协议快照。

证据等级：A0 静态清单与规范；A1 现成真实记录；A2 受控真实差分；A3 mock 属性/状态机测试；A4 新结构与规模实验。A0/A1 不替代 A2；A3 的自洽不自动代表与真实服务一致；高保真发布需说明每能力覆盖了哪些等级以及残余 U。

## 2. 通用验证矩阵

| 编号 | 范围与实验 | 独立期望/观察 | 发布门槛（D） |
|---|---|---|---|
| V01 契约 | 各 profile 的 tools/list 全分页；name/description/inputSchema/required/default/enum、可见开关、资源/提示模板、协议协商 | 原始快照与固定源逐工具 diff；模型别名及 strict/coercion 路径另比 | 已宣称支持工具 100% 有来源及无未解释差异；全量未覆盖显式列出 |
| V02 输出 | 成功/空/单项/多项/异常/大内容；MIME、isError、structuredContent、分页元数据与必要版本 | 原始 MCP 和经过 harness 的双 golden；动态字段语义比较 | 声称支持的结构与错误包装零未解释差异 |
| V03 参数与错误 | 缺必填、null/空/0/false、越界、非法枚举/路径/类型、未知字段、未授权、不存在、冲突、重复请求 | 固定源码处理 + 真实反例；区分广告 schema 和 handler 投影/默认规则，检查状态未越权变动 | 真实接口应拒绝的关键负例均拒绝；非法接受计数为 0。已核实的剥离未知键/缺省转换单列兼容行为，不误当新特性接受 |
| V04 状态 | 创建/读取/更新/删除/历史/引用/部分批量失败，类型/计算/生命周期 | 不复用 handler 的 invariant checker；实际 DB/blob/Git 导出 | 不变量违反 0；假成功/幻觉资源 0 |
| V05 组合 | 随机合法状态机序列，操作交换/重复/分叉/回滚；搜索分页与直接读/批量改单项读 | 可交换操作比较终态；非交换操作有独立推导 | 相同定义条件下结果一致；不能误要求真实异步索引即时一致 |
| V06 多入口 | M→SDK/HTTP/CLI 读取与 X→M 读取；跨 Google Drive/Sheets/Forms、Git/MCP、HF SDK/文件、Notion 浏览器范围 | 单一资源身份/版本/ACL；独立入口导出 | 范围内交叉读写零分叉；未支持入口明确报错 |
| V07 身份时间 | 多角色/作用域、隐藏资源、DST/时间戳、版本冲突、限流和异步中间态 | 权限真值矩阵、时钟事件表、服务状态机 | 越权及虚假任务执行为 0；时间/状态偏差逐项判定 |
| V08 并发隔离 | 双写/读写竞争、相同名不同 episode、缓存/游标/blob 互串、旧 job 重置后提交 | 检查历史满足该服务隔离语义；观察跨 episode 键 | 跨 episode 泄漏/损坏 0；不把全部服务强制线性一致 |
| V09 恢复回放 | 每个提交/响应/队列边界故障注入，snapshot clone/reset，固定日志回放 | 状态 hash/输出 hash/事件序列/幂等边界 | 可重建状态与响应完全一致；非幂等重复结果符合真实契约 |
| V10 数据分布 | 多 seed、页边界、长文、重复/缺失/干扰/权限、未见任务图 | 分布统计、命名预测 baseline、训练测试内容相似检测 | 无答案字段泄漏；分布缺口逐域披露；避免只随机改名 |
| V11 LLM 质量 | 重复读、长序列、换工具、缺上下文、恶意业务文本、要求“不存在也成功” | 外部规则+提交态+真实记录+人工盲审；非同 LLM 自评 | 幻觉/错误接受/越权/解题提示硬失败 0；修复失败不提交 |
| V12 性能成本 | 代码/LLM/混合相同 profile/数据/任务/验证，统计并发、token、重试、有效率 | 每有效轨迹总成本、吞吐、p95/p99、CPU/内存/blob | 先通过同一保真门槛再比较性能；达不到门槛不能靠成功率补偿 |

“0”是样本中的硬错误数，不是证明总体错误率为零。若 n 个独立失败机会零错误，粗略 95% 上界可用约 3/n 作样本量规划（A，独立近似；相关序列按 cluster 统计）。例如 3,000 次零错仅能支持约 0.1% 的上界，不能声称百万调用无风险；生产还需持续抽样和失败隔离。

## 3. 逐服务的高价值反例

| 对象 | 首要契约/语义反例 | 独立 oracle 与真实验证条件 |
|---|---|---|
| google-cloud | NULL/NUMERIC/ARRAY/STRUCT/时区/SQL dialect；对象 generation 与前置条件；日志过滤/延迟；Compute 操作的运行/失败 | 小数据手算+BigQuery 受控查询记录、GCS bytes/hash 与版本、操作结果；未来专用 GCP 项目，不访问生产资源 |
| google_calendar | 时间范围边界/DST、全天/定时区分、更新/删除重读、时间窗列表；未暴露 recurrence/ACL 能力不伪造工具 | 独立时间库与真实 API 记录；固定工具硬编码 primary，须使用专用测试账号的 primary 日历，不能靠次级 calendarId 隔离；仅封闭测试参与者 |
| google_forms | batchUpdate 原子性、item/question ID、revision/writeControl、响应不可随便“写成功”、Drive/表单身份 | 表单结构图和响应记录 checker；专用表单+测试响应者，不收集真实用户数据 |
| google_sheet | RAW/USER_ENTERED、公式/值/格式差别、A1 引用、空尾行裁剪、批量与 Drive 分享一致性 | 独立网格值/公式小集/Drive ACL oracle；专用 Drive 文件夹和测试用户 |
| notion | block 树引用/分页、page vs database、rich_text 长度、归档/权限；旧 API 版本与新 data source 分开 | 独立树和属性检查、SDK/API/必要浏览器交叉；专用 workspace/page，不操作现有页面 |
| snowflake | 大小写标识符、NULL/NUMBER/TIMESTAMP/VARIANT、DDL/事务、结果截断和会话状态 | 手算+独立 SQL 样例+专用 Snowflake DB/role/warehouse 的未来差分；不以本地 SQL 引擎自评 |
| wandb | GraphQL 查询/可写 mutation 边界、run/history/artifact/reports 一致性；Weave 顶层/嵌套/缺失/零成本及 ID/时间回填；真实执行不编造 | 独立 GraphQL/状态检查，报告保存后 SDK 读取，包装投影与权威值分查；专用 entity/project |
| github | 只读/toolsets/allowlist、issue 与 PR 关系、Git blob/tree/commit/ref、SHA 冲突、分页/搜索；M 正文→REST base64→Git 原字节 | Git 对象图+REST/raw 记录及形似 base64 的普通文本负例；专用 org/repos，不能真实触发任意外部 Actions |
| huggingface | 动态账号工具 schema、SDK repo commit/files/LFS、gated/private 权限、datasets splits/config、Jobs/Space 执行 | 固定 tools/list profile + Hub SDK/files hash；封闭测试 org/repo/计算额度，动态工具未冻结不发全覆盖声明 |

详细操作和固定版本缺陷见各服务报告。对于已知 MCP bug，应将真实失败作为兼容回归证据；修复 profile 另有预期。不能因为希望业务语义正确而修改既有契约的工具成功行为，也不能把 bug 利用轨迹未经标注混入迁移训练集。

## 4. 差分验证方法及本阶段边界

**可使用现成记录的部分**：工具可见性和 schema（前提记录包含完整快照）、参数映射、输出包装、已发生的错误/分页/状态转移、跨入口相同 ID 的关联。必须记录来源部署版本/日期/权限条件。只有孤立响应无法推断前置态，更不能证明未走到的合法路径。当前仓库没有发现可直接使用的 Toolathlon dump，业务调用轨迹的 A1 未验证。本轮新增 HF 匿名 initialize/tools/list 只核实该次协议与四工具契约（shared F22），不构成工具执行或业务状态轨迹。

**需要受控真实环境的部分**：写后读/删后读、并发更新、身份权限、异步最终一致、未知 SQL/公式/批量边界、新配置动态工具、SDK/CLI/browser 交叉。后续须准备一次性资源、明确可执行操作清单、调用/费用额度、范围限定和记录脱敏方式，由用户授权后执行。本阶段仅列条件，不执行创建、修改、清理或全局部署。

步骤：冻结真实 MCP/依赖/配置和 tools snapshot → 准備可比初态与资源映射 → 从不含任务答案的操作图生成合法及非法调用 → 分别执行真实/模拟路径 → 收集各步原始响应及独立终态 → 分域解释差异 → 修正 profile 或标不支持 → 在未用于修正的 holdout 重验。操作顺序、随机性、读取时间窗和重试均入记录。

比较方式：ID 是一致双射，不是删字段；时间按字段的瞬时点/日期/时区/精度语义；集合仅在真实契约无序时排序；分页比较元素不重不漏、cursor 所属查询和状态，而不要求 cursor 字符串相同；签名 URL 比较所指对象、权限、有效期与 bytes，不要求签名相同；浮点容差必须按类型和计算规范设定，精确 DECIMAL/计数不允许任意 epsilon；异步比较允许的状态偏序和期限，不要求网络时延相同。

当规范与固定 server 行为冲突，保留两个证据，标明在哪层发生。能力矩阵应更新对应差异和 profile，而非只追求绿色测试。

## 5. 首轮试点与扩大覆盖门槛

主试点建议使用 **google_sheet + 必要 Drive X 层**：固定 0.4.1 的表格读写/建表/工作表操作/分享能力使用同一后端，让 SDK/HTTP 与 MCP 交叉访问。首轮即包含算术、SUM/AVERAGE/IF、同工作簿跨 tab 引用的小公式集，核对 formulaValue/userEnteredValue、effectiveValue、formattedValue；M 写固定 USER_ENTERED，X 额外测 RAW，不能把 M 改成 RAW 或把全部公式当字面字符串。完整公式库、外部引用及所有 batchUpdate 分支继续列为分期缺口。必须额外注入 copy 后 rename 失败、create 后 Drive move 失败及部分分享失败，oracle 分别核验 sheet 已存在、真实 parents、每个 recipient 权限；不依赖 create 返回的 folder 或 list 的完整性（固定 0.4.1 仅列 Drive 首屏，见服务报告）。

试点任务：多工作簿、多页/长数据、近似名称、权限受限项目；检索指定业务数据→按值更新/新增→经不同入口确认→遇到非法范围或权限拒绝→由 agent 修正→评测指定记录和未受影响范围。生成至少 30 个训练未见 seed（D），每 seed 变化至少结构/权限/内容三轴；为每任务保留多条合法执行路径，独立评测只看目标状态和副作用约束。

主试点能比较 LLM 的**内容预生成**价值，却不足以证明在线接口仿真的 LLM 价值。补充 **W&B `query_wandb_support_bot` 文档问答** 对照：固定 `83f6d7f` 的 `src/wandb_mcp_server/server.py:192-194` 确实注册该工具，`mcp_tools/query_wandbot.py:36-99` 访问 support bot 并返回其问答 JSON；这是真实服务允许的生成行为，不能与任意查询结果编造混淆。

在相同冻结 W&B 文档语料、相同 `question` 输入和原始输出契约下比较三组：代码检索+有限模板回答；LLM 主导组织回答+确定性来源/契约检查；混合缓存/检索快速路径+有证据时调用 LLM。问题集覆盖事实检索、多段整合、版本冲突、无资料可答、错误前提、恶意文档文本和重复问答；冻结文档版本/来源集合，答案中的事实由独立证据集与人工盲审核验，不能由同一个仿真 LLM 自评。不得把 agent 任务答案、run 私有状态或评分目标交给支持机器人，也不得额外替 agent 编写本来只是存储输入文本的报告。

该试点可比较自然语言响应的开发成本、覆盖、多样性、来源幻觉、拒答/帮助程度与单位有效轨迹成本；没有取得真实 support bot 记录前，不能宣称回答分布已高保真。它不证明 LLM 主导写事务正确，后者若进入方案须另通过 V04–V09/V11 的提案/提交测试；不能从只读问答的成功外推到 GraphQL mutation、SQL 或执行结果。W&B 领域作者与非原作者审查均已核对该工具及试点范围，证据和审查记录见对应报告。

| Gate | 扩容前的证据（D） | 未通过时 |
|---|---|---|
| G0 契约冻结 | 固定源码+完整工具清单+配置组合+输入/输出黄金样例，未覆盖工具逐项列明 | 不宣称接口高保真，先补证据 |
| G1 可迁移核心 | V01–V07 支持范围全部通过，至少 3,000 个关键负例/状态检查无硬错，独立 oracle mutation 能检出目标错误 | 修复规则/缩小发布 profile 并保留完整设计缺口；不把失败轨迹放训练 |
| G2 新结构 | 组合图/任务业务域 holdout、30+ seed、100–1,000 步长序列；反事实命名与近重复测试 | 修正生成分布或状态检索，不能固定顺序 |
| G3 隔离恢复 | 1→10→100 episode 并发梯度，所有 V08–V09 边界无串读/双提交，重建 hash 一致 | 暂停扩容，先定位隔离或日志问题 |
| G4 LLM 价值 | 三组同契约同语义门槛后比较有效轨迹成本、开发工时、修复率、尾延迟、未知组合失败率；人审盲评 | 无净收益则移除在线 LLM，保留初始化用途 |
| G5 更大覆盖 | 新工具/SQL/公式/执行/动态 profile 先补真实差分与错误集，再测 1,000 episode 及目标日调用量 | 不用高吞吐代替语义证明 |

这些样本数和并发梯度是首轮测量起点；若缺陷高度相关，需增加独立环境和错误类别。发布声明逐维列 I/S/C/T/D/P，不给一个总分掩盖缺口。最终 agent 在真实受控环境上的迁移评测用于检验训练收益，但不能反过来代替 API 一致性验证。
