# 面向大规模 agent 合成的高保真 MCP 模拟环境设计

分析日期：2026-09-10；仓库基线：`ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7` 及本次工作树。**九对象分析、非原作者交叉审查、原作者修订和文档验收均已完成。** 本阶段仅分析、文档和只读扫描；没有实现 mock、改变任务行为、启动完整 benchmark、写入真实业务、清理资源或全局部署。F=核实事实，D=设计建议，A=规划假设，U=待确认。

**总体建议（D）：采用分服务的确定性业务状态与执行组件，保留/精确复现各自 MCP 契约，并让 SDK、HTTP、CLI 等入口接同一权威状态。LLM 主要用于多样环境内容，以及真实接口本来允许的生成行为；不以一种技术覆盖全部服务。首轮优先 Sheets+必要 Drive 状态链，另以 W&B 原生 support bot 做在线 LLM 对照。**

这是一组“可核实版本的 MCP 接口 + 支撑合理操作的后端语义”的设计，不是整个云平台复刻计划，也不是 current finalpool 最小工具集。任意 SQL、GraphQL、代码/Jobs 等工具代表开放的语义族，需要显式支持范围与错误，不能把工具名数量当作实现规模。训练可信度取决于状态一致、参数/权限/计算正确、数据分布和独立验证，不取决于返回多少次 success。

## 产物与阅读路径

| 产物 | 内容 |
|---|---|
| [shared.md](mcp-mock/shared.md) | 公共调用链、F/D/A/U、M/B/X、保真向量、共享机制、复核后的冲突 |
| [capability-matrix.csv](mcp-mock/capability-matrix.csv) | 127 行能力族/入口，11 列版本、操作、状态、方案、LLM、缺口、验证、优先级与证据；各服务报告保留全工具清单 |
| [9 份服务报告](mcp-mock/services/) | 同一 10 节模板，工具清单、状态模型、组合序列、方案比较、LLM、合成与审查 |
| [synthesis-design.md](mcp-mock/synthesis-design.md) | 多 seed/任务生成、oracle、并发隔离、快照回放、数据质量、LLM 状态链与规模成本 |
| [validation-plan.md](mcp-mock/validation-plan.md) | V01–V12 验证、真实差分条件、G0–G5 门槛、主试点与 LLM 对照 |
| [source-inventory.json](mcp-mock/source-inventory.json) / [scan_inventory.py](mcp-mock/scan_inventory.py) | 本次任务成员与公共源码 SHA-256；只读扫描，不导入配置、不读取凭据，不代表运行工具快照 |
| [service-template.md](mcp-mock/service-template.md) / [audit_artifacts.py](mcp-mock/audit_artifacts.py) | 统一报告模板和文档结构/矩阵/源码一致性校验；不是 mock fidelity verifier |
| [review-ledger.md](mcp-mock/review-ledger.md) | 非原作者审查、原作者修订、跨报告问题处置与逐项需求验收 |

## 1. 统一保真标准与源码边界

先定义六维 **I 接口、S 业务状态、C 跨操作/跨入口一致性、T 身份和时间、D 数据分布、P 规模性能**；每维单独报告“可准确复现、有限范围准确、近似、分期、U”。不用一个总分掩盖 SQL 计算错误或接口不完整。完整标准见 shared 的保真表。

- I：原始/模型侧名称和说明、输入 schema/必填/默认/实际 parser、输出 content/MIME/元数据、错误层级、工具可见开关、资源/提示/协议；改名、过度简化描述、放宽参数或改输出形状都会改变 agent 行为。
- S/C：ID/引用/版本/生命周期、写后读/删后读、搜索/分页/过滤/排序/批量/直接读，全部来自同一业务状态；真实分步操作保留部分失败，不把所有 MCP 调用强行事务化。
- T：作用域、账号/组织/项目/工作区、权限、不存在/冲突/重复、时区、异步和限流按服务分别建模；不把 wrapper allowlist 当后端 IAM。
- D/P：多样规模/内容/历史/权限/干扰与吞吐/隔离/恢复分开测。固定 seed 可复现，不等于固定数据或固定调用顺序。

