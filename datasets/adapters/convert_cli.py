"""
datasets/adapters/convert_cli.py
---------------------------------
数据集格式转换 CLI 工具。

用法：
  # 转换 LongMemEval 数据集
  python datasets/adapters/convert_cli.py \\
      --adapter longmemeval \\
      --input  /path/to/longmemeval_data.jsonl \\
      --output datasets/longmemeval_retrieval.json

  # 转换 LoCoMo 数据集（只保留 single-hop 和 multi-hop 类型）
  python datasets/adapters/convert_cli.py \\
      --adapter locomo \\
      --input  /path/to/locomo.json \\
      --output datasets/locomo_retrieval.json \\
      --locomo-qa-types single-hop multi-hop

  # 限制每个数据集最多转换 50 条（快速验证用）
  python datasets/adapters/convert_cli.py \\
      --adapter longmemeval \\
      --input  /path/to/data.jsonl \\
      --output datasets/lme_sample.json \\
      --max-cases 50
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="convert_cli",
        description="将外部数据集（LongMemEval / LoCoMo）转换为 MemTest-Mini 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--adapter",
        required=True,
        choices=["longmemeval", "locomo"],
        help="使用的适配器名称",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        metavar="PATH",
        help="原始数据集文件路径（JSON 或 JSONL）",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        metavar="PATH",
        help="转换后的 MemTest-Mini JSON 输出路径",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        metavar="N",
        help="最多转换 N 条用例（不指定则转换全部）",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        default=False,
        help="生成用例的 require_all 设为 true（默认 false，即至少匹配一个关键词）",
    )

    # LongMemEval 专用参数
    lme_group = parser.add_argument_group("LongMemEval 专用参数")
    lme_group.add_argument(
        "--lme-max-setup-turns",
        type=int,
        default=20,
        metavar="N",
        help="每个用例最多保留多少轮 setup 消息（默认: 20）",
    )

    # LoCoMo 专用参数
    locomo_group = parser.add_argument_group("LoCoMo 专用参数")
    locomo_group.add_argument(
        "--locomo-max-setup-turns",
        type=int,
        default=30,
        metavar="N",
        help="每个用例最多保留多少轮对话消息（默认: 30）",
    )
    locomo_group.add_argument(
        "--locomo-qa-types",
        nargs="+",
        metavar="TYPE",
        default=None,
        help=(
            "只转换指定类型的 QA（空格分隔）。\n"
            "可选: single-hop multi-hop temporal_reasoning adversarial"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 动态导入适配器，避免循环依赖
    if args.adapter == "longmemeval":
        from datasets.adapters.longmemeval import LongMemEvalAdapter
        adapter = LongMemEvalAdapter(
            max_setup_turns=args.lme_max_setup_turns,
            require_all=args.require_all,
        )
    elif args.adapter == "locomo":
        from datasets.adapters.locomo import LoCoMoAdapter
        adapter = LoCoMoAdapter(
            max_setup_turns=args.locomo_max_setup_turns,
            require_all=args.require_all,
            qa_types=args.locomo_qa_types,
        )
    else:
        print(f"[错误] 未知适配器: {args.adapter}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'─' * 50}")
    print(f"  适配器  : {args.adapter}")
    print(f"  输入    : {args.input}")
    print(f"  输出    : {args.output}")
    print(f"{'─' * 50}")

    try:
        test_cases = adapter.convert(args.input)
    except FileNotFoundError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        sys.exit(1)

    # 裁剪（如果指定了 --max-cases）
    if args.max_cases and len(test_cases) > args.max_cases:
        print(f"[截断] 保留前 {args.max_cases} 条（共 {len(test_cases)} 条）")
        test_cases = test_cases[: args.max_cases]

    adapter.save(test_cases, args.output)
    print(
        f"\n转换完成！可直接用于测试：\n"
        f"  python main.py --url http://localhost:8000 --dataset {args.output}"
    )


if __name__ == "__main__":
    main()
