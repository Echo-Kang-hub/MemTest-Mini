"""
agent_api/example_agent.py
--------------------------
MemTest-Mini 目标 Agent 接口规范 + 最小化 Stub 实现。

本文件有两个用途：
  1. 【接口规范文档】：展示目标 Agent 必须实现的三个标准 RESTful API，
     带有完整注释、请求/响应 Schema 和 OpenAPI 元数据。
     任何语言/框架实现的 Agent，只需对外暴露同样签名的接口即可接入 MemTest-Mini。

  2. 【可运行 Stub】：提供最小化的内存存储实现，用于调试 MemTest-Mini 框架本身。
     不包含真实的 LLM 或记忆算法，仅做回显/存储。

启动方式：
    pip install fastapi uvicorn
    python agent_api/example_agent.py

Swagger UI（启动后访问）：
    http://127.0.0.1:8000/docs

OpenAPI JSON Schema：
    http://127.0.0.1:8000/openapi.json
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求 / 响应 Schema 定义
# （与 memtest/models.py 中的定义保持结构一致，可直接复制到你的 Agent 项目）
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """POST /chat 请求体"""
    user_id: str = Field(
        ...,
        description="用户唯一标识符，用于隔离不同用户的独立记忆空间。"
                    "测试框架会为每个用例生成唯一 user_id。",
        examples=["user_001"],
    )
    message: str = Field(
        ...,
        description="用户输入的文本消息。",
        examples=["我对海鲜严重过敏。"],
    )


class ChatResponse(BaseModel):
    """POST /chat 响应体"""
    response: str = Field(
        ...,
        description="Agent 生成的文本回复。",
        examples=["好的，我已记录您对海鲜过敏的信息。"],
    )
    retrieved_memories: Optional[List[str]] = Field(
        default=None,
        description=(
            "【可选但推荐】Agent 在生成本次回复时从记忆库中检索到的相关记忆片段列表。\n"
            "提供此字段可帮助测试框架进行更细粒度的检索质量分析。\n"
            "若 Agent 不支持，可返回 null 或省略此字段。"
        ),
        examples=[["用户对海鲜过敏", "用户有过敏史"]],
    )


class MemoryResponse(BaseModel):
    """GET /memory/{user_id} 响应体"""
    memories: Any = Field(
        ...,
        description=(
            "当前用户的完整记忆库内容。\n"
            "格式灵活：可以是字符串列表、键值字典或嵌套结构，"
            "测试框架会将其序列化为字符串后进行关键词匹配。"
        ),
        examples=[
            ["用户对海鲜过敏", "用户有一只叫旺财的柯基"],
            {"allergy": "海鲜", "pet": "旺财（柯基）"},
        ],
    )


class ResetRequest(BaseModel):
    """POST /reset 请求体"""
    user_id: str = Field(
        ...,
        description="需要清空所有记忆和对话历史的用户标识符。",
        examples=["user_001"],
    )


class ResetResponse(BaseModel):
    """POST /reset 响应体"""
    status: str = Field(
        ...,
        description="操作状态，成功时必须为 'ok'，测试框架依赖此字段判断重置是否成功。",
        examples=["ok"],
    )
    message: Optional[str] = Field(
        default=None,
        description="可选的附加说明信息。",
        examples=["用户 user_001 的状态已重置"],
    )


# ---------------------------------------------------------------------------
# FastAPI 应用实例
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MemTest-Mini 目标 Agent 标准接口规范",
    description=(
        "## 接入 MemTest-Mini 的目标 Agent 必须实现以下三个接口\n\n"
        "本服务是一个最小化的 **Stub 实现**，用于调试 MemTest-Mini 框架本身。\n"
        "不包含真实的 LLM 调用或向量记忆逻辑，请替换为你自己的 Agent 实现。\n\n"
        "### 接口概览\n"
        "| 接口 | 方法 | 用途 |\n"
        "|------|------|------|\n"
        "| `/chat` | POST | 对话接口，接收消息并返回 Agent 回复 |\n"
        "| `/memory/{user_id}` | GET | 白盒读取记忆库（测试框架专用）|\n"
        "| `/reset` | POST | 清空用户状态，确保测试环境干净 |"
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# 最小化 Stub 存储（仅用于调试，请勿在生产环境使用）
# ---------------------------------------------------------------------------

# 内存中的简单 KV 存储：{user_id: [记忆条目, ...]}
_memory_store: Dict[str, List[str]] = {}


# ---------------------------------------------------------------------------
# 接口实现
# ---------------------------------------------------------------------------

@app.post(
    "/chat",
    response_model=ChatResponse,
    summary="对话接口",
    description=(
        "### 功能要求\n"
        "接收用户消息，Agent 内部需完成以下步骤（本 Stub 仅做简化模拟）：\n\n"
        "1. **记忆提取**：从本次消息中识别并存储关键信息（人名、偏好、过敏源等）\n"
        "2. **记忆检索**：从历史记忆中查找与本次查询相关的信息\n"
        "3. **回复生成**：基于检索到的记忆，用 LLM 生成上下文感知的回复\n"
        "4. **记忆更新**：检测到用户状态变更时，更新/覆盖旧记忆（不留冲突副本）\n\n"
        "> ⚠️ **Stub 说明**：本实现仅将消息原文存入列表并返回固定格式回复，"
        "不包含真实 LLM 逻辑。"
    ),
    tags=["Core API"],
)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    对话接口 — 真实 Agent 应在此实现完整的记忆增强对话逻辑。

    Stub 行为：将用户消息追加到记忆列表，返回简单确认回复。
    """
    user_id = req.user_id
    message = req.message

    # ── 初始化该用户的记忆存储 ──
    if user_id not in _memory_store:
        _memory_store[user_id] = []

    # ── [Stub] 直接将消息作为记忆存储（生产环境应使用 LLM 做实体/意图提取）──
    _memory_store[user_id].append(message)

    # ── [Stub] 构造简单回复，返回最近检索到的记忆 ──
    recent_memories = _memory_store[user_id][-3:]  # 返回最近 3 条
    stub_response = (
        f"[Stub] 已接收您的消息并记录。"
        f"当前记忆库共 {len(_memory_store[user_id])} 条记录。"
    )

    return ChatResponse(
        response=stub_response,
        retrieved_memories=recent_memories,
    )


