"""
memtest/client.py
-----------------
AgentClient：封装对目标 Agent HTTP API 的所有请求。

特性：
  - 超时控制（可配置）
  - 指数退避重试（仅对网络级错误重试，HTTP 4xx/5xx 不重试）
  - 统一的自定义异常体系，方便上层捕获
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from .models import ChatResponse, MemoryResponse, ResetResponse


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class AgentClientError(Exception):
    """AgentClient 专用基础异常"""


class AgentConnectionError(AgentClientError):
    """网络连接失败或请求超时"""


class AgentAPIError(AgentClientError):
    """Agent 返回非 2xx HTTP 状态码"""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {detail}")


# ---------------------------------------------------------------------------
# 客户端主类
# ---------------------------------------------------------------------------

class AgentClient:
    """
    与目标 Agent 进行 HTTP 通信的客户端。

    目标 Agent 必须实现以下三个接口（参见 agent_api/example_agent.py）：
      POST /chat              — 对话接口
      GET  /memory/{user_id} — 记忆探查接口（白盒测试专用）
      POST /reset             — 环境重置接口
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ) -> None:
        """
        初始化客户端。

        Args:
            base_url:      目标 Agent 的根 URL，例如 "http://localhost:8000"
            timeout:       单次请求超时时间（秒）
            max_retries:   最大重试次数（仅对网络级错误重试）
            retry_backoff: 重试等待基础时间，第 n 次重试等待 backoff * n 秒
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    # ------------------------------------------------------------------
    # 内部：带重试的原始 HTTP 请求
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """
        执行 HTTP 请求，对网络故障进行指数退避重试。

        重试策略：
          - httpx.ConnectError / httpx.TimeoutException → 重试
          - HTTP 4xx / 5xx → 直接抛出 AgentAPIError，不重试（避免重复副作用）
        """
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as http:
                    resp = http.request(method, url, **kwargs)

                # HTTP 错误码 → 解析错误详情后抛出，不重试
                if resp.status_code >= 400:
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    raise AgentAPIError(resp.status_code, str(detail))

                return resp

            except AgentAPIError:
                raise  # HTTP 级别错误，直接向上传播

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                wait = self.retry_backoff * (attempt + 1)
                if attempt < self.max_retries - 1:
                    time.sleep(wait)  # 退避等待后重试

            except httpx.HTTPError as exc:
                raise AgentConnectionError(f"HTTP 通信错误: {exc}") from exc

        raise AgentConnectionError(
            f"经过 {self.max_retries} 次重试后仍无法连接到 {url}。"
            f"最后一次错误: {last_error}"
        )

    # ------------------------------------------------------------------
    # 公开 API 方法
    # ------------------------------------------------------------------

    def chat(self, user_id: str, message: str) -> ChatResponse:
        """
        调用 POST /chat 接口。

        Args:
            user_id: 用户标识符
            message: 用户消息文本

        Returns:
            ChatResponse，包含 response 和可选的 retrieved_memories
        """
        resp = self._request(
            "POST", "/chat",
            json={"user_id": user_id, "message": message},
        )
        return ChatResponse(**resp.json())

    def get_memory(self, user_id: str) -> MemoryResponse:
        """
        调用 GET /memory/{user_id} 接口，白盒读取用户当前完整记忆库。

        Args:
            user_id: 用户标识符

        Returns:
            MemoryResponse，包含 memories 字段
        """
        resp = self._request("GET", f"/memory/{user_id}")
        return MemoryResponse(**resp.json())

    def reset(self, user_id: str) -> ResetResponse:
        """
        调用 POST /reset 接口，清空指定用户的所有对话历史与记忆。

        每个测试用例开始前必须调用此方法，确保测试环境干净隔离。

        Args:
            user_id: 需要重置的用户标识符

        Returns:
            ResetResponse，status 为 'ok' 表示成功
        """
        resp = self._request("POST", "/reset", json={"user_id": user_id})
        return ResetResponse(**resp.json())
