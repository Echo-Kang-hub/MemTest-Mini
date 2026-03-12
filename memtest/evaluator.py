"""
memtest/evaluator.py
--------------------
评估器模块，支持两种评估策略：

  1. ExactMatchEvaluator — 关键词精确匹配
     无需 API Key，速度极快，适合验证精确信息是否存在。
     将内容序列化为小写字符串后进行子串搜索。

  2. LLMJudgeEvaluator — LLM 作为裁判
     调用 OpenAI 兼容 API，让大模型判断语义正确性。
     能处理同义词、改写、多语言等精确匹配无法覆盖的场景。
"""

from __future__ import annotations

import json
import os
from typing import List, Optional, Any

from .models import ResultStatus, SubCheckResult


# ---------------------------------------------------------------------------
# 精确匹配评估器
# ---------------------------------------------------------------------------

class ExactMatchEvaluator:
    """
    精确关键词匹配评估器。

    将待检测内容（字符串/列表/字典）序列化为小写字符串，
    逐一检查 expected_items 中的关键词是否存在于其中。
    """

    @staticmethod
    def _to_str(content: Any) -> str:
        """将任意类型的内容序列化为可搜索的小写字符串。"""
        if isinstance(content, str):
            return content.lower()
        # list / dict → JSON 字符串后转小写，保留结构信息
        return json.dumps(content, ensure_ascii=False).lower()

    def check_contains(
        self,
        content: Any,
        expected_items: List[str],
        require_all: bool = True,
        check_name: str = "contains_check",
    ) -> SubCheckResult:
        """
        检查 content 是否包含 expected_items 中的关键词。

        Args:
            content:        被检查的内容（字符串、列表或字典均可）
            expected_items: 期望出现的关键词列表
            require_all:    True = 所有词都必须存在；False = 至少存在一个
            check_name:     子检查名称（显示在报告中）

        Returns:
            SubCheckResult，status 为 PASS 或 FAIL
        """
        content_str = self._to_str(content)
        found = [item for item in expected_items if item.lower() in content_str]
        missing = [item for item in expected_items if item.lower() not in content_str]

        if require_all:
            passed = len(missing) == 0
            reason = (
                f"所有期望关键词均已找到: {expected_items}"
                if passed
                else f"缺失关键词: {missing}"
            )
        else:
            passed = len(found) > 0
            reason = (
                f"已找到至少一个期望关键词: {found}"
                if passed
                else f"未找到任何期望关键词: {expected_items}"
            )

        return SubCheckResult(
            check_name=check_name,
            status=ResultStatus.PASS if passed else ResultStatus.FAIL,
            reason=reason,
        )

    def check_excludes(
        self,
        content: Any,
        excluded_items: List[str],
        require_all_absent: bool = True,
        check_name: str = "excludes_check",
    ) -> SubCheckResult:
        """
        检查 content 中是否【不】包含 excluded_items 中的关键词。
        用于验证旧记忆是否已被覆盖/清除。

        Args:
            content:             被检查的内容
            excluded_items:      期望不应出现的关键词（旧状态/被覆盖信息）
            require_all_absent:  True = 所有词都不能出现；False = 只要有一个缺失即通过
            check_name:          子检查名称

        Returns:
            SubCheckResult，status 为 PASS 或 FAIL
        """
        content_str = self._to_str(content)
        found_forbidden = [
            item for item in excluded_items if item.lower() in content_str
        ]

        if require_all_absent:
            passed = len(found_forbidden) == 0
            reason = (
                "所有旧记忆均已被覆盖或清除。"
                if passed
                else f"发现应被覆盖的旧记忆关键词: {found_forbidden}"
            )
        else:
            passed = len(found_forbidden) < len(excluded_items)
            reason = (
                f"部分旧记忆仍存在: {found_forbidden}"
                if found_forbidden
                else "所有旧记忆均已清除。"
            )

        return SubCheckResult(
            check_name=check_name,
            status=ResultStatus.PASS if passed else ResultStatus.FAIL,
            reason=reason,
        )


