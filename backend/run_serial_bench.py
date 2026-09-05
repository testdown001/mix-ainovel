"""Make an offline continuous-chapter blind packet; optionally run two LLM judge passes."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.services.bench.serial_reading import SerialCase, judge_serial, write_reading_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UTF-8 JSON: common context + two aligned chapter sequences")
    parser.add_argument("--outdir", type=Path, required=True, help="New output directory; existing directories are rejected")
    parser.add_argument("--judge", action="store_true", help="Use configured default LLM for two paid, swapped-order judge calls")
    parser.add_argument("--user-id", type=int, default=0, help="LLM accounting user when --judge is enabled")
    args = parser.parse_args()
    case = SerialCase.model_validate_json(args.input.read_text(encoding="utf-8"))
    packet = write_reading_packet(case, args.outdir)
    exit_code = 0
    if args.judge:
        async def evaluate():
            from app.db.session import AsyncSessionLocal
            from app.services.llm_service import LLMService
            async with AsyncSessionLocal() as session:
                return await judge_serial(LLMService(session), packet, user_id=args.user_id)
        result = asyncio.run(evaluate())
        (args.outdir / "judge.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Judge:", result["status"])
        if result["status"] == "unavailable":
            exit_code = 2
    print("Blind reading packet:", (args.outdir / "reading.html").resolve())
    print("Share reading.html and ballot.json only; keep private/answer-key.json until voting ends.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
