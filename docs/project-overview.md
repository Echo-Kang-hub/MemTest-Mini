# MemTest-Mini 项目说明文档

> 轻量级、可本地运行的 **AI Agent 记忆能力测试框架**

---

## 目录

1. [项目定位与背景](#1-项目定位与背景)
2. [项目目录结构](#2-项目目录结构)
3. [核心模块详解](#3-核心模块详解)
   - [main.py — 命令行入口](#31-mainpy--命令行入口)
   - [memtest/models.py — 数据模型](#32-memtestmodelspy--数据模型)
   - [memtest/client.py — HTTP 客户端](#33-memtestclientpy--http-客户端)
   - [memtest/runner.py — 测试运行器](#34-memtestrunnerpy--测试运行器)
   - [memtest/evaluator.py — 评估器](#35-memtestevalpyy--评估器)
   - [memtest/reporter.py — 报告生成器](#36-memtestreporterpy--报告生成器)
   - [agent_api/example_agent.py — 示例 Agent](#37-agent_apiexample_agentpy--示例-agent)
4. [测试类型与原理](#4-测试类型与原理)
   - [Extraction（记忆提取测试）](#41-extraction记忆提取测试)
   - [Retrieval（记忆检索测试）](#42-retrieval记忆检索测试)
   - [Update（记忆更新测试）](#43-update记忆更新测试)
5. [评估方法](#5-评估方法)
   - [精确匹配（exact）](#51-精确匹配exact)
   - [LLM 裁判（llm_judge）](#52-llm-裁判llm_judge)
6. [Agent 接入规范](#6-agent-接入规范)
7. [配置文件说明](#7-配置文件说明)
8. [完整测试流程示意](#8-完整测试流程示意)

---

## 1. 项目定位与背景

现代 AI Agent 通常具备"记忆"能力——能在多轮对话中记住用户的个人信息、偏好、历史状态，并在后续对话中准确调用。MemTest-Mini 是专门用于**测试和量化这一能力**的框架，它：

- 对被测 Agent **无技术栈限制**，只需要暴露三个标准 HTTP 接口。
- 提供三种维度的记忆能力测试：**提取、检索、更新**。
- 支持两种评估策略：无 API Key 的**精确匹配**，以及语义理解更强的 **LLM 裁判**。
- 测试结果可在终端实时查看，也可导出为 Markdown 报告，便于集成到 CI/CD 流程。

---

## 2. 项目目录结构

```
MemTest-Mini/
│
├── main.py                      # 命令行入口（参数解析 + 主流程）
├── config.yaml                  # 配置文件（API Key、端点、评估方法等）
├── config.example.yaml          # 配置模板（可安全提交到 Git）
├── requirements.txt             # Python 依赖列表
├── README.md                    # 快速上手说明
│
├── memtest/                     # 框架核心包
│   ├── __init__.py              # 公开导出 TestRunner, load_dataset
│   ├── models.py                # 全部数据模型（测试用例、API Schema、结果）
│   ├── client.py                # AgentClient：HTTP 通信 + 重试
│   ├── runner.py                # TestRunner：主调度器
│   ├── evaluator.py             # ExactMatchEvaluator + LLMJudgeEvaluator
│   └── reporter.py              # TerminalReporter + MarkdownReporter
│
├── datasets/                    # 内置测试数据集
│   ├── extraction_tests.json    # 记忆提取测试用例
│   ├── retrieval_tests.json     # 记忆检索测试用例
│   ├── update_tests.json        # 记忆更新测试用例
│   └── adapters/                # 第三方数据集适配器（LoCoMo、LongMemEval 等）
│       ├── base.py
│       ├── locomo.py
│       ├── longmemeval.py
│       └── convert_cli.py
│
├── agent_api/                   # Agent 接口规范与 Stub 实现
│   ├── __init__.py
│   └── example_agent.py        # 可运行的最小化 Stub（开发调试用）
│
└── docs/                        # 项目文档（本文件所在目录）
    └── project-overview.md
```

---

## 3. 核心模块详解

### 3.1 `main.py` — 命令行入口

整个框架的启动脚本，负责：

1. **解析命令行参数**：`--url`（Agent 地址）、`--dataset`（数据集路径或目录）、`--eval`（评估方法）、`--report`（报告输出路径）等。
2. **读取 `config.yaml`**：自动加载同目录的 `config.yaml`，作为参数的低优先级默认值。
3. **优先级链**：命令行参数 > 环境变量 `OPENAI_API_KEY` > `config.yaml`。
4. **驱动 `TestRunner`** 完成测试并生成报告。

典型命令：

```bash
# 精确匹配模式（无需 API Key）
python main.py --url http://localhost:8000 --dataset datasets/

# LLM 裁判模式（API Key 来自 config.yaml）
python main.py --url http://localhost:8000 --dataset datasets/ \
               --eval llm_judge --report reports/report.md
```

---

### 3.2 `memtest/models.py` — 数据模型

定义框架内所有数据结构（基于 **Pydantic**）：

| 模型类 | 用途 |
|---|---|
| `ExtractionTestCase` | 记忆提取测试用例 Schema |
| `RetrievalTestCase` | 记忆检索测试用例 Schema |
| `UpdateTestCase` | 记忆更新测试用例 Schema |
| `ChatRequest / ChatResponse` | `/chat` 接口请求/响应 |
| `MemoryResponse` | `/memory/{user_id}` 接口响应 |
| `ResetRequest / ResetResponse` | `/reset` 接口请求/响应 |
| `SubCheckResult` | 单项子检查结果（含 status、reason、score） |
| `TestCaseResult` | 单个测试用例的完整结果 |
| `EvalMethod` | 评估方法枚举（`EXACT` / `LLM_JUDGE`） |
| `ResultStatus` | 结果枚举（`PASS` / `FAIL` / `ERROR`） |

`UpdateTestCase` 的关键字段：

| 字段 | 说明 |
|---|---|
| `expected_response_contains` | 回复中应包含的新状态关键词 |
| `expected_memory_contains` | 记忆库中应包含的更新后状态关键词（验证融合成功） |
| `require_all_contains` | 回复检查：是否要求所有词都出现 |
| `require_all_memory` | 记忆检查：是否要求所有词都出现 |

---

### 3.3 `memtest/client.py` — HTTP 客户端

`AgentClient` 封装了与目标 Agent 的全部 HTTP 通信：

- **`chat(user_id, message)`** → `POST /chat`，返回 Agent 的文本回复
- **`get_memory(user_id)`** → `GET /memory/{user_id}`，返回当前记忆快照
- **`reset(user_id)`** → `POST /reset`，清空用户的记忆和对话历史

**重试策略**：对网络连接失败和超时进行指数退避重试（最多 `max_retries` 次），HTTP 4xx/5xx 不重试（避免重复副作用）。

---

### 3.4 `memtest/runner.py` — 测试运行器

`TestRunner` 是框架的**核心调度器**，工作流程如下：

```
load_dataset(json_file)
    │
    ▼  对每个 TestCase：
┌─────────────────────────────┐
│ 1. 生成唯一 user_id          │
│ 2. POST /reset  清空环境     │
│ 3. 发送 setup/turns 消息     │
│ 4. 发送 query  获取最终回复  │
│ 5. Evaluator 评估结果        │
│ 6. （按需）GET /memory 白盒  │
└─────────────────────────────┘
    │
    ▼
TestCaseResult 列表
    │
    ▼
Reporter 输出
```

**隔离保证**：每个测试用例使用 `memtest_{test_id}_{uuid}` 格式的独立 `user_id`，配合 `/reset` 确保测试间完全无状态污染。

---

### 3.5 `memtest/evaluator.py` — 评估器

提供两种相互独立的评估策略：

#### `ExactMatchEvaluator`（精确匹配）

- `check_contains(content, expected_items)` — 检查内容中是否包含期望关键词
- `check_excludes(content, excluded_items)` — 检查内容中是否已清除旧记忆词

原理：将 Agent 回复或记忆库序列化为小写字符串，做子串搜索。速度极快，零成本。

#### `LLMJudgeEvaluator`（LLM 裁判）

- `judge(question, agent_response, expected_keywords)` — 调用 OpenAI 兼容 API，由大模型判断语义是否正确

使用以下 Prompt 结构让 LLM 输出结构化 JSON 判断：

```
【测试问题】
【Agent 的回复】
【评测标准（期望关键信息）】
→ 输出 {"pass": bool, "score": 0.0-1.0, "reasoning": "..."}
```

优点：能处理同义词、改写、多语言（如"摄影师" ↔ "photographer"）等精确匹配无法覆盖的语义等价场景。

---

### 3.6 `memtest/reporter.py` — 报告生成器

**`TerminalReporter`**：在终端打印彩色统计摘要（依赖 `rich`，未安装时降级为纯文本）。

**`MarkdownReporter`**：将结果导出为结构化 `.md` 文件，包含：
- 测试时间和总通过率
- 逐用例的 PASS / FAIL / ERROR 状态
- 每个子检查的详细原因
- LLM Judge 置信度分数（如适用）

---

### 3.7 `agent_api/example_agent.py` — 示例 Agent

基于 **FastAPI** 实现的可运行 Stub，有两个用途：

1. **接口规范文档**：展示目标 Agent 必须实现的三个接口（含 OpenAPI 注解）。
2. **调试 Stub**：使用内存字典模拟记忆存储，可在真实 Agent 就绪前用于验证测试框架本身。

启动方式：
```bash
pip install fastapi uvicorn
python agent_api/example_agent.py
# → http://127.0.0.1:8000/docs 查看 Swagger UI
```

---

## 4. 测试类型与原理

### 4.1 Extraction（记忆提取测试）

**目的**：验证 Agent 能否从嘈杂对话中识别并存储关键个人信息。

**流程**：

```
发送 turns（含目标信息的对话）
    ↓
GET /memory/{user_id}  获取记忆快照
    ↓
检查快照是否包含 expected_memory_contains 中的关键词
```

**典型场景**：用户在闲聊中顺带提到"我对海鲜严重过敏"，系统应识别并存储过敏信息，而不是将其当作无关信息忽略。

**示例用例**（`extraction_tests.json`）：
```json
{
  "test_id": "ext_001",
  "type": "extraction",
  "turns": [{"role": "user", "content": "今天天气真不错...对了，我对海鲜严重过敏，上次吃虾差点送医院。"}],
  "expected_memory_contains": ["海鲜过敏"],
  "require_all": true
}
```

---

### 4.2 Retrieval（记忆检索测试）

**目的**：验证 Agent 在多轮无关对话后，能否准确检索历史记录来回答具体问题。

**流程**：

```
发送 setup 消息（建立记忆 + 干扰性无关对话）
    ↓
发送 query（测试问题）
    ↓
检查 POST /chat 回复是否包含 expected_response_contains
```

**典型场景**：用户先说"我养了一只叫旺财的柯基"，几轮无关对话后问"我的狗叫什么名字？"，Agent 应正确回答"旺财"。

**示例用例**（`retrieval_tests.json`）：
```json
{
  "test_id": "ret_001",
  "type": "retrieval",
  "setup": [
    {"role": "user", "content": "我养了一只叫'旺财'的柯基，它今年3岁了，特别活泼。"},
    {"role": "user", "content": "今天北京天气真好..."},
    {"role": "user", "content": "你觉得 Python 和 Go 哪个更适合做后端开发？"}
  ],
  "query": "我的狗叫什么名字？",
  "expected_response_contains": ["旺财"],
  "require_all": true
}
```

---

### 4.3 Update（记忆更新与融合测试）

**目的**：验证 Agent 在状态变更时是否能**正确融合记忆**——在回复中体现最新状态，同时在记忆库中以包含历史上下文的方式保留变更轨迹。

正确的记忆系统不应简单地删除旧记录，而应类似于"曾经是程序员，后来转行做了摄影师"这样的融合式记忆，既保留历史，又能准确回答当前状态。

**流程**：

```
发送 turns（先建立旧信息，再告知新信息）
    ↓
发送 query
    ↓
双重检查：
  ① POST /chat 回复包含新信息（expected_response_contains）
  ② GET  /memory 快照已包含更新后的当前状态（expected_memory_contains）
```

**典型场景**：用户先说"我是程序员"，后来说"我转行做摄影师了"，Agent 回复当前职业时应正确说出"摄影师"，记忆库中也应融合这一最新状态（允许保留"曾经是程序员"的历史上下文）。

**示例用例**（`update_tests.json`）：
```json
{
  "test_id": "upd_001",
  "type": "update",
  "turns": [
    {"role": "user", "content": "我现在的职业是程序员，在一家互联网大厂工作..."},
    {"role": "user", "content": "我上个月辞职了，现在转行做独立摄影师了..."}
  ],
  "query": "我现在是做什么工作的？",
  "expected_response_contains": ["摄影师"],
  "expected_memory_contains": ["摄影师"],
  "require_all_contains": true,
  "require_all_memory": true
}
```

---

## 5. 评估方法

### 5.1 精确匹配（`exact`）

| 属性 | 值 |
|---|---|
| 是否需要 API Key | 否 |
| 速度 | 极快 |
| 适用场景 | 关键词明确、不需要语义理解 |
| 缺点 | 无法识别同义词和改写 |

**工作原理**：将 Agent 回复或记忆快照序列化为小写字符串，对每个 `expected_items` 中的关键词做 `in` 子串查找。`require_all=True` 时要求所有关键词均存在，`require_all=False` 时只需出现至少一个。

### 5.2 LLM 裁判（`llm_judge`）

| 属性 | 值 |
|---|---|
| 是否需要 API Key | 是（OpenAI 兼容 API） |
| 速度 | 较慢（一次 LLM 调用/检查） |
| 适用场景 | 需要语义理解、多语言等价、改写识别 |
| 缺点 | 有 API 成本，性能依赖模型质量 |

**评分结构**：LLM 输出 `{"pass": bool, "score": float, "reasoning": str}`，`score` 为 0-1 的置信度，`reasoning` 为简短中文判断理由。

**API Key 优先级**：命令行 `--llm-api-key` > 环境变量 `OPENAI_API_KEY` > `config.yaml` 中的 `llm_judge.api_key`。

---

## 6. Agent 接入规范

任何被测 Agent 只需实现以下三个 HTTP 接口：

### `POST /chat`

```json
// 请求
{"user_id": "memtest_xxx", "message": "我对海鲜过敏"}

// 响应
{"response": "好的，我已记录您对海鲜过敏的信息。", "retrieved_memories": ["..."]}
```

### `GET /memory/{user_id}`

```json
// 响应
{"memories": ["海鲜过敏", "住在北京"]}
// memories 字段格式灵活，字符串列表或字典均可接受
```

### `POST /reset`

```json
// 请求
{"user_id": "memtest_xxx"}

// 响应
{"status": "ok", "message": "已清空用户记忆"}
```

> `/memory` 和 `/reset` 接口是**白盒测试接口**，专供测试框架使用，实际生产环境可设置访问控制。

---

## 7. 配置文件说明

`config.yaml` 中各字段的含义：

```yaml
agent:
  url: "http://localhost:8000"   # 被测 Agent 的根地址
  timeout: 30                    # HTTP 请求超时（秒）
  max_retries: 3                 # 网络错误最大重试次数

eval:
  method: "llm_judge"            # 评估方法: exact 或 llm_judge

llm_judge:
  model: "gpt-4o-mini"           # 评测模型（支持任何 OpenAI 兼容模型）
  api_key: "sk-..."              # API Key（建议改用环境变量，避免泄露）
  base_url: "https://..."        # 自定义端点（留空使用 OpenAI 官方地址）

report:
  output: "reports/report.md"    # 报告输出路径（留空则仅输出到终端）
```

---

## 8. 完整测试流程示意

```
用户运行命令
    │
    ▼
main.py
  ├─ 读取 config.yaml + 命令行参数
  ├─ 初始化 TestRunner
  │     ├─ AgentClient（HTTP 通信层）
  │     └─ Evaluator（ExactMatch 或 LLMJudge）
  │
  └─ 遍历所有数据集 JSON 文件
        │
        ▼ 对每个 TestCase：
      runner.run_file(json)
        │
        ├─ POST /reset       ← 清空上一个用例的残留状态
        ├─ POST /chat × N    ← 按顺序发送 setup/turns 消息
        ├─ POST /chat        ← 发送 query，获取最终回复
        ├─ GET  /memory      ← （extraction/update）获取记忆快照
        └─ Evaluator.eval()  ← 对回复执行包含检查；对记忆执行包含检查（融合验证）
              │
              ▼
        SubCheckResult[]
              │
              ▼
        TestCaseResult（overall: PASS/FAIL/ERROR）
              │
              ▼
  TerminalReporter → 彩色终端输出
  MarkdownReporter → reports/report.md（如配置了路径）
```
