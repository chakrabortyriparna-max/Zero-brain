#!/usr/bin/env python3
"""Batch run 10-point eval for all 8 skills via Cerebras with rate-limit pacing."""
import argparse
import subprocess
import sys
import time

SKILLS = [
    "codegen-assist",
    "create-second-brain-prd",
    "draft-ai-email",
    "gps-prompt-engineer",
    "learn-unfamiliar-code",
    "organize-research",
    "summarize-slack",
    "vault-structure",
]

API_KEY = "csk-mwj49xktxymkc2nx6fkttjmmyn599xpyfrr64f24crm2hdr4"
DEFAULT_MODEL = "llama3.1-8b"
DELAY = 15  # seconds between requests to stay under 5 RPM

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch run 10-point eval for all 8 skills via Cerebras")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Cerebras model ID (default: llama3.1-8b)")
    parser.add_argument("--trials", type=int, default=1, help="Trials per case (default: 1)")
    args = parser.parse_args()

    model = args.model
    trials = args.trials
    print(f"Batch evaluation: model={model}, trials={trials}")

    results = {}

    for skill in SKILLS:
        print(f"\n{'='*60}")
        print(f"Evaluating: {skill}")
        print(f"{'='*60}")

        proc = subprocess.run(
            [
                sys.executable,
                ".claude/scripts/skill_eval_full.py",
                skill,
                "--cerebras",
                "--quick",
                "--skip-harness",
                "--trials", str(trials),
                "--model", model,
            ],
            capture_output=False,
            env={**dict(subprocess.os.environ), "CEREBRAS_API_KEY": API_KEY},
        )

        results[skill] = proc.returncode == 0

        # Rate limit pacing: 15s between skills (each skill ~10-15 calls at ~1-2s each)
        if skill != SKILLS[-1]:
            print(f"[RATE LIMIT] Sleeping {DELAY}s before next skill...")
            time.sleep(DELAY)

    print(f"\n{'='*60}")
    print("BATCH EVALUATION COMPLETE")
    print(f"{'='*60}")
    for skill, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {skill}")

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)