三层范围分别列出：M 是当前配置实际暴露的 MCP；B 是必需后端语义以及不在 M 中的其他平台能力；X 是初始化/评测/SDK/HTTP/CLI/浏览器额外入口。同一资源经 M/X 访问必须同态，但不能因为一个厂商就合并 OAuth、IAM 或资源 ID。

F：已读 `docs/mcp-analysis.md` 及适用目录（未发现 AGENTS.md），以当前实现为准。`utils/mcp/tool_servers.py:50-130` 读取 YAML 并合并任务配置；`utils/roles/task_agent.py:465-551` 连接服务、合并本地工具并记录模型工具；`tool_name_aliases.py:21-28` 改模型别名但不改原始 dispatch；`custom_mcp_util.py:129-177,187-229` 有 schema/参数转换、content JSON 包装及长输出截断。初始化/配置可能执行业务代码，见 `task_agent.py:983-1001`、`utils/data_structures/task_config.py:250-258`，本次没有 import 这些入口。

F：重新扫描 108 个 finalpool task_config；九对象声明任务数为 Cloud 8、Calendar 2、Forms 2、Sheets 11、Notion 8、Snowflake 4、W&B 3、GitHub 7、HF 5，成员见 source-inventory 与各报告，任务可重复涉及多个服务，不能相加当任务总数。**声明外仍有依赖**：Forms 的 `fillout-online-forms` 走浏览器/SDK；Notion 初始化有 notion_official/Playwright；GitHub 的初始化/CLI 也不能只按 needed_mcp_servers 判断。现有轨迹仅能证明已用路径，本次未找到可用 Toolathlon dump，不声称有真实轨迹实证。

## 2. 九对象的保真上限、难点和推荐路线

以下是设计可行性，**不是已实现或测得的兼容等级**。I 的精确复现还需固定全部运行依赖和捕获实际 tools/resources/prompts 快照；后端滚动策略另记日期/profile。D 通过受约束多 seed 内容生成提升，P 需按真实负载压测，二者均未验证。

各维目标单列如下；“可准确”指有条件的设计上限，“限域”指必须列明支持语义，“分期”指高级行为尚不在首批实现。“待测”不能由源码分析替代。

| 对象 | I 接口 | S 状态 | C 跨入口 | T 身份/时间 | D 数据分布 | P 规模 |
|---|---|---|---|---|---|---|
| google-cloud | 固定源可准确，依赖待冻结 | SQL/GCS 限域，Compute 分期 | 多 SDK/对象限域准确 | IAM/异步分期校准 | 多项目/类型/历史待测 | SQL/执行负载待测 |
| google_calendar | 固定包可准确，运行 U | 事件/PATCH 可准确，recurrence 限域 | 同 primary 状态可准确 | ACL/DST/时间窗需差分 | 历史/冲突/密度待测 | 时间展开负载待测 |
| google_forms | 固定源可准确 | 结构/响应限域准确 | Drive/API/页面分期对齐 | 发布日期/ACL/revision 待差分 | 题型/回答/版本待测 | 大响应集待测 |
| google_sheet | 固定源可准确，content 依赖 U | 网格可准确，公式限域 | Sheets/Drive/SDK 可准确 | ACL/并发/部分失败需差分 | 类型/公式/干扰待测 | 大网格/重算待测 |
| notion | 固定 OpenAPI 可准确 | 树/属性限域准确 | API/SDK 可准确，remote/UI 分期 | ACL/缓存/策略需差分 | 长文/树/历史待测 | 树遍历/索引待测 |
| snowflake | 固定源可准确，依赖待冻结 | 方言/类型/事务限域 | 会话/connector/Snowpark 限域 | role/warehouse/时间需差分 | 数据倾斜/NULL/类型待测 | 查询执行待测 |
| wandb | 六工具固定源可准确 | GraphQL/Weave/报告限域 | SDK/HTTP 多入口分期对齐 | entity/异步/限流需差分 | runs/文本/回答分布待测 | history/trace/LLM 待测 |
| github | 静态工具集可准确，配置待核 | Git 可准确，平台长尾分期 | Git/REST/GraphQL/CLI 限域 | token/ACL/搜索/执行需差分 | 仓库/讨论/历史待测 | Git/索引/Actions 待测 |
| huggingface | 匿名快照已核，账号集合 U | 仓库/文件限域，执行分期 | Hub/Viewer/raw/SDK 分期对齐 | gated/ACL/配额需差分 | 仓库/数据集/搜索待测 | blob/Viewer/执行待测 |

