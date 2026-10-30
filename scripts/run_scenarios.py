#!/usr/bin/env python3
"""
CLI Scenario Benchmark Suite Runner (Task 7.1 - 7.3)
Runs automated stress-test scenarios, displays ANSI console scorecards,
and exports structured benchmark evaluation reports.
"""
import asyncio
import argparse
import sys
import json
from pathlib import Path

# Ensure repository root is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import settings  # noqa: E402
from backend.core.twin_state import create_default_farm  # noqa: E402
from backend.agents.agronomist import AgronomistAgent  # noqa: E402
from backend.agents.irrigation import IrrigationAgent  # noqa: E402
from backend.agents.market import MarketAgent  # noqa: E402
from backend.agents.commander import CommanderAgent  # noqa: E402
from backend.benchmarks.runner import benchmark_runner  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def print_banner():
    print("=" * 72)
    print("🌾 FARM_COM AUTONOMOUS OS: SCENARIO STRESS BENCHMARK SUITE")
    print("   Evaluating Multi-Agent Council Resilience, Biology & Energy Economics")
    print("=" * 72)


def print_scorecard(report):
    print("\n" + "-" * 72)
    print(f"📊 COMPOSITE EVALUATION SCORECARD: GRADE {report.composite_grade} ({report.composite_score}/100)")
    print(f"   Scenarios Passed: {report.passed_scenarios}/{report.total_scenarios}")
    print("-" * 72)

    for i, r in enumerate(report.results, 1):
        status_icon = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"\n{i}. [{status_icon}] {r.scenario_name}")
        print(f"   Score: {r.score}/100 (Grade {r.grade}) | Executed in: {r.elapsed_time_s}s")
        print(f"   Summary: {r.summary}")
        print("   Detailed Metrics:")
        for m in r.metrics:
            check = "✓" if m.passed else "✗"
            print(f"     • [{check}] {m.name:34}: {m.value:>6.1f} {m.unit:<5} (Target: {m.target:>5.1f})")


async def main():
    parser = argparse.ArgumentParser(description="Farm_com Scenario Benchmark Suite CLI Runner")
    parser.add_argument("--scenario", default="all", help="Scenario ID to run ('all', 'drought_shock', 'fungal_outbreak', etc.)")
    parser.add_argument("--export", default=None, help="File path to export report (e.g. benchmark_results.json)")
    args = parser.parse_args()

    print_banner()

    # Instantiate digital twin and agent swarm
    farm = create_default_farm(width=settings.grid_size_x, height=settings.grid_size_y)
    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    print(f"Instantiated Da Lat Smart Farm ({farm.grid_width}x{farm.grid_height} plots) & Council...")

    if args.scenario == "all":
        print("Executing full multi-scenario benchmark battery...")
        report = await benchmark_runner.run_all(farm, commander)
        print_scorecard(report)

        if args.export:
            export_path = Path(args.export)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"\n📁 Report successfully exported to: {export_path.resolve()}")
    else:
        print(f"Executing single scenario: '{args.scenario}'...")
        res = await benchmark_runner.run_scenario(args.scenario, farm, commander)
        status_icon = "✅ PASS" if res.passed else "❌ FAIL"
        print(f"\n[{status_icon}] {res.scenario_name}: {res.score}/100 (Grade {res.grade})")
        print(f"Summary: {res.summary}")


if __name__ == "__main__":
    asyncio.run(main())
