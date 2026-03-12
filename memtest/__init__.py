"""
MemTest-Mini — 轻量级本地 Agent 记忆测试框架

对外暴露的公共 API：
  - TestRunner   : 测试运行器（主入口）
  - load_dataset : 从 JSON 文件加载测试用例
  - AgentClient  : HTTP 客户端（可单独使用）
  - EvalMethod   : 评估方法枚举
  - ResultStatus : 测试结果状态枚举
  - TestCaseResult: 单个用例的完整结果
"""

from .runner import TestRunner, load_dataset
from .client import AgentClient
from .models import EvalMethod, ResultStatus, TestCaseResult

__version__ = "0.1.0"
__all__ = [
    "TestRunner",
    "load_dataset",
    "AgentClient",
    "EvalMethod",
    "ResultStatus",
    "TestCaseResult",
]
