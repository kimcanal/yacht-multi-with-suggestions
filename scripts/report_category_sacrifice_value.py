#!/usr/bin/env python3
"""Report exact opportunity costs of zero-closing Yacht categories.

Unlike ``estimate_closing_costs.py``, this tool does not roll out a learned
policy.  It reads the full-game exact value table, so every reported number is
the expected-score loss of removing one still-open category from one exact
scorecard state.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.value.endgame import (
    DEFAULT_ENDGAME_VALUE_TABLE_PATH,
    EndgameValueTable,
    capped_upper_total,
    closed_mask_from_scorecard,
    load_endgame_value_table,
    yacht_bonus_available,
)
from yacht_core.constants import CATEGORY_NAMES


@dataclass(frozen=True)
class Profile:
    """A scorecard state used to make category values comparable."""

    slug: str
    title: str
    description: str
    scorecard: tuple[int | None, ...]


PROFILES = (
    Profile(
        slug="opening",
        title="초반: 빈 점수판",
        description="12칸이 모두 열려 있고 Upper Bonus 진행도는 0점이다.",
        scorecard=(None,) * 12,
    ),
    Profile(
        slug="bonus-race",
        title="중반: Upper Bonus 마감권",
        description="Ones~Fives로 57점을 쌓았고 Sixes와 모든 하단 칸이 열려 있다.",
        scorecard=(3, 8, 9, 12, 25, None, None, None, None, None, None, None),
    ),
    Profile(
        slug="late-three",
        title="후반: Ones·Large Straight·Yacht만 남음",
        description="상단은 58점이며, 남은 세 칸 중 무엇을 0점으로 닫을지 비교하는 상태다.",
        scorecard=(None, 4, 9, 12, 15, 18, 0, 0, 0, 0, None, None),
    ),
)


def analyze_profile(profile: Profile, table: EndgameValueTable) -> dict:
    """Return the exact value lost by zero-closing every open category."""
    scorecard = profile.scorecard
    base_mask = closed_mask_from_scorecard(scorecard)
    upper_total = capped_upper_total(scorecard)
    yacht_bonus = yacht_bonus_available(scorecard)
    baseline = table.lookup_state(base_mask, upper_total, yacht_bonus)
    if baseline is None:
        raise ValueError(f"value table has no entry for profile {profile.slug}")

    rows = []
    for category_idx, category_name in enumerate(CATEGORY_NAMES):
        if scorecard[category_idx] is not None:
            continue
        after_zero = table.lookup_state(base_mask | (1 << category_idx), upper_total, yacht_bonus)
        if after_zero is None:
            raise ValueError(
                f"value table has no state after closing {category_name} in profile {profile.slug}"
            )
        rows.append({
            "category": category_name,
            "category_idx": category_idx,
            "remaining_ev_after_zero": float(after_zero),
            "zero_close_cost": float(baseline - after_zero),
        })

    rows.sort(key=lambda row: (-row["zero_close_cost"], row["category_idx"]))
    return {
        "slug": profile.slug,
        "title": profile.title,
        "description": profile.description,
        "upper_total": upper_total,
        "yacht_bonus_available": yacht_bonus,
        "baseline_remaining_ev": float(baseline),
        "rows": rows,
    }


def render_markdown(reports: list[dict], table_path: str) -> str:
    lines = [
        "# 상태별 족보 희생 비용 리포트",
        "",
        "이 리포트의 숫자는 full-game exact value table에서 직접 조회한다. 각 상태의 `0점 종료 비용`은 "
        "그 칸을 지금 0점으로 닫기 전후의 남은 게임 기대점수 차이다.",
        "",
        "```text",
        "0점 종료 비용 = V(현재 점수판) - V(해당 칸을 0점으로 닫은 뒤 점수판)",
        "```",
        "",
        "따라서 숫자가 클수록 그 칸을 희생했을 때 잃는 장기 가치가 크다. 이는 특정 주사위 패에서의 "
        "‘지금 기록’ 추천이 아니라, 점수판 상태만 놓고 본 족보 보존 가치다.",
        "",
        f"- Value table: `{table_path}`",
        "- 생성 명령: `python scripts/report_category_sacrifice_value.py --markdown-output docs/category-sacrifice-value-report.md`",
        "",
    ]
    for report in reports:
        lines.extend([
            f"## {report['title']}",
            "",
            report["description"],
            "",
            f"- 현재 상단 합계: `{report['upper_total']}/63`",
            f"- Yacht Bonus 가능: `{'예' if report['yacht_bonus_available'] else '아니오'}`",
            f"- 아무 칸도 희생하지 않았을 때 남은 게임 EV: `{report['baseline_remaining_ev']:.3f}점`",
            "",
            "| 0점으로 닫는 칸 | 남은 게임 EV | 0점 종료 비용 |",
            "| --- | ---: | ---: |",
        ])
        for row in report["rows"]:
            lines.append(
                f"| {row['category']} | {row['remaining_ev_after_zero']:.3f}점 | "
                f"{row['zero_close_cost']:.3f}점 |"
            )
        lines.append("")

    lines.extend([
        "## 읽는 법",
        "",
        "- **고정 우선순위가 아니다.** 예를 들어 Sixes의 비용은 Upper Bonus 마감권에서 커질 수 있고, "
        "후반에는 남은 칸 수 자체가 판단을 바꾼다.",
        "- **실전 기록은 이 표보다 더 많은 정보를 쓴다.** 실제 최적 모드는 현재 주사위, 즉시 점수, Upper Bonus "
        "확정 여부, Yacht Bonus까지 더해 각 기록 행동을 비교한다.",
        "- **희생 후보는 비용이 낮은 쪽부터 검토한다.** 단, 현재 패로 높은 점수를 기록할 수 있다면 0점 희생보다 "
        "그 기록의 전체 기대가치가 우선될 수 있다.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report exact category zero-close costs by scorecard state.")
    parser.add_argument("--value-table", default=DEFAULT_ENDGAME_VALUE_TABLE_PATH)
    parser.add_argument("--profile", action="append", choices=[profile.slug for profile in PROFILES])
    parser.add_argument("--markdown-output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected = set(args.profile or [profile.slug for profile in PROFILES])
    reports = [analyze_profile(profile, load_endgame_value_table(args.value_table)) for profile in PROFILES if profile.slug in selected]
    markdown = render_markdown(reports, args.value_table)
    print(markdown)
    if args.markdown_output:
        output_path = Path(args.markdown_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