| 对象/报告 | 可达到的保真范围与主要难点 | 首选与备选（D） |
|---|---|---|
| [google-cloud](mcp-mock/services/google-cloud.md) | 39 个工具；I 源码包装清楚。S/C 在经差分的 BigQuery SQL、GCS 字节/版本、Logging/Compute 状态机范围可高；SQL 方言/统计、签名/IAM、日志投递和异步是长尾。不能承诺全 Google Cloud | 保留 MCP+本地 API/SDK transport；核实版本的 BQ/GCS 模拟器加独立语义层；Logging/Compute 代码状态机；备选兼容 MCP facade。LLM 离线内容 |
| [google_calendar](mcp-mock/services/google_calendar.md) | 5 工具；I 可按 1.0.2 锁基线。S/T 难点是 primary 身份、PATCH、时间窗、DST、既有 recurrence/attendees 和截断；M 未提供这些字段写入不代表读取可忽略 | 确定性 Calendar 内核+契约 facade；备选保留 Node MCP 换 API/认证。LLM 离线文本，不决定日程结果 |
| [google_forms](mcp-mock/services/google_forms.md) | 5 工具；基础 S/C 可准确。高级题型 rich-read、Forms/Drive/页面提交一致性、发布默认迁移和 revision/历史回答是难点；M 不能凭空获得发布/提交能力 | 有状态 facade+Forms/Drive API 核心，必要 SDK/页面适配；备选保留 wrapper 换后端。LLM 生成初始问卷/回答内容 |
| [google_sheet](mcp-mock/services/google_sheet.md) | 15 工具与 spreadsheet resource template；网格/ID/Drive 的 S/C 可精确。公式/类型/格式、A1 引用、多步部分失败、FastMCP 输出及资源兼容需独立核验 | Sheets/Drive 权威内核+公式执行组件，保留或匹配 MCP；SDK/HTTP 共用；备选 facade。LLM 仅非结构化初态内容 |
| [notion](mcp-mock/services/notion.md) | 19 工具；固定 OpenAPI 有窄 schema/包装缺陷。Block 树、属性、版本、ACL/搜索缓存可较高；远程 duplicate/move 与 UI、多 data source 新版是额外难点 | 保留有 BASE_URL 钩子的固定 wrapper+本地 HTTP 权威状态；SDK/UI/remote profile 分层适配；备选 facade。LLM 初始长文 |
| [snowflake](mcp-mock/services/snowflake.md) | 14 工具，写开关及 resource/序列化另核；S 的大头是 SQL/NUMBER/NULL/时间/VARIANT/会话/DDL 事务，不能用本地 SQL 相似语法代替兼容 | 固定 MCP+受控 Snowpark/connector/API 适配与经差分执行器；备选 facade。LLM 造业务背景，不产出 SQL 结果 |
| [wandb](mcp-mock/services/wandb.md) | 固定提交六工具；GraphQL/Weave 查询、报告写入、support bot 必须分开。S/C 需 run/history/artifact/报告一致；动态后端 schema/查询及自然语言回答分布 U | 代码 GraphQL/Weave/报告状态与真实必要执行；support bot 可用受来源约束 LLM/RAG；备选保留 server 换后端 |
| [github](mcp-mock/services/github.md) | 固定源码 91 业务工具、可选 3 dynamic 工具，另有 resources/prompts；只读环境键存在绑定冲突，不能据 YAML 推定实际只读。Git 图/文件/issue/PR 可高，搜索、Actions/安全/自动编码及权限长尾需分期 | 真实 Git 对象与操作+GitHub HTTP/GraphQL 语义层+原 MCP；备选 facade。LLM 初始 issue/代码内容，执行结果来自执行器 |
| [huggingface](mcp-mock/services/huggingface.md) | 匿名 0.4.18 四工具快照已核，hf_fs 含广泛路径/命令；未有指定账号快照不能声称全量 I。Hub repo/commit/files/ACL/SDK 可按 profile 设计；搜索、datasets、Jobs/Space/推理的不同后端需分开 | 冻结工具 profile+本地 Hub/API/blob/Git/执行层；LLM 可做内容/有证据的原生生成能力；备选已验证范围 MCP facade |