@app.get(
    "/memory/{user_id}",
    response_model=MemoryResponse,
    summary="记忆探查接口（白盒测试专用）",
    description=(
        "### 用途\n"
        "直接读取并返回指定用户当前记忆库中的**全部内容**，供测试框架进行白盒验证。\n\n"
        "### 测试框架的使用场景\n"
        "- **记忆提取测试**：验证 Agent 是否成功将关键信息写入了记忆库\n"
        "- **记忆更新测试**：验证 Agent 是否正确覆盖了旧记忆（旧关键词不再出现）\n\n"
        "### 实现要求\n"
        "必须返回该用户当前**所有生效**的记忆内容，包括：\n"
        "- 已提取的结构化记忆（偏好、事实等）\n"
        "- 尚未被更新/覆盖的历史记忆\n\n"
        "> ⚠️ **安全提示**：此接口暴露了内部状态，"
        "生产部署时应添加身份鉴权保护，或仅在测试网络环境中开放。"
    ),
    tags=["Core API"],
)
async def get_memory(
    user_id: str = Path(..., description="需要查询记忆的用户标识符"),
) -> MemoryResponse:
    """
    记忆探查接口 — 白盒读取完整记忆库。

    Stub 行为：返回内存字典中该用户的记忆列表。
    """
    memories = _memory_store.get(user_id, [])
    return MemoryResponse(memories=memories)


@app.post(
    "/reset",
    response_model=ResetResponse,
    summary="环境重置接口",
    description=(
        "### 用途\n"
        "清空指定用户的所有对话历史和记忆数据，将其恢复到初始状态。\n\n"
        "### 调用时机\n"
        "**测试框架在每个测试用例开始之前都会调用此接口**，"
        "确保用例之间完全隔离，不会因为记忆污染而相互影响。\n\n"
        "### 实现要求（严格）\n"
        "必须清空该用户的**所有**数据，包括但不限于：\n"
        "- 对话历史（短期记忆/上下文窗口）\n"
        "- 长期记忆库（向量存储、键值存储等）\n"
        "- 摘要缓存、用户画像等派生数据\n\n"
        "> 成功重置后必须返回 `{\"status\": \"ok\"}`。"
    ),
    tags=["Core API"],
)
async def reset(req: ResetRequest) -> ResetResponse:
    """
    环境重置接口 — 清空指定用户的所有状态。

    Stub 行为：从内存字典中删除该用户的记忆条目。
    """
    user_id = req.user_id
    existed = user_id in _memory_store

    if existed:
        del _memory_store[user_id]

    return ResetResponse(
        status="ok",
        message=(
            f"用户 '{user_id}' 的对话历史和记忆已全部清空。"
            if existed
            else f"用户 '{user_id}' 不存在记录，无需清空。"
        ),
    )


# ---------------------------------------------------------------------------
# 健康检查（可选但推荐）
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary="健康检查",
    description="返回服务运行状态。测试框架在启动前可调用此接口确认 Agent 已就绪。",
    tags=["Utility"],
)
async def health_check():
    """健康检查接口，供测试框架确认 Agent 已启动并可响应。"""
    return JSONResponse({"status": "ok", "service": "MemTest-Mini Stub Agent"})


# ---------------------------------------------------------------------------
# 启动入口（直接运行此文件时）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print("=" * 55)
    print("  MemTest-Mini Stub Agent 已启动（调试模式）")
    print("=" * 55)
    print("  Swagger UI  : http://127.0.0.1:8000/docs")
    print("  OpenAPI JSON: http://127.0.0.1:8000/openapi.json")
    print("  健康检查    : http://127.0.0.1:8000/health")
    print("  按 Ctrl+C 停止服务")
    print("=" * 55)

    uvicorn.run(app, host="127.0.0.1", port=8000)