# ---------------------------------------------------------------------------
# LLM 裁判评估器
# ---------------------------------------------------------------------------

class LLMJudgeEvaluator:
    """
    LLM 裁判评估器。

    通过调用 OpenAI 兼容 API，让大模型判断 Agent 的回答是否正确利用了记忆。
    相比精确匹配，能处理同义词、改写、语义等价、多语言混用等场景。

    依赖：pip install openai
    """

    # 评测 Prompt 模板（中文）
    JUDGE_PROMPT_TEMPLATE = """你是一个严格公正的 AI 评测裁判。你的任务是判断一个 AI Agent 的回复是否正确地利用了其记忆来回答问题。

【测试问题】
{question}

【Agent 的回复】
{agent_response}

【评测标准】
Agent 的回复应当包含或正确表达以下关键信息（语义正确即可，不要求字面完全一致）：
{expected_keywords}

【判断规则】
- 语义等价（如"摄影师"与"photographer"）应视为通过
- 如果 Agent 明确说不记得、回避了问题，或给出明显错误/矛盾的信息，应判定为失败
- 如果回复完全不相关，应判定为失败

请严格以以下 JSON 格式回复，不要输出任何其他内容：
{{"pass": true/false, "score": 0.0到1.0之间的浮点数, "reasoning": "简短的判断理由（中文，不超过50字）"}}"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """
        初始化 LLM 裁判。

        Args:
            model:    使用的评测模型，默认 gpt-4o-mini（速度/成本最优平衡）
            api_key:  OpenAI API Key；若不传，从环境变量 OPENAI_API_KEY 读取
            base_url: 自定义 API 端点（用于 OpenAI 兼容服务，如 Azure、本地部署等）
        """
        try:
            from openai import OpenAI as _OpenAI
        except ImportError as exc:
            raise ImportError(
                "使用 LLM Judge 需要安装 openai 包: pip install openai"
            ) from exc

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "未提供 OpenAI API Key。\n"
                "请在启动参数中通过 --llm-api-key 提供，"
                "或设置环境变量 OPENAI_API_KEY。"
            )

        init_kwargs: dict = {"api_key": key}
        if base_url:
            init_kwargs["base_url"] = base_url

        self._client = _OpenAI(**init_kwargs)
        self.model = model

    def judge(
        self,
        question: str,
        agent_response: str,
        expected_keywords: List[str],
        check_name: str = "llm_judge_check",
    ) -> SubCheckResult:
        """
        让 LLM 裁判对 Agent 的回复进行语义评估。

        Args:
            question:          发给 Agent 的原始问题
            agent_response:    Agent 的回复文本
            expected_keywords: 期望 Agent 在回复中体现的关键信息列表
            check_name:        子检查名称（显示在报告中）

        Returns:
            SubCheckResult，包含 PASS/FAIL 状态、原因说明和置信度分数
        """
        prompt = self.JUDGE_PROMPT_TEMPLATE.format(
            question=question,
            agent_response=agent_response,
            expected_keywords=", ".join(expected_keywords),
        )

        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,  # 评测需要结果确定性
            )
            raw = completion.choices[0].message.content or "{}"
            result = json.loads(raw)

            passed = bool(result.get("pass", False))
            score = float(result.get("score", 1.0 if passed else 0.0))
            reasoning = result.get("reasoning", "（LLM 未提供理由）")

            return SubCheckResult(
                check_name=check_name,
                status=ResultStatus.PASS if passed else ResultStatus.FAIL,
                reason=reasoning,
                score=score,
            )

        except json.JSONDecodeError as exc:
            return SubCheckResult(
                check_name=check_name,
                status=ResultStatus.ERROR,
                reason=f"LLM 返回了无效的 JSON 格式: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            return SubCheckResult(
                check_name=check_name,
                status=ResultStatus.ERROR,
                reason=f"LLM Judge API 调用失败: {type(exc).__name__}: {exc}",
            )
