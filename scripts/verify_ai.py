#!/usr/bin/env python3
"""Run the AI validation suite used locally and in CI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_step(label: str, cmd: list[str]) -> None:
    print(f"[verify] {label}")
    completed = subprocess.run(cmd, cwd=ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-repeats", type=int, default=1)
    parser.add_argument("--warm-cases", type=int, default=250)
    parser.add_argument("--cold-cases", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260411)
    parser.add_argument("--report-every", type=int, default=0)
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--skip-cold-soak", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    python = sys.executable

    run_step(
        "py_compile",
        [
            python,
            "-m",
            "py_compile",
            "yacht_engine.py",
            "server.py",
            "scripts/benchmark_ai.py",
            "scripts/check_ai_golden.py",
            "scripts/soak_ai.py",
            "scripts/verify_ai.py",
            "yacht_ai/__init__.py",
            "yacht_ai/constants.py",
            "yacht_ai/scoring.py",
            "yacht_ai/advice.py",
            "yacht_ai/solver.py",
            "yacht_ai/ml_policy.py",
        ],
    )
    run_step("golden", [python, "scripts/check_ai_golden.py"])

    if not args.skip_benchmark:
        run_step(
            "benchmark",
            [python, "scripts/benchmark_ai.py", "--repeats", str(args.benchmark_repeats)],
        )

    warm_cmd = [
        python,
        "scripts/soak_ai.py",
        "--cases",
        str(args.warm_cases),
        "--seed",
        str(args.seed),
    ]
    if args.report_every:
        warm_cmd.extend(["--report-every", str(args.report_every)])
    run_step("soak-warm", warm_cmd)

    if not args.skip_cold_soak:
        cold_cmd = [
            python,
            "scripts/soak_ai.py",
            "--cases",
            str(args.cold_cases),
            "--seed",
            str(args.seed),
            "--cold-cache",
        ]
        if args.report_every:
            cold_cmd.extend(["--report-every", str(args.report_every)])
        run_step("soak-cold", cold_cmd)

    print("[verify] all checks passed")


if __name__ == "__main__":
    main()