相对开发成本：Calendar/Forms 基础域较低但后端/权限不能省；Sheets/Notion/Hub 仓库域中高；SQL/GraphQL 全语义、GitHub 执行/安全、Cloud 多服务最高。纯 LLM 可以快出格式样例，但不能省掉 ID、ACL、状态、精确执行和 oracle；长期成本通常随每工具模型调用增长。具体各服务比较、token/延迟假设和代码/LLM/混合三路线见其第 5/7 节；没有实测前不承诺人日或商业价格。

## 3. 必须先做的能力与不能接受的近似

优先级围绕迁移价值、任务多样性、共享收益、开发/运行成本、可验证性和数据风险综合判断；finalpool 覆盖仅是辅助。

**共同 P0**：冻结工具契约和实际 parser/包装；权威状态、稳定 ID/引用、身份/权限、写后跨工具读、错误及部分失败；必需 SDK/HTTP/CLI 路由；真实计算/查询结果；独立 oracle；episode 隔离和可验证日志。每个服务还须支持合理读取中出现的丰富对象，即使 M 没有相应创建工具。

| 不可接受的近似 | 会训练出的错误规律 | 控制 |
|---|---|---|
| 写入总成功、非法参数静默纠正、越权自动授权 | 不查状态、不修参数、盲目重试 | 真实拒绝集、提交前后故障、独立终态检查 |
| SQL/GraphQL/代码用 LLM 编结果，数值全转 float，NULL 当零 | 不正确查询/统计也有“合理答案” | 执行组件与类型语义集；兼容 wrapper 精度损失只在输出层记录 |
| 搜索/分页/SDK 各用独立 fixture、隐藏自动翻页 | 不存在的 ID 可读、重读自动出现目标、接口范围误学 | 一份状态和索引水位；保留实际页参数与 wrapper 截断 |
| 为方便统一全回滚、create 自动幂等、异步瞬时成功 | 不会处理中间态、部分失败与不确定提交 | 分服务提交边界、job 状态机、并发历史验证 |
| 模板命名泄题、固定干扰/权限、仅复刻答案轨迹 | 依赖环境规律捷径而不学工具组合 | 多轴 seed、反事实改名、图结构/领域 holdout、不可见 oracle |
| 假本地服务返回无法访问的真实 URL、只换 MCP 漏 SDK/CLI | 轨迹在真实文件/网页或多入口立即失效 | 显式 URL/文件/对象/认证路由，验证引用能解析且 ACL 正确 |

合法但未实现的功能必须在 manifest 明示，并返回与原服务包装一致的可识别不支持错误；若真实服务无此错误，要标模拟器扩展，不能伪装成原生。固定 MCP 的已核实缺陷可有兼容回归 profile，但独立 oracle 不接受错误状态，缺陷利用轨迹默认不进主迁移训练集。修复 profile 使用新版本契约，不静默改旧版。

