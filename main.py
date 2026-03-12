"""
main.py
-------
MemTest-Mini 命令行入口。

典型用法：

  # 对单个数据集文件运行精确匹配测试
  python main.py --url http://localhost:8000 --dataset datasets/extraction_tests.json

  # 对目录下所有 JSON 文件批量测试
  python main.py --url http://localhost:8000 --dataset datasets/

  # 使用 LLM Judge 评估，并导出 Markdown 报告
  python main.py --url http://localhost:8000 --dataset datasets/ \\
                 --eval llm_judge --llm-model gpt-4o-mini \\
                 --report reports/report.md

  # 使用自定义 OpenAI 兼容 API 端点（如 DeepSeek、本地 Ollama 等）
  python main.py --url http://localhost:8000 --dataset datasets/ \\
                 --eval llm_judge \\
                 --llm-base-url https://api.deepseek.com/v1 \\
                 --llm-model deepseek-chat \\
                 --report reports/report.md --verbose
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# 确保项目根目录在 sys.path 中，支持直接 python main.py 运行
sys.path.insert(0, str(Path(__file__).parent))

from memtest import TestRunner, load_dataset
from memtest.models import AnyTestCase, EvalMethod, TestCaseResult


# ---------------------------------------------------------------------------
# 加载 config.yaml（可选，不存在或解析失败时静默跳过）
# ---------------------------------------------------------------------------

def load_config() -> Dict[str, Any]:
    """尝试加载与 main.py 同目录的 config.yaml，返回解析后的字典。"""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml  # type: ignore
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 命令行参数解析
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="memtest",
        description="MemTest-Mini — 轻量级本地 Agent 记忆能力测试框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --url http://localhost:8000 --dataset datasets/extraction_tests.json
  python main.py --url http://localhost:8000 --dataset datasets/ --eval llm_judge
  python main.py --url http://localhost:8000 --dataset datasets/ --report reports/report.md -v
        """,
    )

    # ── 必填参数 ──
    required = parser.add_argument_group("必填参数")
    required.add_argument(
        "--url",
        required=True,
        metavar="AGENT_URL",
        help="目标 Agent 的根 URL，例如: http://localhost:8000",
    )
    required.add_argument(
        "--dataset",
        required=True,
        metavar="PATH",
        help="测试数据集 JSON 文件路径，或包含多个 JSON 文件的目录路径",
    )

    # ── 评估配置 ──
    eval_group = parser.add_argument_group("评估配置")
    eval_group.add_argument(
        "--eval",
        choices=["exact", "llm_judge"],
        default="exact",
        dest="eval_method",
        help=(
            "评估方法（默认: exact）\n"
            "  exact     — 精确关键词匹配，无需 API Key，速度快\n"
            "  llm_judge — LLM 作为裁判，语义评估，需要 OpenAI API Key"
        ),
    )

    # ── LLM Judge 专用配置 ──
    llm_group = parser.add_argument_group("LLM Judge 配置（--eval llm_judge 时有效）")
    llm_group.add_argument(
        "--llm-model",
        default="gpt-4o-mini",
        metavar="MODEL",
        help="评测模型名称（默认: gpt-4o-mini）",
    )
    llm_group.add_argument(
        "--llm-api-key",
        default=None,
        metavar="KEY",
        help="OpenAI API Key（也可通过环境变量 OPENAI_API_KEY 设置）",
    )
    llm_group.add_argument(
        "--llm-base-url",
        default=None,
        metavar="URL",
        help="OpenAI 兼容 API 的自定义端点（支持 DeepSeek、Azure 等）",
    )

    # ── 报告输出 ──
    output_group = parser.add_argument_group("报告输出")
    output_group.add_argument(
        "--report",
        default=None,
        metavar="OUTPUT_PATH",
        help="Markdown 报告输出路径（不指定则仅输出到终端），例如: reports/report.md",
    )

    # ── HTTP 客户端配置 ──
    http_group = parser.add_argument_group("HTTP 配置")
    http_group.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="单次 HTTP 请求超时时间（秒，默认: 30）",
    )
    http_group.add_argument(
        "--retries",
        type=int,
        default=3,
        metavar="N",
        help="网络错误最大重试次数（默认: 3）",
    )

    # ── 其他选项 ──
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细的执行日志（调试用）",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# 数据集文件收集
# ---------------------------------------------------------------------------

