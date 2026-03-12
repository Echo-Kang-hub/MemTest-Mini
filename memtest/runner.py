"""
memtest/runner.py
-----------------
TestRunner：测试运行器，是整个框架的核心调度器。

完整工作流程：
  1. 从 JSON 文件加载并解析测试用例（load_dataset）
  2. 对每个用例：
     a. 生成唯一 user_id，确保测试间完全隔离
     b. 调用 POST /reset 清空 Agent 的用户状态
     c. 依次发送 setup/turns 中的消息
     d. 发送 query（如有），获取最终回复
     e. 调用 Evaluator 进行评估，生成 SubCheckResult
     f. 汇总得到 TestCaseResult
  3. 调用 Reporter 输出终端报告，并可选导出 Markdown
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import List, Optional, Union

from .client import AgentClient, AgentClientError
from .evaluator import ExactMatchEvaluator, LLMJudgeEvaluator
from .models import (
    AnyTestCase,
    EvalMethod,
    ExtractionTestCase,
    MemoryResponse,
    RetrievalTestCase,
    ResultStatus,
    SubCheckResult,
    TestCaseResult,
    UpdateTestCase,
)
from .reporter import MarkdownReporter, TerminalReporter


# ---------------------------------------------------------------------------
# 数据集加载
# ---------------------------------------------------------------------------

def _parse_test_case(raw: dict) -> AnyTestCase:
    """根据 'type' 字段将原始字典解析为对应的 Pydantic 测试用例模型。"""
    test_type = raw.get("type")
    if test_type == "extraction":
        return ExtractionTestCase(**raw)
    elif test_type == "retrieval":
        return RetrievalTestCase(**raw)
    elif test_type == "update":
        return UpdateTestCase(**raw)
    else:
        raise ValueError(
            f"未知的测试类型: {test_type!r}，"
            f"支持的类型: extraction | retrieval | update"
        )


def load_dataset(path: Union[str, Path]) -> List[AnyTestCase]:
    """
    从 JSON 文件加载测试用例列表。

    文件格式：顶层为 JSON 数组，每个元素为一个测试用例对象。
    示例：[{"test_id": "ext_001", "type": "extraction", ...}, ...]

    Args:
        path: JSON 数据集文件路径

    Returns:
        解析后的测试用例列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError:        JSON 格式错误或 type 字段无效
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"数据集文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    if not isinstance(raw_list, list):
        raise ValueError(
            f"数据集文件应为 JSON 数组，实际为: {type(raw_list).__name__}"
        )

    return [_parse_test_case(item) for item in raw_list]


# ---------------------------------------------------------------------------
# 测试运行器
# ---------------------------------------------------------------------------