## 4. 可共享的组件与必须独立的语义

可共享：episode 路由/认证主体映射、事务与提交收据、内容寻址 blob、虚拟时钟/可控事件队列、日志/快照/克隆/reset、依赖/工具 manifest、契约快照校验、LLM 调用网关/提案格式/版本校验/来源记录、指标与审计。PostgreSQL 等只承担存储/事务，不承担 Snowflake/BigQuery 方言兼容；完整说明及官方兼容边界见 synthesis §5。

必须独立：Cloud IAM 与 Workspace OAuth/Drive ACL、Calendar 时间/recurrence、Forms 题目/revision/publication、Sheets 公式/网格、Notion Block/属性/数据库、SQL 两种方言/事务会话、W&B GraphQL/Weave/报告、Git commit 图/PR/Actions、HF repo/datasets/Jobs/Spaces。统一 ID 服务只能分配各域合法 ID，不能把所有 ID/URL 形状改成统一 UUID。

可确认的共享业务关系：Forms/Sheets 的 Drive File 映射与 ACL；GitHub/HF 可共享 Git/大文件存储基础机制但有各自 API/权限/版本与数据模型；W&B artifact→HF 文件、Cloud→表格/Calendar/Notion 等是显式复制或引用，带来源 ID/版本/hash，不自动共享授权或级联删除。跨服务任务必须声明每个入口的 principal/资源可见性与一致性期限。

## 5. 超出既有任务的合成方式

以 seed/config 生成多规模、多层级、长内容、历史、缺字段、近似名称、重复与干扰、权限差异和关联资源。状态生成后用独立约束验证；从状态生成任务，或从任务约束构造环境再证明存在可行路径。任务成功标准是业务状态/产物和允许副作用，允许不同正确操作顺序；不把参考轨迹传给环境。

训练/测试拆分同时包含内容、业务领域、工具族和调用图结构；覆盖创建→查询→修改→再查→删除、分页定位→批改、参数/权限失败→恢复、多工具同资源、跨服务交接、异步/并发/中断等组合。当前 finalpool 单独回归，不影响最终工具/语义覆盖分母。详见 synthesis §2–4、各服务 §4/8。

## 6. 如何证明行为一致性

先比固定工具和原始/模型输出契约，再比独立状态/业务不变量、负例、随机操作图、多入口、并发恢复和数据分布；随后使用受控真实差分验证迁移语义。不能让模拟器与评测器复制同一业务 handler；用独立关系检查、人工审定小数据结果、真实记录和 mutation testing 验证 oracle 本身。

差分保留 ID 双射/引用关系、时间语义、分页完整性/游标约束、顺序、精确数值和异步状态偏序；不靠删除所有动态字段制造一致。真实服务写入实验仅在未来明确授权的专用账户/资源/额度下执行；本阶段不运行。验收依据是 validation 的 V01–V12 与 G0–G5，零样本错误仍报告样本量/统计边界，不能当作总体零风险。

## 7. 规模、隔离、恢复与复现

建议共享服务进程和不可变内容，按 episode 分片权威状态；所有主键、FK、索引、缓存、cursor、blob 权限、异步 job 和 SDK 会话均绑定 episode。敏感执行组件用独立沙箱。不同 episode 可用相同可见资源名而不串读；不复用当前全局 deploy/prune 回收环境。

快照含业务状态/ACL/版本、虚拟时钟、随机流、队列水位、索引与 blob；clone 采用基线+overlay，reset 换 generation 使旧会话失效。记录每个真实提交单元与响应；崩溃恢复按日志重建，不重新执行已提交的非幂等 create。LLM 输出和校验结果也入日志，回放不重新采样模型。

