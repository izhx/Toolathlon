# 交叉审查与需求验收记录

查阅日期：2026-09-10。统筹维护。本文记录本阶段的文档与证据审查，不代表模拟器运行验证。F=事实、D=设计、U=待确认。

## 1. 角色、模型和文件边界

统筹先完成 shared/template 与框架摸底，领域分三批、每位一次只负责一个 MCP；最多三位领域/审查与一位统筹并行。所有创建配置均显式 `gpt-6-astra / xhigh`。2026-09-10 12:02 UTC 再查本次统筹和八个领域会话的实际运行 `model/effort`，包括分析、非原作者审查和作者修订，各 turn 均为该值；HF 复用完成 Snowflake 后的同一会话，没有模型降级。

领域作者只维护自己报告；审查者只提交问题和证据，由原作者修订，统筹更新共享材料并确认处置。HF 的作者与 Snowflake 相同，所以不能由该作者互审这两份报告。

| 服务 | 原作者 | 非原作者审查分工 | 状态 |
|---|---|---|---|
| google-cloud | google_cloud | wandb | C-01 作者修订完成，统筹复核闭环 |
| google_calendar | google_calendar | wandb | CAL-01 作者修订完成，统筹复核闭环 |
| google_forms | google_forms | github | F-01/F-02 作者修订完成，统筹复核闭环 |
| google_sheet | google_sheet | snowflake | SH-01 作者登记完成，统筹复核闭环 |
| notion | notion | github | N-01 作者登记完成，统筹复核闭环 |
| snowflake | snowflake | github | SF-01 作者修订完成，统筹复核闭环 |
| wandb | wandb | snowflake | WB-01/WB-02 作者修订完成，统筹复核闭环 |
| github | github | snowflake | GH-01/02/03 作者修订完成，统筹复核闭环 |
| huggingface | snowflake（顺序复用） | wandb | HF-01 作者登记完成，统筹复核闭环 |

## 2. 审查问题与处理

主要问题按服务写入其第 9 节，包含问题、来源/行号、处理和残余 U；本节汇总跨报告问题。审查尚未完成时不得将自检或统筹读稿称为非原作者交叉审查。

