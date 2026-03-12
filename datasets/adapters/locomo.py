"""
datasets/adapters/locomo.py
----------------------------
LoCoMo 数据集适配器。

LoCoMo 论文: "LoCoMo: Very Long-Term Conversational Memory Benchmark" (SIGDIAL 2024)
数据集来源: https://github.com/snap-research/locomo

原始数据格式 (JSON):
{
  "conv_id": "conv_001",
  "date_time": [...],
  "conversation": {
    "1": {              // session 编号（按日期排列）
      "date": "...",
      "dialog": [
        {
          "speaker": "Person1",   // 或 "Person2"
          "utterance": "I'm planning to go hiking next weekend..."
        },
        ...
      ]
    },
    "2": { ... },
    ...
  },
  "qa": [
    {
      "question": "What activity is Person1 planning for next weekend?",
      "answer": "Hiking",
      "evidence_turn_id": [...],
      "type": "single-hop" | "multi-hop" | "temporal_reasoning" | "adversarial"
    },
    ...
  ]
}

转换策略:
  - 每个 conv_id 对应多个 QA 对，每个 QA 对 → 1 个 retrieval 测试用例
  - conversation 中所有 dialog utterance → setup turns（用户视角统一为 role=user）
  - qa[i].question → query
  - qa[i].answer → expected_response_contains（关键词提取）
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .base import BaseDatasetAdapter


class LoCoMoAdapter(BaseDatasetAdapter):
    """
    LoCoMo 数据集适配器。

    LoCoMo 的对话是两人（Person1/Person2）之间的长期对话，
    跨越多个 session（按日期划分），QA 对测试对跨越长期对话的事实检索能力。
    """

    def __init__(
        self,
        max_setup_turns: int = 30,
        target_speaker: str = "Person1",
        require_all: bool = False,
        qa_types: List[str] | None = None,
    ) -> None:
        """
        Args:
            max_setup_turns:  最多保留多少轮对话作为 setup（防止 context 过长）
            target_speaker:   作为"用户"视角的说话人，该用户的话将优先被测试
            require_all:      生成用例中 require_all 字段的值
            qa_types:         只转换指定类型的 QA（None 表示转换全部类型）
                              可选值: "single-hop", "multi-hop",
                                      "temporal_reasoning", "adversarial"
        """
        self.max_setup_turns = max_setup_turns
        self.target_speaker = target_speaker
        self.require_all = require_all
        self.qa_types = set(qa_types) if qa_types else None

    def _extract_keywords(self, answer: str) -> List[str]:
        """从 answer 提取关键词（与 LongMemEval 适配器策略相同）。"""
        answer = answer.strip()
        if len(answer) <= 20:
            return [answer]
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were",
            "he", "she", "it", "they", "his", "her", "its",
            "用户", "他", "她", "的", "了", "是", "在", "有",
        }
        words = answer.split()
        keywords = [
            w.strip(".,!?\"'()[]{}。，！？") for w in words
            if len(w.strip(".,!?\"'()[]{}。，！？")) >= 2
            and w.lower() not in stopwords
        ]
        seen, unique = set(), []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:5] if unique else [answer]

    def _extract_setup_turns(self, conversation: dict) -> List[dict]:
        """
        从多 session 的对话字典中，按 session 顺序提取所有对话轮次。

        LoCoMo 将所有 utterance 的角色统一映射为 "user"，
        并在内容前加 [说话人名] 前缀，保留双方对话的完整语境。
        """
        turns = []
        # session 键是字符串数字，按数值排序保证时序正确
        for session_key in sorted(conversation.keys(), key=lambda x: int(x)):
            session = conversation[session_key]
            date_str = session.get("date", "")
            dialogs = session.get("dialog", [])

            # 在每个 session 开头插入日期标记，帮助 Agent 建立时序记忆
            if date_str and dialogs:
                turns.append({
                    "role": "user",
                    "content": f"[日期：{date_str}]",
                })

            for dialog_entry in dialogs:
                speaker = dialog_entry.get("speaker", "Unknown")
                utterance = dialog_entry.get("utterance", "").strip()
                if not utterance:
                    continue
                turns.append({
                    "role": "user",
                    "content": f"[{speaker}]: {utterance}",
                })

        # 截断
        if len(turns) > self.max_setup_turns:
            turns = turns[-self.max_setup_turns:]

        return turns

    def convert(self, input_path: str) -> List[dict]:
        """
        将 LoCoMo JSON 文件转换为 MemTest-Mini retrieval 测试用例列表。

        Args:
            input_path: LoCoMo JSON 文件路径（单个 conv 对象，或对象数组）

        Returns:
            MemTest-Mini 格式的测试用例列表
        """
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        data = self._load_json(input_path)
        # 支持单个对象或对象数组
        conversations: List[dict] = data if isinstance(data, list) else [data]

        test_cases: List[dict] = []
        skipped = 0

        for conv in conversations:
            conv_id = conv.get("conv_id", f"conv_{len(test_cases):04d}")
            conversation = conv.get("conversation", {})
            qa_list = conv.get("qa", [])

            if not conversation or not qa_list:
                skipped += 1
                continue

            # 提取 setup turns（整段对话历史，所有 QA 对共用）
            setup_turns = self._extract_setup_turns(conversation)
            if not setup_turns:
                skipped += 1
                continue

            for qa_idx, qa in enumerate(qa_list):
                question = qa.get("question", "").strip()
                answer = qa.get("answer", "").strip()
                qa_type = qa.get("type", "unknown")

                if not question or not answer:
                    skipped += 1
                    continue

                # 按类型过滤
                if self.qa_types and qa_type not in self.qa_types:
                    continue

                keywords = self._extract_keywords(answer)

                test_case = {
                    "test_id": f"locomo_{conv_id}_q{qa_idx:02d}",
                    "type": "retrieval",
                    "description": f"[LoCoMo/{qa_type}] {question[:60]}",
                    "setup": setup_turns,
                    "query": question,
                    "expected_response_contains": keywords,
                    "require_all": self.require_all,
                    "_source": {
                        "dataset": "LoCoMo",
                        "conv_id": conv_id,
                        "qa_type": qa_type,
                        "original_answer": answer,
                    },
                }
                test_cases.append(test_case)

        if skipped:
            print(f"[LoCoMo 适配器] 跳过了 {skipped} 条无效记录")
        print(f"[LoCoMo 适配器] 成功转换 {len(test_cases)} 条用例")
        return test_cases
