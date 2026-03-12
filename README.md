# MemTest-Mini

> 轻量级、模块化的本地 Agent **记忆能力**测试框架

通过标准 HTTP 接口与你本地运行的 LLM Agent 交互，自动运行记忆提取、检索、更新三类测试，并生成带统计数据的测试报告。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动内置 Stub Agent（用于调试框架）

```bash
python agent_api/example_agent.py
# Swagger UI → http://127.0.0.1:8000/docs
```

### 3. 运行测试

```bash
# 精确匹配模式（无需 API Key），同时导出 Markdown 报告
python main.py --url http://localhost:8000 --dataset datasets/ \
               --report reports/report.md

# LLM Judge 模式（语义评估，需要 OpenAI API Key）
export OPENAI_API_KEY="sk-..."
python main.py --url http://localhost:8000 --dataset datasets/ \
               --eval llm_judge --report reports/report.md
```

> **⚠️ 本地 LLM 超时提示**：如果你的 Agent 使用了本地 LLM（响应较慢），
> 默认的 30s 超时会导致大量请求失败。建议加上以下参数：
> ```bash
> python main.py --url http://localhost:8000 --dataset datasets/ \
>                --timeout 120 --retries 1 --report reports/report.md
> ```

---

## 项目结构

```
MemTest-Mini/
├── memtest/                  # 框架核心包
│   ├── models.py             # 所有 Pydantic 数据模型（测试用例 Schema + API 模型）
│   ├── client.py             # AgentClient（HTTP 封装，含重试）
│   ├── evaluator.py          # 评估器（精确匹配 + LLM Judge）
│   ├── reporter.py           # 报告生成器（终端 + Markdown）
│   └── runner.py             # TestRunner（核心调度器）
├── agent_api/
│   └── example_agent.py      # FastAPI 接口规范 + 可运行 Stub 实现
├── datasets/
│   ├── extraction_tests.json # 记忆提取测试用例
│   ├── retrieval_tests.json  # 记忆检索测试用例
│   ├── update_tests.json     # 记忆更新/冲突解决测试用例
│   └── adapters/             # 外部数据集适配器
│       ├── base.py           # 适配器抽象基类
│       ├── longmemeval.py    # LongMemEval 数据集适配器
│       ├── locomo.py         # LoCoMo 数据集适配器
│       └── convert_cli.py    # 格式转换 CLI 工具
├── reports/                  # 测试报告输出目录（.gitignore 已忽略）
├── main.py                   # CLI 入口
├── requirements.txt
├── config.example.yaml       # 配置模板（复制为 config.yaml 使用）
└── .gitignore
```

---

## 接入外部数据集（LongMemEval / LoCoMo）

框架提供了格式转换 CLI 工具，可将主流记忆评测数据集转为 MemTest-Mini 格式后直接运行：

```bash
# 1. 下载数据集后，使用适配器转换
python datasets/adapters/convert_cli.py \
    --adapter longmemeval \
    --input   /path/to/longmemeval_data.jsonl \
    --output  datasets/longmemeval_retrieval.json \
    --max-cases 100          # 可选：只取前100条用于快速验证

python datasets/adapters/convert_cli.py \
    --adapter locomo \
    --input   /path/to/locomo.json \
    --output  datasets/locomo_retrieval.json \
    --locomo-qa-types single-hop multi-hop   # 可选：过滤 QA 类型

# 2. 直接用转换后的文件运行测试
python main.py --url http://localhost:8000 \
               --dataset datasets/longmemeval_retrieval.json \
               --timeout 120 --retries 1 \
               --report reports/longmemeval_report.md
```

| 适配器 | 数据集 | 获取地址 |
|--------|--------|----------|
| `longmemeval` | LongMemEval | https://github.com/xiaowu0162/LongMemEval |
| `locomo` | LoCoMo | https://github.com/snap-research/locomo |

---

## 接入你自己的 Agent

你的 Agent 需要实现以下三个 HTTP 接口（任意语言/框架均可）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/chat` | POST | 对话接口，处理消息并返回回复 |
| `/memory/{user_id}` | GET | 白盒读取记忆库（白盒测试专用）|
| `/reset` | POST | 清空用户状态，确保测试隔离 |

详细 Schema 请参考 [agent_api/example_agent.py](agent_api/example_agent.py)。

---

## 测试类型说明

| 类型 | 目的 | 评估方式 |
|------|------|----------|
| `extraction` | 验证 Agent 从对话中提取并存储关键信息的能力 | 读取 `GET /memory`，检查记忆库内容 |
| `retrieval` | 验证多轮干扰后能准确找回之前的记忆 | 检查 `POST /chat` 回复内容 |
| `update` | 验证状态变更时旧记忆被正确覆盖（不留冲突副本）| 回复内容 + 记忆库双重检查 |

---

## 评估方法

- **精确匹配（默认）**：关键词子串搜索，无需 API Key，速度极快。
- **LLM Judge**：调用 OpenAI 兼容 API 进行语义评估，可处理同义词、改写等场景。

```bash
# 使用自定义兼容 API（DeepSeek、Ollama 等）
python main.py --url http://localhost:8000 --dataset datasets/ \
               --eval llm_judge \
               --llm-base-url https://api.deepseek.com/v1 \
               --llm-model deepseek-chat \
               --report reports/report.md
```

---

## 关于线上平台化

当前的架构设计已经为线上扩展做好了准备：

- **调度层**：`TestRunner` 是无状态的，天然适合包装成 `Celery` 异步任务
- **接口层**：`AgentClient` 目前调用本地 Agent，将 URL 注册化后即可支持多用户提交
- **报告层**：`Reporter` 可输出 JSON，交由前端（React/Vue）渲染为可视化仪表盘
- **数据层**：测试用例 JSON 文件可存入数据库，支持数据集管理、检索与复用

典型扩展架构：`FastAPI（Web API）+ Celery + Redis（任务队列）+ PostgreSQL（测试记录）+ React（前端）`

---

## 开源协议

MIT License