| 编号 | 问题与影响 | 证据 | 处理/验证状态 |
|---|---|---|---|
| ROOT-01 | MCP 顶层错误与模型输出不同，统一包装会误导 agent | shared F06/F09/F19/F20 | 统一原始/模型双快照，保留各 wrapper 错误层级；D，未来 V01–V03 验证 |
| ROOT-02 | 多步 MCP 操作不是统一原子事务 | shared F15/F21；Cloud move 源码见服务报告 | 提案提交按真实后端提交单元；Sheets/Cloud/W&B 独立部分失败 oracle；D |
| ROOT-03 | 文档和后端策略日期不同，固定 API header 不冻结服务政策 | shared F13 与版本双坐标说明 | Forms publication 使用 dated profile，实际租户 rollout U；不通过自动发布修复旧任务 |
| ROOT-04 | 只换 MCP 或单个 endpoint 会遗漏 SDK/HTTP/浏览器 | shared F18/F21/F23，各服务 §1 | M/B/X 路由与同态逐入口列清；未有运行验证的部分保留 U |
| ROOT-05 | 本地 SQL 引擎或数据库约束与目标平台不同 | Cloud/Snowflake §5–6，shared SQL 约束说明 | 支持语义集+真实差分，存储 FK 不自动成为用户 SQL FK；D |
| ROOT-06 | 表格内 JS 的竖线未转义，渲染会拆成多列 | Calendar 初稿第 88/90 行，Forms 初稿第 61 行 | 原作者已修订转义并保留表达式语义，统筹列宽检查通过；见 F-01/CAL-01，闭环 |
| F-01 | Forms 表格竖线渲染问题，P3 | 非原作者 github 确认 ROOT-06；Forms 初稿第 61 行 | 原作者已修，统筹重新检查列宽通过，闭环 |
| F-02 | Forms 的“稳定 ID”规则缺少合法 UpdateItemRequest 重设 ID 例外，P2 | 非原作者 github；[官方 UpdateItemRequest](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/batchUpdate#UpdateItemRequest)；统筹重新读取确认，查阅 2026-09-10 | 作者已在 §2/3/4/6/7/8 与 CSV 补 mask 规则、版本化 ID 和独立历史回答验证；统筹逐处复核。旧回答行为 U08 保留，不新增 M 工具；闭环 |
| N-01 | Notion 非原作者审查未发现实质修订问题 | github 重核固定 OpenAPI 19 operations、parser/proxy、BASE_URL/page guard、SDK/remote/UI 分层、LLM 三路线与独立 oracle | 作者已登记核对范围并保留原有 U；统筹重读首页和 §9，无正文事实改动，闭环 |
| SF-01 | Snowflake 空行集包装的目录链式失败遗漏，P2 | 非原作者 github；shared F26 所列固定代码已由统筹复核 | 作者已补 §2/4/8 与 CSV 的空目录失败、合法首表替代及严格/修复 profile；统筹逐处重读确认，保留运行 U，闭环 |
| C-01 | Cloud 未知工具名一律“协议层拒绝”的断言过强，P2 | 非原作者 wandb；shared F27 的固定 SDK 证据经统筹重读，核正源码行号 | 原作者已补 §2/6/8 与 CSV，区分 ToolError 工具结果和未知 RPC method；统筹重读核实，运行 SDK U 保留，闭环 |
| CAL-01 | Calendar 未转义 JS 竖线，P3；无新增实质问题 | 非原作者 wandb 重核发布包 hash、五工具/SDK0.4.0握手与官方时间窗/分页语义，确认 ROOT-06 | 作者已修四处表达式竖线并登记，统筹重读及完整 Markdown 检查通过；原 U 保留，闭环 |
| SH-01 | Sheets 非原作者审查未发现实质修订问题 | snowflake 重核固定 server hash、15 工具/1 资源、全部 11 声明任务及 Drive-X、FastMCP 列表投影与缺 resource 方法、HyperFormula 固定兼容边界 | 作者已登记具体范围及接受结论；统筹核对首页/§9，正文和 U1–U6 保持，闭环 |
| HF-01 | HF 非原作者审查未发现实质修订问题 | wandb 重核两原始快照字节/hash、匿名四工具/输出、固定源11具名+动态与账号 U、Viewer/UTF-8/URI/执行/共享状态、三路线与独立 oracle | 作者已登记接受审查，统筹重读首页/§9；实际部署/账号/语义分布/执行 U 保持，原始快照未变，闭环 |
| WB-01 | Weave 成本排序误写为会排除无成本并正确排序，P2 | 非原作者 snowflake；shared F29 源码链经统筹复核 | 作者已修 §2.4/6/8/CSV 并登记，统筹逐处重读；区分缺失、零、嵌套与顶层成本，记录独立反例及实际响应 U，闭环 |
| WB-02 | Weave trace/span/parent 三字段被误写为值必须不同，P2 | 非原作者 snowflake；shared F30 源码链经统筹复核 | 作者已修 §2.4/3/6/8/CSV，统筹重读；允许兼容回填 trace_id=id，隔离响应时钟/填充值与权威状态，保留合法父边约束，闭环 |
| GH-01 / 作者 G-01 | GitHub create_or_update_file 的 M content 被误写为 base64，P2 | 非原作者 snowflake；shared F31 固定源经统筹复核 | 作者已修 §2/4/6/8/CSV，统筹重读确认；M 正文和 REST base64 分层，加字面 SGVsbG8= 及独立 Git/raw bytes 反例，运行差分 U，闭环 |
| GH-02 / 作者 G-02 | GitHub cwes 的可选数组 parser 缺陷遗漏，P2 | 非原作者 snowflake；shared F32 的 handler/入站类型链 | 作者已修各对应章节/CSV，统筹重读；区分省略与提供数组/空数组/null 的 wire 结果，专用 parser 与通用断言不混用，运行快照 U，闭环 |
| GH-03 / 作者 G-03 | 子 issue 重排被简写为“至少一定位”，P2 | 非原作者 snowflake；shared F33 经统筹重读 | 作者已修各对应章节/CSV，统筹重读；恰一非零在 OptionalInt 转换后检查，加双给/省略/0/小数反例，不加强原 number schema，运行差分 U，闭环 |

九份报告均已经非原作者审查。审查者核对固定源、工具/入口边界、候选兼容性、状态和 LLM/oracle 方案；未发现架构需要推翻的证据。上表逐项记录原作者修订和统筹核验，运行镜像、账号策略、完整 SQL 与差分效果等既有 U 保持，不因审查完成而写成运行事实。

## 3. 原始需求的逐项落点

| 原始章节 | 本阶段可审查落点 | 验收要点 |
|---|---|---|
| 一 核心目标 | 总体 §1–3/5/9；全部服务 §1/4/8 | 以实际暴露能力及合理语义为界，finalpool 仅例子；设计结束后不进入实现 |
| 二 范围与原则 | shared 术语；服务 §1/2/6；总体 §3/4 | M/B/X 分开、未实现显式失败、本地/公网分类、不过度复刻平台 |
| 三 统一保真 | shared 六维表；总体 §1/2；各服务缺口 | I/S/C/T/D/P 独立，schema/状态/分布/性能不合成一分 |
| 四 源码摸底 | shared F01–F33；source-inventory.json；服务 §1/2 来源索引 | 当前源码/版本/路径行号、任务外入口、安装依赖与动态快照；不导入配置 |
| 五 单域分析 | 九份服务报告同一 10 节模板 | 全工具/能力族、状态/约束、组合、候选方案、缺口及误学风险、LLM |
| 六 合成设计 | synthesis-design §1–8；服务 §8 | 多样初态、双向任务生成、可解性、独立 oracle、多路径、隔离/恢复/质量 |
| 七 服务重点 | Cloud/Snowflake §5/6；Google 各报告 §1/3；Notion/GitHub/HF §1/3；W&B/HF §2 | 方言/类型/NULL、Drive/认证、Git/文件/多入口、已暴露写与动态工具 |
| 八 LLM 七项 | 九报告 §7；synthesis §6/7；validation V11/V12 | 代码/LLM/混合逐域比较；相关状态、外部校验、提交/回放、幻觉/泄题、成本假设 |
| 九 协作 | 本文 §1/2；总体 §10；各服务 §9 | 同一实际模型/强度、分批、非原作者复核、原作者修订、公共结论持久化 |
| 十 验证 | validation V01–V12、差分方法、G0–G5 | 契约/语义/组合/多入口/并发/分布/LLM/成本全覆盖，真实写只规划 |
| 十一 产物 | 总体产物表；audit_artifacts.py | 所有指定路径、统一矩阵 11 列、九报告有 LLM 节、来源和 U |
| 十二 最终决策 | 总体 §2–9；最终交付说明 | 九域保真与难点、优先/有害近似、共享/独立、扩展/证明/规模/路线/成本/首批；主试点+LLM 对照 |

## 4. 文档检查边界

`audit_artifacts.py` 只读检查九报告章节、能力矩阵的 11 列与逐行一致性、已采集公共源码/任务配置 hash 和任务成员。它不证明来源解释正确、审查完成、真实兼容或训练迁移。后者需本轮人工/交叉证据审查及未来 validation 计划中的实验。

最终核验（2026-09-10）：九报告的非原作者审查及原作者修订/登记全部完成，上述问题均已闭环，原始需求逐项落点已由统筹复核。按最终作者报告重新汇总后，`audit_artifacts.py` 返回 pass：9 份同模板报告、127 行矩阵/11 列、source hash/任务成员、43 个本地链接及 Markdown 表格检查通过。仅本次 19 个产物的可识别凭据模式扫描无匹配。工作树变更范围仍为本次文档/只读扫描脚本与原有用户改动，没有进入 mock 实现。

残余 U 是报告中明确列出的运行版本、指定账号/后端行为、候选兼容长尾与实测经济性等，需要未来独立实验；它们不再是待做的文档审查。本结果不是运行保真、性能或迁移测试。
