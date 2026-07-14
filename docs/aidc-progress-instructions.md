# AIDCProgressExpert Instructions 设计

本文解释 `src/tsgo/aidc_progress/instructions.py` 的约束和验收逻辑。运行时以代码中的 `AIDC_PROGRESS_EXPERT_INSTRUCTIONS` 为准。

## 1. Instructions 的目标

Agent 的目标不是“搜几篇相关新闻”，而是回答三个可审计的问题：

1. 这个名称究竟对应哪个地块、申请主体、项目代号和许可集合？
2. 项目已经完成的最强政府/公用事业里程碑是什么？
3. 截止指定日期，最新改变项目状态的已核实事件是什么？

## 2. 为什么身份发现必须排在进展判断之前

同一个项目可能同时出现为：

```text
AWS Stone Ridge
Reeds Farm Lane
某个 Project Code
某个 Owner LLC
某个 LandMARC case number
某个 Parcel/PIN
某个 building permit
某个 substation/transmission project
```

输入中的 `AWS` 只是初始假设。除非政府文件、产权记录、开发协议、公司正式披露或多项可靠证据确认，否则不能把匿名地块或 `large-load customer` 直接归属于 AWS。

## 3. 强制检索面

### 3.1 规划与土地用途

必须覆盖：

```text
rezoning / zoning map amendment
special exception / SPEX / SUP / CUP
comprehensive plan amendment
site plan
staff report
proffer
public hearing
agenda packet / minutes / action report
resolution / ordinance
deferral / withdrawal / amendment / appeal
```

### 3.2 物理建设

必须区分：

```text
entitlement approved
site plan approved
grading / land disturbance
foundation / shell / building permit
inspection activity
temporary CO
final CO
```

判断规则：

- `rezoning approved`：只代表土地用途获准；
- `site plan approved`：不能单独证明工地已开工；
- `grading/land-disturbance permit`：强场地施工信号；
- `foundation/shell/building permit + inspection`：强垂直施工信号；
- `temporary/final CO`：只证明该证书覆盖的楼栋/阶段接近或已可使用。

### 3.3 环境和湿地

必须覆盖：

```text
air permit / amendment
generator / gas engine / turbine
construction deadline
stormwater / NPDES
water withdrawal / discharge
Section 404 / wetland / stream / mitigation
```

空气许可可以披露设备数量和容量，但不能单独证明设备已经安装或数据中心已投产。

### 3.4 电力与输电

必须覆盖：

```text
SCC/PUC docket
CPCN / certificate
transmission route
substation / switching station
large-load service
special contract / rate schedule
utility construction notice
in-service date
```

匿名负荷只能在地理、时间、规模和相关基础设施共同吻合时作为推断，并必须设置 `is_inference=true`。

### 3.5 配套、产权、激励、诉讼和新闻

必须继续检查：

- 水、再生水、污水和泵站；
- 道路扩建、出入口和封路；
- GIS、Assessor、Recorder、deed、parcel split/assembly；
- 税收优惠、PILOT、enterprise zone、development agreement；
- lawsuit、appeal、injunction、remand、stop-work；
- 当地报纸、电视、hyperlocal 和 business journal。

新闻主要负责发现线索、解释争议和补充现场变化；项目阶段优先由一手记录确认。

## 4. 来源等级

| 等级 | 定义 | 示例 |
|---|---|---|
| A | 已生效的一手记录 | signed resolution、issued permit、inspection/CO、court order、recorded deed |
| B | 正式但可能尚未生效的记录 | application、staff report、draft permit、agenda packet、utility filing、public notice |
| C | 可靠当地/区域新闻 | 具名官员、引用文件、现场照片、明确事件日期 |
| D | 企业或行业信息 | company release、contractor、vendor、job posting、trade report |
| E | 弱线索 | community post、匿名说法、无法访问的 snippet |

发生冲突时，Agent 不能静默选择某一个数字或日期；必须写入 `source_conflicts`。

## 5. 日期规则

每个来源尽量分别记录：

```text
event_date       实际会议、签发、交易、开工或投运日期
publication_date 页面、新闻或 public notice 发布日期
retrieved_date   Agent 检索日期
```

`latest_verified_event` 是最近一个改变项目状态的非推断事件，不是发布时间最晚的新闻。

## 6. 当前阶段的保守映射

```text
unknown
rumor_or_site_selection
land_acquisition
planning_application
land_use_approved
site_development
vertical_construction
power_infrastructure
commissioning
partially_operational
operational
expansion
stalled_or_cancelled
```

阶段由“最强已核实里程碑”决定。若楼体已建但供电项目仍在建设，报告可以把园区状态写为 `power_infrastructure` 或在 construction/power 两个 StatusSection 中分别说明，不能简单宣称 operational。

## 7. 输出验收

返回前必须检查：

- 行政辖区已确认或明确标记未知；
- 输入名称、别名和地点线索全部搜索；
- 新发现的 LLC、地址、Parcel、case、permit、substation 被再次搜索；
- 至少尝试 planning/agenda、permit、environment、power、property/GIS、local-news；
- 高置信度状态带 URL；
- 时间线按事件日期排序；
- current stage 不超过证据；
- 事实和推断分开；
- Portal 不可访问和仍未知的问题进入 `research_gaps`；
- 不存在无来源的“已开工、已通电、已投产”结论。
