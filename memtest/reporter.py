"""
memtest/reporter.py
-------------------
报告生成器，提供两种输出形式：

  1. TerminalReporter  — 使用 rich 库在终端打印彩色统计表格
                         （若 rich 未安装则降级为纯文本输出）
  2. MarkdownReporter  — 将测试结果导出为结构化 Markdown 报告文件
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List

from .models import ResultStatus, TestCaseResult


# ---------------------------------------------------------------------------
# 终端报告
# ---------------------------------------------------------------------------

class TerminalReporter:
    """
    在终端打印格式化的测试结果摘要。
    优先使用 rich 库渲染彩色表格，若不可用则降级为纯文本。
    """

    def __init__(self, results: List[TestCaseResult]) -> None:
        self.results = results

    @staticmethod
    def _try_import_rich():
        """尝试导入 rich，失败返回 None。"""
        try:
            from rich.console import Console
            return Console()
        except ImportError:
            return None

    def print_summary(self) -> None:
        """打印完整的测试摘要：总览面板 + 详细用例表格 + 失败用例展开。"""
        passed = sum(1 for r in self.results if r.overall_status == ResultStatus.PASS)
        failed = sum(1 for r in self.results if r.overall_status == ResultStatus.FAIL)
        errors = sum(1 for r in self.results if r.overall_status == ResultStatus.ERROR)
        total = len(self.results)
        pass_rate = (passed / total * 100) if total > 0 else 0.0

        console = self._try_import_rich()
        if console is None:
            self._print_plain(passed, failed, errors, total, pass_rate)
            return

        # ── 导入 rich 组件 ──
        from rich.table import Table
        from rich.panel import Panel
        from rich import box

        # ── 总览面板 ──
        rate_color = (
            "green" if pass_rate >= 80
            else ("yellow" if pass_rate >= 50 else "red")
        )
        summary_text = (
            f"[bold]总用例数:[/bold] {total}   "
            f"[green]通过: {passed}[/green]   "
            f"[red]失败: {failed}[/red]   "
            f"[yellow]错误: {errors}[/yellow]   "
            f"[{rate_color}]通过率: {pass_rate:.1f}%[/{rate_color}]"
        )
        console.print(
            Panel(
                summary_text,
                title="[bold cyan]MemTest-Mini 测试报告[/bold cyan]",
                box=box.ROUNDED,
            )
        )

        # ── 详细用例表格 ──
        table = Table(
            title="测试用例详情",
            box=box.SIMPLE_HEAD,
            show_lines=True,
            header_style="bold magenta",
        )
        table.add_column("测试 ID", style="cyan", no_wrap=True)
        table.add_column("类型", justify="center")
        table.add_column("状态", justify="center")
        table.add_column("耗时(s)", justify="right")
        table.add_column("详情摘要")

        status_styles = {
            ResultStatus.PASS:  "[bold green]✓ PASS[/bold green]",
            ResultStatus.FAIL:  "[bold red]✗ FAIL[/bold red]",
            ResultStatus.ERROR: "[bold yellow]⚠ ERROR[/bold yellow]",
        }

        for r in self.results:
            status_str = status_styles.get(r.overall_status, str(r.overall_status))
            # 优先显示失败/错误的子检查原因
            reasons = [
                f"[{c.check_name}] {c.reason}"
                for c in r.sub_checks
                if c.status != ResultStatus.PASS
            ]
            detail = r.error_message or ("; ".join(reasons) if reasons else "—")
            if len(detail) > 80:
                detail = detail[:77] + "..."

            table.add_row(
                r.test_id,
                r.test_type,
                status_str,
                f"{r.duration_seconds:.2f}",
                detail,
            )

        console.print(table)

        # ── 失败/错误用例展开详情 ──
        failed_results = [
            r for r in self.results if r.overall_status != ResultStatus.PASS
        ]
        if failed_results:
            console.print("\n[bold red]═══ 失败 / 错误用例详情 ═══[/bold red]")
            for r in failed_results:
                console.print(f"\n  [cyan]{r.test_id}[/cyan]  ({r.test_type})")
                if r.error_message:
                    console.print(f"    [yellow]执行错误: {r.error_message}[/yellow]")
                for check in r.sub_checks:
                    icon = "✓" if check.status == ResultStatus.PASS else "✗"
                    color = "green" if check.status == ResultStatus.PASS else "red"
                    score_str = (
                        f"  score={check.score:.2f}" if check.score is not None else ""
                    )
                    console.print(
                        f"    [{color}]{icon} [{check.check_name}]{score_str}: "
                        f"{check.reason}[/{color}]"
                    )
                if r.agent_responses:
                    last_resp = r.agent_responses[-1][:120]
                    console.print(f"    [dim]Agent 最后回复: {last_resp}[/dim]")

    def _print_plain(
        self,
        passed: int,
        failed: int,
        errors: int,
        total: int,
        pass_rate: float,
    ) -> None:
        """rich 不可用时的纯文本降级输出。"""
        sep = "=" * 60
        print(f"\n{sep}")
        print("  MemTest-Mini 测试报告")
        print(sep)
        print(
            f"  总用例: {total} | 通过: {passed} | 失败: {failed} | 错误: {errors}"
        )
        print(f"  通过率: {pass_rate:.1f}%")
        print("-" * 60)
        for r in self.results:
            print(
                f"  [{r.overall_status.value:5s}] {r.test_id}"
                f" ({r.test_type}) - {r.duration_seconds:.2f}s"
            )
            for c in r.sub_checks:
                if c.status != ResultStatus.PASS:
                    print(f"         → [{c.check_name}] {c.reason}")
        print(f"{sep}\n")


# ---------------------------------------------------------------------------
# Markdown 报告导出
# ---------------------------------------------------------------------------

class MarkdownReporter:
    """将测试结果导出为结构化 Markdown 报告文件。"""

    def __init__(
        self,
        results: List[TestCaseResult],
        agent_url: str = "",
    ) -> None:
        self.results = results
        self.agent_url = agent_url

    def export(self, output_path: str) -> None:
        """
        生成 Markdown 报告并写入文件。

        Args:
            output_path: 输出文件路径，例如 "reports/report.md"
        """
        # 自动创建父目录
        parent = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(parent, exist_ok=True)

        content = self._build_content()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"\n[报告] Markdown 报告已导出至: {output_path}")

    def _build_content(self) -> str:
        """构建完整的 Markdown 文本。"""
        passed = sum(1 for r in self.results if r.overall_status == ResultStatus.PASS)
        failed = sum(1 for r in self.results if r.overall_status == ResultStatus.FAIL)
        errors = sum(1 for r in self.results if r.overall_status == ResultStatus.ERROR)
        total = len(self.results)
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 按类型汇总
        type_stats: dict = {}
        for r in self.results:
            t = r.test_type
            type_stats.setdefault(t, {"pass": 0, "fail": 0, "error": 0})
            if r.overall_status == ResultStatus.PASS:
                type_stats[t]["pass"] += 1
            elif r.overall_status == ResultStatus.FAIL:
                type_stats[t]["fail"] += 1
            else:
                type_stats[t]["error"] += 1

        lines: List[str] = [
            "# MemTest-Mini 测试报告",
            "",
            f"> 生成时间：{now}  ",
            f"> 目标 Agent：`{self.agent_url or '未指定'}`",
            "",
            "---",
            "",
            "## 总览",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总用例数 | {total} |",
            f"| 通过 (PASS) | {passed} |",
            f"| 失败 (FAIL) | {failed} |",
            f"| 错误 (ERROR) | {errors} |",
            f"| **通过率** | **{pass_rate:.1f}%** |",
            "",
            "## 按类型统计",
            "",
            "| 测试类型 | 通过 | 失败 | 错误 |",
            "|----------|:----:|:----:|:----:|",
        ]
        for t, s in type_stats.items():
            lines.append(f"| {t} | {s['pass']} | {s['fail']} | {s['error']} |")

        lines += [
            "",
            "---",
            "",
            "## 用例详情",
            "",
        ]

        for r in self.results:
            badge = {
                ResultStatus.PASS:  "✅ PASS",
                ResultStatus.FAIL:  "❌ FAIL",
                ResultStatus.ERROR: "⚠️ ERROR",
            }.get(r.overall_status, str(r.overall_status))

            lines.append(f"### `{r.test_id}` — {badge}")
            lines.append("")
            lines.append(f"- **类型**: {r.test_type}")
            if r.description:
                lines.append(f"- **描述**: {r.description}")
            lines.append(f"- **耗时**: {r.duration_seconds:.2f}s")
            lines.append("")

            if r.error_message:
                lines.append(f"> ⚠️ **执行错误**: `{r.error_message}`")
                lines.append("")

            if r.sub_checks:
                lines.append("**子检查结果:**")
                lines.append("")
                lines.append("| 检查项 | 状态 | 分数 | 原因 |")
                lines.append("|--------|:----:|:----:|------|")
                for c in r.sub_checks:
                    icon = (
                        "✅" if c.status == ResultStatus.PASS
                        else ("❌" if c.status == ResultStatus.FAIL else "⚠️")
                    )
                    score_str = f"{c.score:.2f}" if c.score is not None else "—"
                    lines.append(
                        f"| `{c.check_name}` | {icon} | {score_str} | {c.reason} |"
                    )
                lines.append("")

            if r.agent_responses:
                lines.append(
                    "<details><summary>Agent 回复记录（点击展开）</summary>"
                )
                lines.append("")
                for i, resp in enumerate(r.agent_responses, 1):
                    lines.append(f"**回复 {i}:**")
                    lines.append(f"```")
                    lines.append(resp)
                    lines.append(f"```")
                    lines.append("")
                lines.append("</details>")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
