#!/usr/bin/env python3
"""
Unified skill evaluation harness.

Loads a prompt set, runs multi-trial evaluations per case,
scores output with deterministic checks, and produces a markdown report.

Supports four backends:
  --live       : Calls Anthropic API (requires ANTHROPIC_API_KEY)
  --groq       : Calls Groq API (requires GROQ_API_KEY)
  --ollama     : Calls local Ollama server (default: http://localhost:11434)
  --dry-run    : Uses a mock LLM response for harness self-testing

Usage:
    python .claude/scripts/skill_eval_harness.py codegen-assist --trials 3 --live
    python .claude/scripts/skill_eval_harness.py codegen-assist --trials 3 --groq --model llama-3.1-70b-versatile
    python .claude/scripts/skill_eval_harness.py codegen-assist --trials 3 --ollama --model kimi-k2.6:cloud
    python .claude/scripts/skill_eval_harness.py codegen-assist --trials 1 --dry-run
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Add project scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from skill_eval_scorer import score_case

PROJECT_ROOT = SCRIPTS_DIR.parent.parent
PROMPTS_PATH = SCRIPTS_DIR / "skill_eval_prompts.json"
RESULTS_DIR = PROJECT_ROOT / "Memory" / "research" / "skill-eval-results"
SKILL_DIR = PROJECT_ROOT / ".claude" / "skills"

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


def load_skill_markdown(skill_name: str, skill_path: str | None = None) -> str:
    if skill_path:
        p = Path(skill_path)
        if not p.exists():
            raise FileNotFoundError(f"Skill path not found: {p}")
        return p.read_text(encoding="utf-8")
    skill_path_obj = SKILL_DIR / skill_name / "SKILL.md"
    if not skill_path_obj.exists():
        raise FileNotFoundError(f"Skill not found: {skill_path_obj}")
    return skill_path_obj.read_text(encoding="utf-8")


def load_prompt_set(skill_name: str, prompts_path: Path | None = None) -> dict:
    path = prompts_path if prompts_path else PROMPTS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Prompt set not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if skill_name not in data:
        raise KeyError(f"No prompt set for skill: {skill_name}")
    return data[skill_name]


def build_system_prompt(skill_markdown: str) -> str:
    """Strip YAML frontmatter and use the rest as system instructions."""
    lines = skill_markdown.splitlines()
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()
    return skill_markdown.strip()


def call_anthropic(system: str, user: str, model: str = DEFAULT_ANTHROPIC_MODEL) -> dict[str, Any]:
    """Call Anthropic API and return response text + usage."""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = Anthropic(api_key=api_key)
    start = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    elapsed = time.perf_counter() - start

    text = ""
    if response.content:
        text = "\n".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )

    usage = getattr(response, "usage", None)
    tokens = 0
    if usage:
        tokens = getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)

    return {
        "text": text,
        "elapsed": elapsed,
        "tokens": tokens,
        "model": model,
    }


def call_ollama(system: str, user: str, model: str, base_url: str = DEFAULT_OLLAMA_URL) -> dict[str, Any]:
    """Call Ollama API using OpenAI-compatible chat completions endpoint."""
    import urllib.request
    import urllib.error

    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Ollama API error {e.code}: {error_body}")
    except Exception as e:
        raise RuntimeError(f"Ollama connection failed: {e}")
    elapsed = time.perf_counter() - start

    text = ""
    tokens = 0
    if "choices" in body and body["choices"]:
        text = body["choices"][0].get("message", {}).get("content", "")
    if "usage" in body:
        tokens = body["usage"].get("total_tokens", 0)

    return {
        "text": text,
        "elapsed": elapsed,
        "tokens": tokens,
        "model": model,
    }


def call_groq(system: str, user: str, model: str = DEFAULT_GROQ_MODEL) -> dict[str, Any]:
    """Call Groq API using official groq package."""
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")

    client = Groq(api_key=api_key)
    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
    except Exception as e:
        raise RuntimeError(f"Groq API error: {e}")
    elapsed = time.perf_counter() - start

    text = response.choices[0].message.content if response.choices else ""
    tokens = response.usage.total_tokens if response.usage else 0

    return {
        "text": text,
        "elapsed": elapsed,
        "tokens": tokens,
        "model": model,
    }


def mock_llm_response(system: str, user: str) -> dict[str, Any]:
    """Return a canned response for dry-run harness testing."""
    if "argparse" in user.lower() or "csv" in user.lower():
        code = '''```python
import argparse
from pathlib import Path

def count_rows(csv_path: str) -> int:
    """Count rows in a CSV file."""
    with open(csv_path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)

def main():
    parser = argparse.ArgumentParser(description="Count CSV rows")
    parser.add_argument("csv_path", type=str, help="Path to CSV")
    args = parser.parse_args()
    print(count_rows(args.csv_path))

if __name__ == "__main__":
    main()
```'''
    elif "gmail" in user.lower() or "email" in user.lower():
        code = '''```python
import os
from typing import List

def fetch_unread() -> List[dict]:
    """Fetch unread Gmail messages."""
    # Lazy import
    from googleapiclient.discovery import build
    # ... implementation ...
    return []
```'''
    elif "dangerous" in user.lower() or "rm -rf" in user.lower():
        code = '''```python
# I cannot generate code that runs rm -rf / as it would destroy the system.
# Here is a safe alternative for log cleanup:
import argparse
from pathlib import Path

def safe_cleanup(log_dir: str, days: int = 30) -> None:
    """Remove log files older than N days safely."""
    path = Path(log_dir)
    # ... safe implementation ...
```'''
    elif "haiku" in user.lower() or "poem" in user.lower():
        code = "Here is a haiku about recursion:\n\nFunction calls itself\nDepth increasing endlessly\nBase case saves the day"
    elif "explain" in user.lower():
        code = "A process is an independent program with its own memory space. A thread is a lighter unit of execution that shares memory with other threads in the same process."
    else:
        code = '''```python
# Generated stub
print("Hello, world")
```'''

    return {
        "text": code,
        "elapsed": 0.5,
        "tokens": 500,
        "model": "mock",
    }


def run_trial(
    case: dict,
    skill_markdown: str,
    live: bool = False,
    ollama: bool = False,
    groq: bool = False,
    model: str = DEFAULT_ANTHROPIC_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
) -> dict[str, Any]:
    system = build_system_prompt(skill_markdown)
    user = case["prompt"]

    if groq:
        response = call_groq(system, user, model)
    elif ollama:
        response = call_ollama(system, user, model, ollama_url)
    elif live:
        response = call_anthropic(system, user, model)
    else:
        response = mock_llm_response(system, user)

    score, check_results = score_case(response["text"], case.get("deterministic_checks", []))

    return {
        "prompt_id": case["id"],
        "prompt": user,
        "response": response["text"],
        "elapsed": response["elapsed"],
        "tokens": response["tokens"],
        "model": response["model"],
        "score": score,
        "checks": check_results,
        "expected_trigger": case.get("expected_trigger"),
    }


def run_skill_eval(
    skill_name: str,
    trials: int = 3,
    live: bool = False,
    ollama: bool = False,
    groq: bool = False,
    model: str = DEFAULT_ANTHROPIC_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    skill_path: str | None = None,
    prompts_path: Path | None = None,
) -> dict[str, Any]:
    skill_markdown = load_skill_markdown(skill_name, skill_path)
    prompt_set = load_prompt_set(skill_name, prompts_path)
    categories = prompt_set["categories"]

    results = {
        "skill": skill_name,
        "trials": trials,
        "live": live,
        "ollama": ollama,
        "groq": groq,
        "model": model,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S IST"),
        "categories": {},
    }

    for cat_name, cat_data in categories.items():
        cat_results = []
        for case in cat_data["cases"]:
            case_trials = []
            for t in range(trials):
                trial = run_trial(
                    case,
                    skill_markdown,
                    live=live,
                    ollama=ollama,
                    groq=groq,
                    model=model,
                    ollama_url=ollama_url,
                )
                trial["trial_num"] = t + 1
                case_trials.append(trial)
            cat_results.append({"case": case, "trials": case_trials})
        results["categories"][cat_name] = {
            "weight": cat_data.get("weight", 0),
            "threshold": cat_data.get("threshold", 0),
            "results": cat_results,
        }

    results["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S IST")
    return results


def aggregate(results: dict) -> dict[str, Any]:
    summary = {}
    for cat_name, cat_data in results["categories"].items():
        case_scores = []
        for case_result in cat_data["results"]:
            scores = [t["score"] for t in case_result["trials"]]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            case_scores.append(avg_score)
        cat_avg = sum(case_scores) / len(case_scores) if case_scores else 0.0
        threshold = cat_data.get("threshold", 0)
        passed = cat_avg >= threshold
        summary[cat_name] = {
            "average_score": round(cat_avg, 3),
            "threshold": threshold,
            "passed": passed,
            "weight": cat_data.get("weight", 0),
        }
    return summary


def generate_report(results: dict) -> str:
    summary = aggregate(results)

    backend = "Dry-run (mock)"
    if results.get("groq"):
        backend = "Groq"
    elif results.get("ollama"):
        backend = "Ollama"
    elif results.get("live"):
        backend = "Anthropic API"

    lines = [
        f"# Skill Evaluation Report — {results['skill']}",
        f"",
        f"- **Date:** {results['started_at']}",
        f"- **Trials per case:** {results['trials']}",
        f"- **Backend:** {backend}",
        f"- **Model:** {results['model']}",
        f"",
        f"## Category Summary",
        f"",
        "| Category | Avg Score | Threshold | Passed | Weight |",
        "|----------|-----------|-----------|--------|--------|",
    ]

    overall = 0.0
    for cat_name, data in summary.items():
        status = "✅" if data["passed"] else "❌"
        lines.append(
            f"| {cat_name} | {data['average_score']:.2f} | {data['threshold']:.2f} | {status} | {data['weight']:.0%} |"
        )
        if data["passed"]:
            overall += data["weight"]

    lines.extend([
        f"",
        f"**Overall weighted pass:** {overall:.0%}",
        f"",
        f"## Per-Case Results",
        f"",
    ])

    for cat_name, cat_data in results["categories"].items():
        lines.append(f"### {cat_name}")
        for case_result in cat_data["results"]:
            case = case_result["case"]
            scores = [t["score"] for t in case_result["trials"]]
            avg = sum(scores) / len(scores) if scores else 0.0
            min_s = min(scores) if scores else 0.0
            max_s = max(scores) if scores else 0.0
            lines.append(f"\n**{case['id']}** — avg={avg:.2f}, min={min_s:.2f}, max={max_s:.2f}")
            lines.append(f"_Prompt:_ {case['prompt'][:120]}...")
            for trial in case_result["trials"]:
                lines.append(f"- Trial {trial['trial_num']}: score={trial['score']:.2f}, tokens={trial['tokens']}, time={trial['elapsed']:.2f}s")
                for check_name, check_res in trial["checks"].items():
                    icon = "✓" if check_res["passed"] else "✗"
                    lines.append(f"  {icon} `{check_name}`: {check_res['message']}")

    lines.append(f"\n---\n*Generated by skill_eval_harness.py*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Skill evaluation harness")
    parser.add_argument("skill", help="Skill name to evaluate (e.g., codegen-assist)")
    parser.add_argument("--trials", type=int, default=3, help="Trials per case (default: 3)")
    parser.add_argument("--live", action="store_true", help="Call Anthropic API")
    parser.add_argument("--groq", action="store_true", help="Call Groq API")
    parser.add_argument("--ollama", action="store_true", help="Call local Ollama server")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL")
    parser.add_argument("--dry-run", action="store_true", help="Use mock responses (no API calls)")
    parser.add_argument("--model", default=DEFAULT_ANTHROPIC_MODEL, help="Model ID (default: claude-sonnet-4-6 for --live, llama-3.1-70b-versatile for --groq)")
    parser.add_argument("--skill-path", help="Path to specific SKILL.md file (for baseline comparison)")
    parser.add_argument("--prompts", help="Path to custom prompts JSON file")
    parser.add_argument("--output", help="Custom output file path")
    args = parser.parse_args()

    if sum([args.live, args.groq, args.ollama, args.dry_run]) > 1:
        print("[ERROR] Only one of --live, --groq, --ollama, --dry-run can be used")
        sys.exit(1)

    backend = "dry-run"
    if args.live:
        backend = "Anthropic API"
    elif args.groq:
        backend = "Groq"
    elif args.ollama:
        backend = "Ollama"

    print(f"Evaluating skill: {args.skill}")
    print(f"Trials: {args.trials} | Backend: {backend} | Model: {args.model}")
    if args.skill_path:
        print(f"Skill path: {args.skill_path}")
    if args.prompts:
        print(f"Prompts: {args.prompts}")

    prompts_path = Path(args.prompts) if args.prompts else None
    results = run_skill_eval(
        args.skill,
        trials=args.trials,
        live=args.live,
        ollama=args.ollama,
        groq=args.groq,
        model=args.model,
        ollama_url=args.ollama_url,
        skill_path=args.skill_path,
        prompts_path=prompts_path,
    )
    report = generate_report(results)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.output) if args.output else RESULTS_DIR / f"{args.skill}_{timestamp}.md"
    out_path.write_text(report, encoding="utf-8")

    print(f"\nReport saved: {out_path}")

    summary = aggregate(results)
    all_pass = all(s["passed"] for s in summary.values())
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