规模逐级测 1/10/100/1000 episode 与实际调用/响应分布；吞吐、p95/p99、token 配额、DB/执行/blob 成本及失败废弃成本分别报告。合成设计的示例假设 100 tool/s、3 秒/模型调用、10% 修复，在全 LLM 路径约需 330 个在途请求；这些是容量规划算式，尚非运行表现。

## 8. LLM 路线的职责、偏差与总成本

每服务均比较代码主导、LLM 主导及混合。推荐代码负责 schema/实际投影、ID/引用、ACL、SQL/代码执行、精确计算/排序/分页、持久化/并发。LLM 可承担合法初始化文本、真实服务本来允许的生成行为或经约束的实验提案，不因接口难实现就交给模型猜结果。

候选提案链：调用+经权限检查的完整相关状态→LLM 提案→外部契约/不变量/权限/版本校验→按真实提交边界写入→从已提交态生成最终响应。大状态通过精确索引查询和 blob 引用获取，摘要仅用于定位；查询遗漏不能变成不存在。失败最多有限修复，不为 agent 修正非法输入；冲突重取状态；失败不提交且记录为仿真故障。仿真 LLM 不接评分目标/任务答案，业务文本不能覆盖规则。

用独立 oracle、真实记录和人审测长序列漂移、资源/字段/结果幻觉、非法接受、过度成功、额外解题帮助、答案泄露与重复读取一致性。LLM 生成新文字只有在初始化/合法创建或原生生成接口时才成立，已有 read 值必须来自状态。

成本按有效轨迹计算：开发/维护、初始化、运行模型和执行、校验、失败重跑、存储。`N*f*a*(1+r)*(Tin*pin+Tout*pout)/1e6` 是额外仿真模型费，其中 f 是 LLM 路径比例，a 是每次调用模型数。synthesis §7 的占位价格示例把 100 万次全 LLM 调用算为 $26,400，f=5% 为 $1,320；**虚构价格仅作敏感性，不是供应商报价**。确定性快速路径、内容预生成、独立 episode 批处理、带状态/权限版本缓存与高频规则固化是降本方向；不能以跳校验降低成本。

## 9. 第一批实现建议、试点与后续批次

本节是后续规划，不授权或启动实现。优先级是有依赖的批次，不是删除低优先能力。

1. **A 批：共享最小内核 + Sheets/Drive 完整契约试点 + Calendar**。Sheets 有固定 15 工具和跨 API 状态价值，加入常用精确公式小集、Drive ACL/文件、拷贝/重命名/移动/分享部分失败、多入口 oracle；Calendar 工具少但时间/重复/跨进程约束能验证状态内核是否可迁移。A 批需 G0/G1/G2/G3，不能仅现有任务 PASS。
2. **B 批：Forms + Notion 结构资源，W&B 有限 GraphQL/Weave/报告与 support bot 对照**。复用 Drive/长文/blob/身份机制，扩展 UI/X 入口和独立树/属性约束；已暴露报告写工具不能因为现有任务只读而忽略。原生问答用于对比在线 LLM 价值。
3. **C 批：GitHub/HF 仓库文件与版本共享机制**。使用真实 Git/字节，不把本地 Git 服务当 GitHub/Hub API 完整替代。先冻结 HF 工具配置，再对写入、datasets/执行等分别验收；动态工具未冻结不宣称全兼容。
4. **D 批：Cloud BQ/GCS 与 Snowflake 专项兼容、Logging/Compute、GitHub/HF 执行长尾**。SQL 可在前面并行做证据与差分准备，发布需各语义族门槛。优先真实执行和类型正确；高级 SQL、网络外部函数/计算/异步平台依次扩展，不交给 LLM 编结果。

主试点的可审查闭环：生成含近似名/权限差异/多 tab/类型/公式的环境→agent 发现目标→读/更新/复制/分享→参数/权限或后半步失败→依据工具/状态调整→SDK/HTTP 和 MCP 交叉读→独立评测目标和未受影响数据。包括不同顺序与未见业务结构，不围绕某个答案实现。

