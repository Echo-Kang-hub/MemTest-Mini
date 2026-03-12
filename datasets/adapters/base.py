"""
datasets/adapters/base.py
--------------------------
数据集适配器抽象基类。

所有外部数据集（LongMemEval、LoCoMo 等）的适配器都必须继承此类，
实现 convert() 方法，将原始格式转换为 MemTest-Mini 标准的 JSON 列表。

输出格式（标准 MemTest-Mini retrieval 类型）：
[
  {
    "test_id": "...",
    "type": "retrieval",
    "description": "...",
    "setup": [{"role": "user", "content": "..."}],
    "query": "...",
    "expected_response_contains": ["..."],
    "require_all": false
  },
  ...
]
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class BaseDatasetAdapter(ABC):
    """
    数据集适配器抽象基类。

    子类只需实现 convert() 方法，返回符合 MemTest-Mini 格式的字典列表。
    save() 方法由基类提供，统一处理文件写入。
    """

    @abstractmethod
    def convert(self, input_path: str) -> List[dict]:
        """
        将原始数据集文件转换为 MemTest-Mini 测试用例列表。

        Args:
            input_path: 原始数据集文件路径（JSON/JSONL）

        Returns:
            符合 MemTest-Mini Schema 的字典列表，可直接写入 JSON 文件，
            也可传入 load_dataset() 后进入 TestRunner。
        """

    def save(self, test_cases: List[dict], output_path: str) -> None:
        """
        将转换后的测试用例保存为 JSON 文件。

        Args:
            test_cases:  convert() 的返回值
            output_path: 输出文件路径
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)
        print(f"[适配器] 已导出 {len(test_cases)} 条测试用例 → {out}")

    def convert_and_save(self, input_path: str, output_path: str) -> List[dict]:
        """一步完成转换 + 保存，返回转换后的用例列表。"""
        cases = self.convert(input_path)
        self.save(cases, output_path)
        return cases

    # ------------------------------------------------------------------
    # 工具方法（供子类使用）
    # ------------------------------------------------------------------

    @staticmethod
    def _load_jsonl(path: str) -> List[dict]:
        """加载 JSONL 格式文件（每行一个 JSON 对象）。"""
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(f"[警告] 第 {i} 行 JSON 解析失败，已跳过: {exc}")
        return records

    @staticmethod
    def _load_json(path: str) -> list | dict:
        """加载普通 JSON 文件。"""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
