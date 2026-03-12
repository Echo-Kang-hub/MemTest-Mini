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
# 精确匹配模式（无需 API Key）
python main.py --url http://localhost:8000 --dataset datasets/

# LLM Judge 模式（语义评估，需要 OpenAI API Key）
export OPENAI_API_KEY="sk-..."
python main.py --url http://localhost:8000 --dataset datasets/ \
               --eval llm_judge --report reports/report.md
```

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
│   └── update_tests.json     # 记忆更新/冲突解决测试用例
├── main.py                   # CLI 入口
├── requirements.txt
├── config.example.yaml       # 配置模板（复制为 config.yaml 使用）
└── .gitignore
```

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
               --llm-model deepseek-chat
```

---

## 开源协议

MIT License
