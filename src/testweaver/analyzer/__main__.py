"""analyzer 를 단독으로 돌려 보는 진입점.

    uv run python -m testweaver.analyzer <프로젝트 경로>
    uv run python -m testweaver.analyzer <프로젝트 경로> -o analysis.json

CLI 전체(`testweaver` 명령)는 별도 담당 영역이라, 여기서는 analyzer 출력만
확인하고 넘겨줄 수 있게 한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from testweaver.analyzer.models import AnalysisResult, NoteLevel
from testweaver.analyzer.pipeline import analyze_project
from testweaver.analyzer.serialize import dumps, write_analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m testweaver.analyzer",
        description="FastAPI 프로젝트를 정적 분석해 기능 목록을 뽑는다.",
    )
    parser.add_argument("project_root", type=Path, help="분석할 프로젝트 경로")
    parser.add_argument(
        "-o", "--output", type=Path, help="JSON 을 저장할 파일 (없으면 표준출력)"
    )
    parser.add_argument(
        "-s", "--summary", action="store_true", help="JSON 대신 요약만 출력"
    )
    args = parser.parse_args(argv)

    result = analyze_project(args.project_root)

    if args.summary:
        print(summarize(result))
    elif args.output:
        print(f"저장됨: {write_analysis(result, args.output)}")
    else:
        print(dumps(result))

    return 1 if any(n.level is NoteLevel.ERROR for n in result.notes) else 0


def summarize(result: AnalysisResult) -> str:
    """무엇을 뽑았고 무엇을 못 뽑았는지 한눈에 보여 준다."""
    constraints = [c for f in result.features for c in f.constraints]
    exceptions = [e for f in result.features for e in f.endpoint.exceptions]
    by_location: dict[str, int] = {}
    for constraint in constraints:
        by_location[constraint.location.value] = (
            by_location.get(constraint.location.value, 0) + 1
        )

    lines = [
        f"기능        {len(result.features)}",
        f"제약        {len(constraints)}  ({_counts(by_location)})",
        f"예외        {len(exceptions)}  (상태코드 미확정 {sum(1 for e in exceptions if not e.resolved)})",
        f"인증 필요   {sum(1 for f in result.features if f.endpoint.requires_auth)}",
        f"권한 필요   {sum(1 for f in result.features if f.endpoint.requires_permission)}",
    ]

    if result.notes:
        lines.append("")
        lines.append(f"해석하지 못한 지점 {len(result.notes)}건")
        by_code: dict[str, int] = {}
        for note in result.notes:
            by_code[note.code.value] = by_code.get(note.code.value, 0) + 1
        lines.extend(f"  {code:<22} {count}" for code, count in sorted(by_code.items()))
    return "\n".join(lines)


def _counts(mapping: dict[str, int]) -> str:
    return ", ".join(f"{key} {value}" for key, value in sorted(mapping.items()))


if __name__ == "__main__":
    sys.exit(main())
