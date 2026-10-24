# 单词书优先的每日课程设计

## 目标

Sabrina 反馈现有 ECDICT 词库（A1–B2，按频率分级）偏难。改为**以「10天单词书」tab 引用那本扫描词书为主词源**，让每日课程与她在词书里的学习内容对齐，两个 tab 形成同一条学习主线。

## 现状

- 主 tab（每日课程）选词来自静态 `content/vocabulary-*.json`（ECDICT，4000 词），按频率优先级 + 10 词窗口抽选。
- 「10天单词书」tab 的词表来自 `~/Library/Application Support/SabrinaEnglish/wordbook/data.json`：10 天、1969 个词条、含 93 个短语，每条自带中文释义（`{"w":"menu","senses":[["n.","菜单"]],"topic":"menu","page":12}`）。
- 该数据**不在 git**，且 `/api/wordbook/data` 需要登录才返回。

## 硬约束

1. **词书内容不得进入 `content/` 或 git**。后端注释明确：`The wordbook is a scanned book: it lives in the data directory (never in git)`。因此不能把词书生成为新的内容分片。
2. **词书结构由后端校验**：`{"entries": {"<day>:<word>": {"level": 0-3, "at": "<iso>"}}}`，`level` 为 `NEW=0 / UNKNOWN=1 / FUZZY=2 / KNOWN=3`，最多 10000 条，key 长度 ≤ 120。
3. 主 tab 的静态内容加载、manifest 哈希校验、离线可用性不得退化。

## 设计

### 选词池：两级，运行时合并

```
优先级 1：单词书 1969 词（按 Day 1→10、书内顺序）
优先级 2：ECDICT 4000 词（按现有频率优先级 + 窗口）
```

- 主 tab 登录后请求 `/api/wordbook/data`，把词条并入选词池，**排在 ECDICT 之前**。
- 未登录或请求失败：静默回退为纯 ECDICT，主 tab 照常可用。
- 这样词书内容始终只经认证接口下发，不落进 git。

### 词条映射

| 字段 | 来源 |
|---|---|
| `word` | 词书 `w` |
| `translation` | 词书 `senses` 拼接（书上的释义，更贴合课程） |
| `phonetic` | ECDICT 命中则用，否则留空（**不编造**） |
| `example` | 沿用现有模板句 |
| `level` | 词书 `Day N` 对应的等级标签 |
| `topic` | 词书 `topic` |
| `contentId` | `wb:<day>:<w>`，与 ECDICT 的 `v1:*` 天然隔离 |

覆盖率实测：ECDICT 命中 1940/1969（99%），有音标 1893/1969（96%）。未命中的 29 条全是多词短语（`main dish`、`shaved ice`、`hot air balloon`），音标留空。

### 双向进度同步

用户要求两个 tab 进度完全共享。

- **词书 → 每日课程**：`level ∈ {FUZZY, KNOWN}` 的词不再进入每日候选（视为已学）。
- **每日课程 → 词书**：在每日课程里学完一个词书词条，写入 `entries["<day>:<w>"] = { level: NEW→FUZZY, at: now }`，并触发已有的 `scheduleProfileSync()`，与词书 tab 的写入路径一致。

> 语义说明：每日课程只把词提升到 `FUZZY`（"见过、需巩固"），把它练到 `KNOWN` 仍由词书的测验/拼写模块负责。这样两边不互相覆盖，也不会把"只是看过一遍"误判为"已掌握"。若希望每日课程直接记 `KNOWN`，改一行即可。

### 与现有窗口/优先级的关系

词书内部按书的 Day 顺序走（用户已确认），因此词书部分**不使用频率窗口随机**；现有 `PRIORITY_WINDOW` 窗口逻辑只作用于 ECDICT 兜底段。这样既保留"高频先学"的设计，又尊重教材编排。

### 缓存与一致性

- 词书数据在会话建立后加载一次，按 `contentVersion` 记忆；`scheduleProfileSync` 的既有流程负责状态持久化。
- 词书状态与主 tab 状态同在 profile `state` 里同步，冲突由既有的 `state_version` 机制处理。
- 词书请求失败不得阻塞主 tab：`loadContentLibrary` 的主流程在词书失败时仍完成。

## 测试计划

单元（node）：
- 词书条目并入后排在 ECDICT 之前；
- `WB_KNOWN`（FUZZY/KNOWN）词被排除；
- 无词书数据时行为与当前完全一致（回归）；
- 多词短语（含空格）能正确生成卡片 id；
- 重复词（词书与 ECDICT 都有）只出一个，且用词书释义。

集成：
- 主 tab 在登录后能拉到词书词并优先展示；
- 每日课程里学词后，词书 `entries` 增加对应条目且 `level=FUZZY`；
- 词书里标 KNOWN 的词不再出现在每日课程；
- 全量 `unittest discover` + `validate_content.py` + 烟测保持通过。

## 回滚

改动集中在 `assets/content-library.js` 与 `index.html`；词书不作为内容分片发布，因此回滚只需 revert 这两个文件，`content/` 与 manifest 不受影响。已写入的词书 `entries` 可与旧版共存（旧版不读这些 key）。
