"""
memtest/models.py
-----------------
定义框架内所有数据模型，包括：
  - 测试用例（TestCase）的 Schema，对应 datasets/ 下的 JSON 数据格式
  - Agent API 的请求/响应模型（供 Client 使用）
  - 测试结果模型（供 Runner -> Reporter 传递数据）
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 通用枚举
# ---------------------------------------------------------------------------

class TestType(str, Enum):
    """测试类型枚举，与 JSON 数据集中 "type" 字段对应。"""
    EXTRACTION = "extraction"
    RETRIEVAL = "retrieval"
    UPDATE = "update"


class EvalMethod(str, Enum):
    """评估策略枚举，在 Runner 初始化时指定。"""
    EXACT = "exact"          # 精确关键词匹配（无需 API Key，速度快）
    LLM_JUDGE = "llm_judge"  # LLM 作为裁判（更灵活，需要 OpenAI API Key）


class ResultStatus(str, Enum):
    """单个测试用例/子检查的评判结果。"""
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"  # 执行期间发生网络/解析异常


# ---------------------------------------------------------------------------
# 测试用例 Schema（对应 datasets/*.json 文件格式）
# ---------------------------------------------------------------------------

class Turn(BaseModel):
    """单轮对话消息。"""
    role: Literal["user", "assistant"] = Field(
        ..., description="消息角色，通常为 'user'"
    )
    content: str = Field(..., description="消息文本内容")


class ExtractionTestCase(BaseModel):
    """
    记忆提取测试用例。

    目的：验证 Agent 能否从包含噪音的对话中提取关键信息并写入记忆库。
    评估方式：发完所有 turns 后调用 GET /memory/{user_id}，
              检查记忆库内容是否包含 expected_memory_contains 中的关键词。
    """
    test_id: str
    type: Literal["extraction"]
    description: Optional[str] = Field(None, description="用例描述，便于报告阅读")
    turns: List[Turn] = Field(
        ..., description="按顺序发送给 Agent 的对话轮次"
    )
    expected_memory_contains: List[str] = Field(
        ..., description="期望在记忆库中出现的关键词/短语列表"
    )
    require_all: bool = Field(
        True, description="True=所有关键词都必须出现；False=至少出现一个即可"
    )


class RetrievalTestCase(BaseModel):
    """
    记忆检索测试用例。

    目的：验证 Agent 在多轮对话后，能否准确找回之前存储的记忆来回答问题。
    评估方式：先发送 setup 消息建立记忆，再发送 query，
              检查 POST /chat 的回复是否包含 expected_response_contains。
    """
    test_id: str
    type: Literal["retrieval"]
    description: Optional[str] = None
    setup: List[Turn] = Field(
        ..., description="建立记忆的前置对话（不含最终查询）"
    )
    query: str = Field(..., description="向 Agent 发出的最终测试问题")
    expected_response_contains: List[str] = Field(
        ..., description="期望在 Agent 回复中出现的关键词/短语列表"
    )
    require_all: bool = Field(
        False, description="True=所有关键词都必须出现；False=至少出现一个即可"
    )


class UpdateTestCase(BaseModel):
    """
    记忆更新与融合测试用例。

    目的：验证面对状态变更时，Agent 能在回复中体现最新状态，同时在记忆库中
          以融合方式保留历史上下文（如"曾经是程序员，现在是摄影师"），
          而不是简单地删除旧记录。
    评估方式（双重检查）：
      1. 检查最终回复包含最新状态（expected_response_contains）
      2. 检查记忆库中已包含更新后的当前状态（expected_memory_contains）
    """
    test_id: str
    type: Literal["update"]
    description: Optional[str] = None
    turns: List[Turn] = Field(
        ..., description="包含旧信息 -> 新信息变更的完整对话序列"
    )
    query: str = Field(..., description="在所有对话结束后发出的查询问题")
    expected_response_contains: List[str] = Field(
        ..., description="期望在最终回复中出现的关键词（应反映最新状态）"
    )
    expected_memory_contains: Optional[List[str]] = Field(
        None,
        description="期望在记忆库中出现的关键词（更新后的当前状态），验证记忆融合是否成功"
    )
    require_all_contains: bool = Field(
        False, description="回复检查：True=所有词都必须出现；False=至少一个"
    )
    require_all_memory: bool = Field(
        True, description="记忆包含检查：True=所有词都必须出现；False=至少一个"
    )


# 联合类型——用于统一处理所有测试用例
AnyTestCase = Union[ExtractionTestCase, RetrievalTestCase, UpdateTestCase]


# ---------------------------------------------------------------------------
# Agent API 请求/响应模型
# （目标 Agent 需实现相同签名的接口，参见 agent_api/example_agent.py）
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """POST /chat 请求体"""
    user_id: str = Field(
        ..., description="用户标识符，用于隔离多用户记忆空间"
    )
    message: str = Field(..., description="用户输入的消息文本")


class ChatResponse(BaseModel):
    """POST /chat 响应体"""
    response: str = Field(..., description="Agent 返回的文本回复")
    retrieved_memories: Optional[List[str]] = Field(
        None,
        description="【可选】Agent 在生成本次回复时检索到的相关记忆片段"
    )


class MemoryResponse(BaseModel):
    """GET /memory/{user_id} 响应体"""
    memories: Any = Field(
        ...,
        description="当前生效的记忆条目（字符串列表、字典等格式均可接受）"
    )


class ResetRequest(BaseModel):
    """POST /reset 请求体"""
    user_id: str = Field(
        ..., description="需要清空记忆和对话历史的用户标识符"
    )


class ResetResponse(BaseModel):
    """POST /reset 响应体"""
    status: str = Field(..., description="操作状态，成功时为 'ok'")
    message: Optional[str] = Field(None, description="可选的附加说明")


# ---------------------------------------------------------------------------
# 测试结果模型（内部使用，由 Runner 填充，由 Reporter 消费）
# ---------------------------------------------------------------------------

class SubCheckResult(BaseModel):
    """单项子检查结果（如"记忆包含检查"、"回复内容检查"）"""
    check_name: str
    status: ResultStatus
    reason: str
    score: Optional[float] = Field(default=None, description="LLM Judge 的置信度分数 0-1")


class TestCaseResult(BaseModel):
    """单个测试用例的完整执行结果"""
    test_id: str
    test_type: str
    description: Optional[str] = None
    overall_status: ResultStatus
    sub_checks: List[SubCheckResult] = Field(default_factory=list)
    duration_seconds: float = 0.0
    # 记录所有对话轮次 Agent 的原始回复（便于调试）
    agent_responses: List[str] = Field(default_factory=list)
    # 执行期间发生异常时的错误信息
    error_message: Optional[str] = None