补充 LLM 试点选择 W&B `query_wandb_support_bot`，对冻结文档与相同问题比较代码检索模板、LLM 来源约束回答、混合路径。衡量回答依据、无证据拒答、版本冲突、提示注入、帮助程度、重复问答、吞吐/费用和人工盲审。这个试点不能证明 LLM 写事务一致，也不能证明全 GraphQL/SQL 可仿真；后者另过提案/状态门槛。具体实验设计和扩大覆盖 gate 见 validation §5。

## 10. 待确认、协作与本阶段验收

跨报告未确认项必须有具体取证动作：运行镜像/依赖/实际握手→离线只读 manifest 和隔离 tools snapshot；远程账号工具→指定账号/配置下全分页快照；后端精细错误/权限/并发/发布策略→未来受控差分；模拟器/SQL/公式兼容→固定版本正负例和独立执行检查；运行成本/LLM迁移效果→相同语义门槛下实测。**U 代表本分析明确的验证边界，不等于已证实可兼容。**

统筹、领域和审查均使用 `gpt-6-astra / xhigh`。2026-09-10 12:02 UTC 重新核验本次统筹及八个领域会话的实际运行元数据 `model/effort`，覆盖分析、审查和修订各 turn，不只依据默认配置；创建子 agent 显式指定相同值。没有降模型或强度。最多 1 位统筹+3 位领域/审查同时运行，领域一次一个 MCP。公共文件由统筹维护，作者只改自己报告；九份报告均由非原作者审查，问题经原作者修订、统筹复核闭环。

| 阶段 | 分派/状态 | 模型证据 |
|---|---|---|
| 统一摸底 | 统筹先写 shared/template 再派发 | 统筹运行 model=gpt-6-astra、effort=xhigh 已核 |
| 领域第 1 批 | google_cloud、google_calendar、google_forms 分析及后续修订完成 | 三会话实际 model/effort 均已核 |
| 领域第 2 批 | google_sheet、notion、snowflake 分析及后续修订/登记完成 | 三会话实际 model/effort 均已核 |
| 领域第 3 批 | wandb、github、huggingface 分析及后续修订/登记完成；HF 顺序复用 Snowflake 会话 | 创建/复用同一目标模型，实际 model/effort 已核 |
| 非原作者交叉审查 | github 审 Forms/Notion/Snowflake；wandb 审 Cloud/Calendar/HF；snowflake 审 Sheets/W&B/GitHub；全部问题已处置 | 三审查会话实际 model/effort 已核，逐项证据见 review-ledger 和各报告 §9 |
| 产物验收 | 九报告、127 行/11 列矩阵、源码 hash/任务成员、43 个本地链接及 Markdown 表格检查通过 | 仅文档和源码一致性检查；运行保真、规模与迁移仍待未来实验 |

已合并的具体发现与证据见 shared F09–F33；各服务第 9 节记录审查问题、来源和处理，review-ledger 对原始十二章要求逐项建立验收落点。残余 U 均有补证动作；没有将运行依赖、账号策略、完整 SQL、动态部署或 LLM 效果写成已验证事实。

文档检查命令：先 `python docs/mcp-mock/audit_artifacts.py --matrix > docs/mcp-mock/capability-matrix.csv` 从作者报告汇总，再运行 `python docs/mcp-mock/audit_artifacts.py`。最终输出 `result=pass`、`services=9`、`capability_rows=127`、`source_hashes_unchanged=true`、`local_links_checked=43`、`markdown_tables_consistent=true`、`runtime_fidelity_tested=false`。另对本次 19 个产物做可识别 token/私钥模式扫描，无匹配；该模式检查不等于全面秘密检测，也未读取凭据文件。已有用户暂存文件和本次范围外文件保持不变。

本阶段在分析与交叉复核完成后结束，不自动进入实现。
