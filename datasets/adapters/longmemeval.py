"""
datasets/adapters/longmemeval.py
---------------------------------
LongMemEval 数据集适配器。

LongMemEval 论文: "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory"
数据集来源: https://github.com/xiaowu0162/LongMemEval

原始数据格式（每条样本为 JSONL 一行）:
{
  "question_id": "q001",
  "question_type": "single_session_user" | "cross_session" | ...,
  "question": "What is the user's dietary restriction?",
  "answer": "The user is vegetarian.",
  "answer_session_ids": ["sess_001"],  // 答案所在的 session
  "sessions": [
    {
      "session_id": "sess_001",
      "messages": [
        {"role": "user",      "content": "..."},
        {"role": "assistant", "content": "..."}
      ]
    },
    ...  // 可能有多个 session（跨 session 检索测试）
  ]
}

转换策略:
  - 每条样本 → 1 个 retrieval 测试用例
  - sessions 中所有 user 消息 → setup turns（建立记忆）
  - question → query
  - answer 分词后提取 → expected_response_contains
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .base import BaseDatasetAdapter


class LongMemEvalAdapter(BaseDatasetAdapter):
    """
    LongMemEval 数据集适配器。

    支持两种输入格式：
      - JSONL: 每行一条样本（官方发布格式）
      - JSON 数组: 包含多条样本的列表
    """

    def __init__(
        self,
        max_setup_turns: int = 20,
        require_all: bool = False,
        answer_split_on: str = " ",
    ) -> None:
        """
        Args:
            max_setup_turns:  最多保留多少轮 setup 消息（防止 prompt 过长）
            require_all:      生成用例中 require_all 字段的值
            answer_split_on:  用于从 answer 字段中提取关键词的分隔符
                              默认按空格分词，取长度≥2的中英文词作为关键词
        """
        self.max_setup_turns = max_setup_turns
        self.require_all = require_all
        self.answer_split_on = answer_split_on

    def _extract_keywords(self, answer: str) -> List[str]:
        """
        从 answer 字段提取用于检索验证的关键词/短语。

        策略：
          1. 若原始 answer 较短（≤20字符），直接作为单个关键词
          2. 否则：按空格分词，过滤掉长度<2的词和常见停用词
        """
        answer = answer.strip()
        # 短答案直接用整体
        if len(answer) <= 20:
            return [answer]

        # 长答案提取有意义的词
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "has", "have", "had", "do", "does", "did", "will", "would",
            "can", "could", "shall", "should", "may", "might",
            "of", "in", "on", "at", "to", "for", "with", "by", "from",
            "and", "or", "but", "not", "that", "this", "which",
            "用户", "他", "她", "它", "的", "了", "是", "在", "有",
        }
        words = answer.split()
        keywords = [
            w.strip(".,!?\"'()[]{}。，！？、；：") for w in words
            if len(w.strip(".,!?\"'()[]{}。，！？、；：")) >= 2
            and w.lower() not in stopwords
        ]
        # 去重并保持顺序
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        # 最多取 5 个关键词（避免过于严苛）
        return unique[:5] if unique else [answer]

    def convert(self, input_path: str) -> List[dict]:
        """
        将 LongMemEval 数据集转换为 MemTest-Mini retrieval 测试用例列表。

        Args:
            input_path: LongMemEval JSONL 或 JSON 文件路径

        Returns:
            MemTest-Mini 格式的测试用例列表
        """
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        # 自动检测格式
        raw_records: List[dict]
        if path.suffix == ".jsonl":
            raw_records = self._load_jsonl(input_path)
        else:
            data = self._load_json(input_path)
            raw_records = data if isinstance(data, list) else [data]

        test_cases: List[dict] = []
        skipped = 0

        for idx, record in enumerate(raw_records):
            question_id = record.get("question_id", f"lme_{idx:04d}")
            question = record.get("question", "")
            answer = record.get("answer", "")
            question_type = record.get("question_type", "unknown")
            sessions = record.get("sessions", [])

            if not question or not answer:
                skipped += 1
                continue

            # 收集所有 session 中的 user 消息作为 setup turns
            setup_turns = []
            for session in sessions:
                for msg in session.get("messages", []):
                    if msg.get("role") == "user":
                        setup_turns.append({
                            "role": "user",
                            "content": msg["content"],
                        })

            # 截断 setup 消息数量
            if len(setup_turns) > self.max_setup_turns:
                setup_turns = setup_turns[-self.max_setup_turns:]

            if not setup_turns:
                skipped += 1
                continue

            keywords = self._extract_keywords(answer)

            test_case = {
                "test_id": f"lme_{question_id}",
                "type": "retrieval",
                "description": f"[LongMemEval/{question_type}] {question[:60]}",
                "setup": setup_turns,
                "query": question,
                "expected_response_contains": keywords,
                "require_all": self.require_all,
                # 保留原始字段供调试
                "_source": {
                    "dataset": "LongMemEval",
                    "question_id": question_id,
                    "question_type": question_type,
                    "original_answer": answer,
                },
            }
            test_cases.append(test_case)

        if skipped:
            print(f"[LongMemEval 适配器] 跳过了 {skipped} 条无效记录（缺少 question/answer/session）")
        print(f"[LongMemEval 适配器] 成功转换 {len(test_cases)} 条用例")
        return test_cases