class TestRunner:
    """
    测试运行器：加载数据集 → 驱动 Client 与 Agent 交互 → 调用 Evaluator 评估。

    典型用法::

        runner = TestRunner(
            agent_url="http://localhost:8000",
            eval_method=EvalMethod.EXACT,
        )
        results = runner.run_file("datasets/extraction_tests.json")
        runner.report(results, markdown_output="reports/report.md")
    """

    def __init__(
        self,
        agent_url: str,
        eval_method: EvalMethod = EvalMethod.EXACT,
        # LLM Judge 专用配置
        llm_model: str = "gpt-4o-mini",
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None,
        # HTTP 客户端配置
        timeout: float = 30.0,
        max_retries: int = 3,
        # 测试行为配置
        user_id_prefix: str = "memtest",
        verbose: bool = False,
    ) -> None:
        """
        初始化测试运行器。

        Args:
            agent_url:      目标 Agent 的根 URL
            eval_method:    评估方法（EXACT 或 LLM_JUDGE）
            llm_model:      LLM Judge 使用的模型名
            llm_api_key:    LLM API Key
            llm_base_url:   自定义 LLM API 端点
            timeout:        单次 HTTP 请求超时（秒）
            max_retries:    网络错误最大重试次数
            user_id_prefix: 测试用户 ID 前缀，每个用例生成独立 user_id
            verbose:        是否输出详细调试日志
        """
        self.agent_url = agent_url
        self.eval_method = eval_method
        self.verbose = verbose
        self.user_id_prefix = user_id_prefix

        # 初始化 HTTP 客户端
        self.client = AgentClient(
            base_url=agent_url,
            timeout=timeout,
            max_retries=max_retries,
        )

        # 初始化精确匹配评估器（始终可用）
        self.exact_eval = ExactMatchEvaluator()

        # 初始化 LLM 裁判评估器（仅 LLM_JUDGE 模式时初始化）
        self.llm_eval: Optional[LLMJudgeEvaluator] = None
        if eval_method == EvalMethod.LLM_JUDGE:
            self.llm_eval = LLMJudgeEvaluator(
                model=llm_model,
                api_key=llm_api_key,
                base_url=llm_base_url,
            )

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        """仅在 verbose 模式下打印调试信息。"""
        if self.verbose:
            print(f"      [DEBUG] {msg}")

    def _make_user_id(self, test_id: str) -> str:
        """
        为每个测试用例生成唯一的 user_id。
        使用随机后缀确保即使并行运行也不会发生 ID 冲突。
        """
        return f"{self.user_id_prefix}_{test_id}_{uuid.uuid4().hex[:8]}"

    def _evaluate_response(
        self,
        question: str,
        response: str,
        expected_items: List[str],
        require_all: bool,
        check_name: str,
    ) -> SubCheckResult:
        """
        根据当前配置的评估方法，对 Agent 回复进行评估。
        LLM_JUDGE 模式不使用 require_all（由 LLM 自主判断语义）。
        """
        if self.eval_method == EvalMethod.LLM_JUDGE and self.llm_eval:
            return self.llm_eval.judge(
                question=question,
                agent_response=response,
                expected_keywords=expected_items,
                check_name=check_name,
            )
        return self.exact_eval.check_contains(
            content=response,
            expected_items=expected_items,
            require_all=require_all,
            check_name=check_name,
        )

    # ------------------------------------------------------------------
    # 各类型测试用例的具体执行逻辑
    # ------------------------------------------------------------------

    def _run_extraction(
        self, tc: ExtractionTestCase, user_id: str
    ) -> TestCaseResult:
        """
        执行记忆提取测试用例。

        流程：发送所有 turns → 读取记忆库 → 检查记忆库是否包含期望信息。
        """
        agent_responses: List[str] = []

        # 1. 按顺序发送所有对话轮次
        for turn in tc.turns:
            self._log(f"发送消息: {turn.content[:60]}...")
            chat_resp = self.client.chat(user_id=user_id, message=turn.content)
            agent_responses.append(chat_resp.response)

        # 2. 白盒读取记忆库内容
        mem_resp: MemoryResponse = self.client.get_memory(user_id=user_id)
        self._log(f"记忆库内容: {str(mem_resp.memories)[:120]}...")

        # 3. 检查记忆库是否包含期望关键词
        check = self.exact_eval.check_contains(
            content=mem_resp.memories,
            expected_items=tc.expected_memory_contains,
            require_all=tc.require_all,
            check_name="memory_contains_check",
        )

        return TestCaseResult(
            test_id=tc.test_id,
            test_type=tc.type,
            description=tc.description,
            overall_status=check.status,
            sub_checks=[check],
            agent_responses=agent_responses,
        )

    def _run_retrieval(
        self, tc: RetrievalTestCase, user_id: str
    ) -> TestCaseResult:
        """
        执行记忆检索测试用例。

        流程：发送 setup 消息（建立记忆）→ 发送 query → 评估回复内容。
        """
        agent_responses: List[str] = []

        # 1. 发送前置 setup 消息，建立记忆
        for turn in tc.setup:
            self._log(f"[setup] {turn.content[:60]}...")
            resp = self.client.chat(user_id=user_id, message=turn.content)
            agent_responses.append(resp.response)

        # 2. 发送最终测试查询
        self._log(f"[query] {tc.query}")
        query_resp = self.client.chat(user_id=user_id, message=tc.query)
        agent_responses.append(query_resp.response)

        # 3. 评估回复（精确匹配 or LLM Judge）
        check = self._evaluate_response(
            question=tc.query,
            response=query_resp.response,
            expected_items=tc.expected_response_contains,
            require_all=tc.require_all,
            check_name="response_contains_check",
        )

        return TestCaseResult(
            test_id=tc.test_id,
            test_type=tc.type,
            description=tc.description,
            overall_status=check.status,
            sub_checks=[check],
            agent_responses=agent_responses,
        )

    def _run_update(
        self, tc: UpdateTestCase, user_id: str
    ) -> TestCaseResult:
        """
        执行记忆更新与融合测试用例。

        流程：发送包含旧→新状态变更的对话 → 发送 query → 双重评估：
          1. 回复是否体现最新状态（response_contains_check）
          2. 记忆库是否已包含更新后的当前状态（memory_contains_check，验证融合）
        """
        agent_responses: List[str] = []
        sub_checks: List[SubCheckResult] = []

        # 1. 发送包含状态变更的完整对话序列
        for turn in tc.turns:
            self._log(f"发送: {turn.content[:60]}...")
            resp = self.client.chat(user_id=user_id, message=turn.content)
            agent_responses.append(resp.response)

        # 2. 发送查询，测试 Agent 是否采用了最新状态
        self._log(f"[query] {tc.query}")
        query_resp = self.client.chat(user_id=user_id, message=tc.query)
        agent_responses.append(query_resp.response)

        # 检查回复包含最新状态信息
        response_check = self._evaluate_response(
            question=tc.query,
            response=query_resp.response,
            expected_items=tc.expected_response_contains,
            require_all=tc.require_all_contains,
            check_name="response_contains_check",
        )
        sub_checks.append(response_check)

        # 3. 白盒读取记忆库，验证更新后的状态已被正确融合进记忆（核心测试点！）
        if tc.expected_memory_contains:
            mem_resp = self.client.get_memory(user_id=user_id)
            self._log(f"记忆库: {str(mem_resp.memories)[:120]}...")
            memory_check = self.exact_eval.check_contains(
                content=mem_resp.memories,
                expected_items=tc.expected_memory_contains,
                require_all=tc.require_all_memory,
                check_name="memory_contains_check",
            )
            sub_checks.append(memory_check)

        # 整体状态：所有子检查都通过才算通过
        if any(c.status == ResultStatus.ERROR for c in sub_checks):
            overall = ResultStatus.ERROR
        elif all(c.status == ResultStatus.PASS for c in sub_checks):
            overall = ResultStatus.PASS
        else:
            overall = ResultStatus.FAIL

        return TestCaseResult(
            test_id=tc.test_id,
            test_type=tc.type,
            description=tc.description,
            overall_status=overall,
            sub_checks=sub_checks,
            agent_responses=agent_responses,
        )

    # ------------------------------------------------------------------
    # 单用例完整执行（含重置 + 异常捕获）
    # ------------------------------------------------------------------

    def _run_single(self, tc: AnyTestCase) -> TestCaseResult:
        """
        执行单个测试用例的完整生命周期：
          1. 生成独立 user_id
          2. 重置 Agent 状态（确保环境干净）
          3. 按类型分派到具体执行方法
          4. 捕获所有异常，记录为 ERROR 状态而非终止
        """
        user_id = self._make_user_id(tc.test_id)
        start_time = time.monotonic()

        try:
            self._log(f"重置用户状态: {user_id}")
            self.client.reset(user_id=user_id)

            if isinstance(tc, ExtractionTestCase):
                result = self._run_extraction(tc, user_id)
            elif isinstance(tc, RetrievalTestCase):
                result = self._run_retrieval(tc, user_id)
            elif isinstance(tc, UpdateTestCase):
                result = self._run_update(tc, user_id)
            else:
                raise ValueError(f"不支持的测试用例类型: {type(tc)}")

        except AgentClientError as exc:
            result = TestCaseResult(
                test_id=tc.test_id,
                test_type=getattr(tc, "type", "unknown"),
                description=getattr(tc, "description", None),
                overall_status=ResultStatus.ERROR,
                error_message=f"Agent 通信错误: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            result = TestCaseResult(
                test_id=tc.test_id,
                test_type=getattr(tc, "type", "unknown"),
                description=getattr(tc, "description", None),
                overall_status=ResultStatus.ERROR,
                error_message=f"执行异常 [{type(exc).__name__}]: {exc}",
            )

        result.duration_seconds = time.monotonic() - start_time
        return result

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def run(self, test_cases: List[AnyTestCase]) -> List[TestCaseResult]:
        """
        运行给定的测试用例列表，返回所有结果。

        Args:
            test_cases: 已解析的测试用例列表

        Returns:
            对应的 TestCaseResult 列表（顺序与输入一致）
        """
        results: List[TestCaseResult] = []
        total = len(test_cases)

        for i, tc in enumerate(test_cases, 1):
            print(
                f"  [{i:3d}/{total}] 运行: {tc.test_id:<20s} ({tc.type})",
                end="",
                flush=True,
            )
            result = self._run_single(tc)

            status_icon = {
                ResultStatus.PASS:  " ✓",
                ResultStatus.FAIL:  " ✗",
                ResultStatus.ERROR: " ⚠",
            }.get(result.overall_status, " ?")
            print(f"{status_icon}  ({result.duration_seconds:.2f}s)")

            results.append(result)

        return results

    def run_file(self, dataset_path: Union[str, Path]) -> List[TestCaseResult]:
        """
        从 JSON 文件加载并运行测试用例。
        是 load_dataset() + run() 的便捷封装。

        Args:
            dataset_path: JSON 数据集文件路径

        Returns:
            测试结果列表
        """
        print(f"\n{'═' * 60}")
        print(f"  数据集  : {dataset_path}")
        test_cases = load_dataset(dataset_path)
        print(f"  用例数  : {len(test_cases)}")
        print(f"  目标    : {self.agent_url}")
        print(f"  评估    : {self.eval_method.value}")
        print(f"{'═' * 60}")

        return self.run(test_cases)

    def report(
        self,
        results: List[TestCaseResult],
        markdown_output: Optional[str] = None,
    ) -> None:
        """
        生成并输出测试报告。

        Args:
            results:         run() 或 run_file() 返回的结果列表
            markdown_output: 若指定，同时导出 Markdown 报告到此路径
        """
        terminal = TerminalReporter(results)
        terminal.print_summary()

        if markdown_output:
            md = MarkdownReporter(results, agent_url=self.agent_url)
            md.export(markdown_output)