def collect_dataset_files(path_str: str) -> List[Path]:
    """
    收集数据集文件路径，支持：
      - 单个 .json 文件
      - 目录（自动搜索目录直接子级所有 .json 文件，按文件名排序）
    """
    path = Path(path_str)

    if not path.exists():
        print(f"[错误] 路径不存在: {path}", file=sys.stderr)
        sys.exit(1)

    if path.is_file():
        return [path]

    if path.is_dir():
        files = sorted(path.glob("*.json"))
        if not files:
            print(f"[错误] 目录 {path} 中没有找到 .json 文件。", file=sys.stderr)
            sys.exit(1)
        return files

    print(f"[错误] 无效路径: {path}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    cfg = load_config()
    cfg_llm: Dict[str, Any] = cfg.get("llm_judge", {}) or {}
    cfg_agent: Dict[str, Any] = cfg.get("agent", {}) or {}
    cfg_eval: Dict[str, Any] = cfg.get("eval", {}) or {}

    # ── 确定评估方法（命令行 > config）──
    if args.eval_method == "exact" and cfg_eval.get("method") == "llm_judge":
        eval_method = EvalMethod.LLM_JUDGE
    else:
        eval_method = (
            EvalMethod.LLM_JUDGE if args.eval_method == "llm_judge"
            else EvalMethod.EXACT
        )

    # ── LLM Judge 模式前置检查（命令行 > 环境变量 > config）──
    api_key: str | None = None
    if eval_method == EvalMethod.LLM_JUDGE:
        api_key = (
            args.llm_api_key
            or os.environ.get("OPENAI_API_KEY")
            or cfg_llm.get("api_key")
        )
        if not api_key:
            print(
                "[错误] 使用 LLM Judge 模式需要提供 OpenAI API Key。\n"
                "       请通过 --llm-api-key 参数传入，"
                "或设置环境变量 OPENAI_API_KEY，"
                "或在 config.yaml 的 llm_judge.api_key 中配置。",
                file=sys.stderr,
            )
            sys.exit(1)

    # ── 合并其他 LLM 配置（命令行优先，其次 config）──
    llm_model = args.llm_model if args.llm_model != "gpt-4o-mini" else (
        cfg_llm.get("model") or args.llm_model
    )
    llm_base_url = args.llm_base_url or cfg_llm.get("base_url")

    # ── 初始化 Runner ──
    try:
        runner = TestRunner(
            agent_url=args.url,
            eval_method=eval_method,
            llm_model=llm_model,
            llm_api_key=api_key,
            llm_base_url=llm_base_url,
            timeout=args.timeout or cfg_agent.get("timeout", 30),
            max_retries=args.retries if args.retries != 3 else (
                cfg_agent.get("max_retries") or args.retries
            ),
            verbose=args.verbose,
        )
    except (ValueError, ImportError) as exc:
        print(f"[错误] 初始化失败: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── 收集数据集文件 ──
    dataset_files = collect_dataset_files(args.dataset)

    # ── 依次运行所有数据集 ──
    all_results: List[TestCaseResult] = []
    for dataset_file in dataset_files:
        try:
            results = runner.run_file(str(dataset_file))
            all_results.extend(results)
        except FileNotFoundError as exc:
            print(f"[错误] 文件不找到: {exc}", file=sys.stderr)
            sys.exit(1)
        except ValueError as exc:
            print(f"[错误] 数据集解析失败: {exc}", file=sys.stderr)
            sys.exit(1)

    if not all_results:
        print("[警告] 没有运行任何测试用例，请检查数据集文件。")
        sys.exit(0)

    # ── 生成报告 ──
    runner.report(all_results, markdown_output=args.report)

    # ── 退出码：全部通过返回 0，否则返回 1（方便 CI/CD 集成）──
    total_passed = sum(1 for r in all_results if r.overall_status.value == "PASS")
    sys.exit(0 if total_passed == len(all_results) else 1)


if __name__ == "__main__":
    main()
