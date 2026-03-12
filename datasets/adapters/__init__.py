"""
datasets/adapters 包

提供将外部长期记忆评测数据集转换为 MemTest-Mini 标准格式的适配器。

支持的数据集：
  - LongMemEval : LongMemEvalAdapter (longmemeval.py)
  - LoCoMo      : LoCoMoAdapter      (locomo.py)

使用方式：
  1. CLI 工具（推荐）：
     python datasets/adapters/convert_cli.py --adapter longmemeval ...

  2. Python API：
     from datasets.adapters import LongMemEvalAdapter
     adapter = LongMemEvalAdapter()
     cases = adapter.convert_and_save("data.jsonl", "datasets/lme.json")
"""

from .longmemeval import LongMemEvalAdapter
from .locomo import LoCoMoAdapter

__all__ = ["LongMemEvalAdapter", "LoCoMoAdapter"]
