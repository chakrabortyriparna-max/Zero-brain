#!/usr/bin/env python3
"""
10-Point Skill Evaluation Framework

Implements all ten best practices for evaluating Claude Code skills:

1. Skill description trigger check        — analyze SKILL.md frontmatter
2. Directives vs information              — scan for imperative vs passive language
3. Negative tests                         — prompts that should NOT trigger the skill
4. Extend from failures                   — re-run previously failed cases
5. Grade outcomes, not paths              — deterministic outcome-based scoring
6. Isolate each run                       — verify no context bleeding between trials
7. Multiple trials                        — 3+ trials per case, look at distribution
8. Test across harnesses                  — loaded skill vs generic prompt
9. Graduate evals                         — capability → regression transition tracking
10. Detect skill retirement               — loaded vs unloaded comparison

Usage:
    python .claude/scripts/skill_eval_full.py codegen-assist --groq --trials 3
    python .claude/scripts/skill_eval_full.py codegen-assist --dry-run
    python .claude/scripts/skill_eval_full.py codegen-assist --skill-only  # points 1-2 only

Exit codes:
    0 = all critical points passed
    1 = one or more critical points failed (blocks git commit)
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# Import existing harness
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from skill_eval_harness import (
    load_skill_markdown,
    load_prompt_set,
    build_system_prompt,
    call_groq,
    call_ollama,
    call_anthropic,
    mock_llm_response,
    run_trial,
    aggregate,
    RESULTS_DIR,
    SKILL_DIR,
    DEFAULT_GROQ_MODEL,
)
from skill_eval_scorer import score_case

HISTORY_PATH = SCRIPTS_DIR / "skill_eval_history.json"
FAILURES_PATH = SCRIPTS_DIR / "skill_eval_failures.json"
GENERIC_SYSTEM = "You are a helpful assistant."

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {}


def _ensure_failures() -> dict:
    if FAILURES_PATH.exists():
        return json.loads(FAILURES_PATH.read_text(encoding="utf-8"))
    return {}


def _save_history(data: dict):
    HISTORY_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _save_failures(data: dict):
    FAILURES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _extract_yaml_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            try:
                import yaml
                return yaml.safe_load("\n".join(lines[1:i])) or {}
            except ImportError:
                # Fallback: naive key-value parsing
                result = {}
                for kv in lines[1:i]:
                    if ":" in kv:
                        k, v = kv.split(":", 1)
                        result[k.strip()] = v.strip().strip('"').strip("'")
                return result
    return {}

# ---------------------------------------------------------------------------
# Point 1: Skill Description Trigger Check
# ---------------------------------------------------------------------------

def eval_point1(skill_markdown: str) -> dict[str, Any]:
    """Analyze SKILL.md description for specificity and trigger clarity."""
    fm = _extract_yaml_frontmatter(skill_markdown)
    description = fm.get("description", "")
    name = fm.get("name", "")
    body = skill_markdown.split("---", 2)[-1] if "---" in skill_markdown else skill_markdown

    issues = []
    score = 1.0

    # Check name exists
    if not name:
        issues.append("Missing 'name' in YAML frontmatter")
        score -= 0.25

    # Check description length (vague = short)
    word_count = len(description.split())
    if word_count < 15:
        issues.append(f"Description too short ({word_count} words); triggers may be vague")
        score -= 0.25
    elif word_count > 100:
        issues.append(f"Description very long ({word_count} words); may be too broad")
        score -= 0.1

    # Check for explicit trigger phrases
    trigger_keywords = ["trigger", "activates on", "fires when", "ONLY when", "STRICT"]
    has_triggers = any(kw.lower() in description.lower() for kw in trigger_keywords)
    if not has_triggers:
        issues.append("No explicit trigger mechanism in description; add 'STRICT trigger list ONLY activates on...'")
        score -= 0.25

    # Check for negative triggers in body
    negative_sections = ["negative trigger", "must not trigger", "never triggers on", "does not fire"]
    has_negative = any(ns in body.lower() for ns in negative_sections)
    if not has_negative:
        issues.append("No negative trigger section found; skill may fire on wrong requests")
        score -= 0.15

    # Check for explicit language (STRICT, ONLY, NEVER, MUST)
    directive_words = ["strict", "only", "never", "must not", "must"]
    directive_count = sum(1 for w in directive_words if w in description.lower())
    if directive_count < 2:
        issues.append(f"Description lacks directive language ({directive_count}/2 directive words)")
        score -= 0.1

    return {
        "point": 1,
        "title": "Skill Description Trigger Check",
        "score": max(0.0, round(score, 2)),
        "passed": score >= 0.8,
        "details": {
            "word_count": word_count,
            "has_explicit_triggers": has_triggers,
            "has_negative_triggers": has_negative,
            "directive_count": directive_count,
            "issues": issues,
        },
    }


# ---------------------------------------------------------------------------
# Point 2: Directives vs Information
# ---------------------------------------------------------------------------

def eval_point2(skill_markdown: str) -> dict[str, Any]:
    """Scan for imperative directives vs passive informational language."""
    body = skill_markdown.split("---", 2)[-1] if "---" in skill_markdown else skill_markdown
    body_lower = body.lower()

    # Imperative / directive patterns
    directives = [
        r"\balways\b", r"\bnever\b", r"\bmust\b", r"\bmust not\b",
        r"\bstop\b", r"\bdo not\b", r"\brequire\b", r"\buse\b (?=\w+)",
        r"\bread from\b", r"\bvalidate\b", r"\bcheck\b (?=\w+)",
    ]
    # Passive / informational patterns
    passive = [
        r"is the recommended", r"it is suggested", r"consider using",
        r"you might want", r"can be used", r"is a good idea",
        r"generally", r"typically", r"usually",
    ]

    directive_hits = sum(1 for pat in directives if re.search(pat, body_lower))
    passive_hits = sum(1 for pat in passive if re.search(pat, body_lower))

    issues = []
    score = 1.0

    if directive_hits < 5:
        issues.append(f"Too few directives ({directive_hits}); models follow instructions, not implications")
        score -= 0.3
    if passive_hits > 0:
        issues.append(f"Found {passive_hits} passive phrase(s); replace with imperatives")
        score -= 0.2 * passive_hits

    # Bonus: check coding standards section uses numbers 1. 2. 3. (clear directives)
    has_numbered_directives = bool(re.search(r"\n\d+\.\s+\*\*[A-Z]", body))
    if not has_numbered_directives:
        issues.append("No numbered imperative list (e.g., '1. **ALWAYS** ...') found")
        score -= 0.1

    return {
        "point": 2,
        "title": "Directives vs Information",
        "score": max(0.0, round(score, 2)),
        "passed": score >= 0.8,
        "details": {
            "directive_hits": directive_hits,
            "passive_hits": passive_hits,
            "has_numbered_directives": has_numbered_directives,
            "issues": issues,
        },
    }


# ---------------------------------------------------------------------------
# Point 3: Negative Tests
# Point 4: Extend from Failures
# Point 5: Grade outcomes, not paths (handled by scorer)
# Point 6: Isolate each run
# Point 7: Multiple trials
# ---------------------------------------------------------------------------

def eval_point3_to_7(
    skill_name: str,
    prompt_set: dict,
    skill_markdown: str,
    trials: int,
    backend_fn,
    model: str = DEFAULT_GROQ_MODEL,
) -> dict[str, Any]:
    """Run prompt-based evaluations: negative tests, failure extension, isolation, multiple trials."""
    categories = prompt_set.get("categories", {})
    results = {}
    all_trials = []

    # Load previous failures for Point 4
    failures_db = _ensure_failures()
    prev_failures = failures_db.get(skill_name, [])
    failure_case_ids = {f["case_id"] for f in prev_failures}

    for cat_name, cat_data in categories.items():
        cat_results = []
        for case in cat_data.get("cases", []):
            case_id = case["id"]
            case_trials = []
            for t in range(trials):
                trial = run_trial(
                    case,
                    skill_markdown,
                    groq=backend_fn == call_groq,
                    ollama=backend_fn == call_ollama,
                    live=backend_fn == call_anthropic,
                    model=model if backend_fn == call_groq else "mock",
                )
                trial["trial_num"] = t + 1
                case_trials.append(trial)
            cat_results.append({"case": case, "trials": case_trials})
            all_trials.extend(case_trials)
        results[cat_name] = cat_results

    # Point 3: Negative test scoring
    negative_cases = results.get("negative", [])
    neg_passed = 0
    neg_total = 0
    for cr in negative_cases:
        expected_trigger = cr["case"].get("expected_trigger", True)
        scores = [t["score"] for t in cr["trials"]]
        avg = sum(scores) / len(scores) if scores else 0.0
        neg_total += 1
        if expected_trigger is False and avg >= 0.99:
            neg_passed += 1

    # Point 4: Failure extension
    failure_regressions = []
    failure_fixes = []
    for cat_name, cat_results in results.items():
        for cr in cat_results:
            case_id = cr["case"]["id"]
            if case_id in failure_case_ids:
                scores = [t["score"] for t in cr["trials"]]
                avg = sum(scores) / len(scores) if scores else 0.0
                if avg < 1.0:
                    failure_regressions.append(case_id)
                else:
                    failure_fixes.append(case_id)

    # Point 6: Isolation check — compare trial distributions
    isolation_issues = []
    for cat_name, cat_results in results.items():
        for cr in cat_results:
            scores = [t["score"] for t in cr["trials"]]
            if len(scores) > 1:
                spread = max(scores) - min(scores)
                if spread > 0.5:
                    isolation_issues.append(
                        f"{cr['case']['id']}: high variance across trials ({spread:.2f}); possible context bleed or non-determinism"
                    )

    # Point 7: Multiple trials summary
    trial_summary = {}
    for cat_name, cat_results in results.items():
        cat_scores = []
        for cr in cat_results:
            scores = [t["score"] for t in cr["trials"]]
            avg = sum(scores) / len(scores) if scores else 0.0
            cat_scores.append(avg)
        trial_summary[cat_name] = {
            "avg": round(sum(cat_scores) / len(cat_scores), 2) if cat_scores else 0.0,
            "min": round(min(cat_scores), 2) if cat_scores else 0.0,
            "max": round(max(cat_scores), 2) if cat_scores else 0.0,
        }

    # Overall score for points 3-7 combined
    # Point 3 weight: 30%, Point 4 weight: 20%, Point 6 weight: 20%, Point 7 weight: 30%
    p3_score = neg_passed / neg_total if neg_total else 1.0
    p4_score = 1.0 if not failure_case_ids else (len(failure_fixes) / len(failure_case_ids))
    p6_score = 1.0 if not isolation_issues else max(0.0, 1.0 - (len(isolation_issues) * 0.2))
    p7_score = sum(s["avg"] for s in trial_summary.values()) / len(trial_summary) if trial_summary else 0.0

    combined_score = (p3_score * 0.30) + (p4_score * 0.20) + (p6_score * 0.20) + (p7_score * 0.30)

    return {
        "point": "3-7",
        "title": "Prompt-Based Evaluation Suite (Negative, Failures, Isolation, Trials)",
        "score": round(combined_score, 2),
        "passed": combined_score >= 0.8,
        "details": {
            "negative": {"passed": neg_passed, "total": neg_total, "score": p3_score},
            "failure_extension": {"previous_failures": list(failure_case_ids), "regressions": failure_regressions, "fixes": failure_fixes, "score": p4_score},
            "isolation": {"issues": isolation_issues, "score": p6_score},
            "trial_summary": trial_summary,
            "score": p7_score,
        },
        "raw_results": results,
    }


# ---------------------------------------------------------------------------
# Point 8: Test Across Harnesses (loaded vs unloaded)
# ---------------------------------------------------------------------------

def eval_point8(
    skill_name: str,
    prompt_set: dict,
    skill_markdown: str,
    trials: int,
    backend_fn,
    model: str = DEFAULT_GROQ_MODEL,
) -> dict[str, Any]:
    """Compare skill-loaded vs generic-unloaded performance."""
    categories = prompt_set.get("categories", {})
    # Use core cases for harness comparison
    core_cases = []
    for cat_data in categories.values():
        for case in cat_data.get("cases", []):
            if case.get("id", "").startswith("core-"):
                core_cases.append(case)

    if not core_cases:
        return {
            "point": 8,
            "title": "Test Across Harnesses",
            "score": 0.0,
            "passed": False,
            "details": {"issues": ["No core cases found for harness comparison"]},
        }

    loaded_scores = []
    unloaded_scores = []

    for case in core_cases:
        for t in range(trials):
            # Loaded
            loaded = run_trial(
                case, skill_markdown,
                groq=backend_fn == call_groq,
                ollama=backend_fn == call_ollama,
                live=backend_fn == call_anthropic,
                model=model if backend_fn == call_groq else "mock",
            )
            loaded_scores.append(loaded["score"])

            # Unloaded (generic system prompt)
            case_generic = dict(case)
            case_generic["prompt"] = case["prompt"]
            unloaded = run_trial(
                case_generic, GENERIC_SYSTEM,
                groq=backend_fn == call_groq,
                ollama=backend_fn == call_ollama,
                live=backend_fn == call_anthropic,
                model=model if backend_fn == call_groq else "mock",
            )
            unloaded_scores.append(unloaded["score"])

    avg_loaded = sum(loaded_scores) / len(loaded_scores) if loaded_scores else 0.0
    avg_unloaded = sum(unloaded_scores) / len(unloaded_scores) if unloaded_scores else 0.0
    delta = avg_loaded - avg_unloaded

    issues = []
    score = 1.0
    if delta < 0.1:
        issues.append(f"Skill adds minimal value (delta={delta:.2f}); consider tightening description or directives")
        score -= 0.4
    if avg_loaded < 0.6:
        issues.append(f"Loaded skill scores low ({avg_loaded:.2f}); skill needs improvement")
        score -= 0.3

    return {
        "point": 8,
        "title": "Test Across Harnesses",
        "score": max(0.0, round(score, 2)),
        "passed": score >= 0.7,
        "details": {
            "avg_loaded": round(avg_loaded, 2),
            "avg_unloaded": round(avg_unloaded, 2),
            "delta": round(delta, 2),
            "issues": issues,
        },
    }


# ---------------------------------------------------------------------------
# Point 9: Graduate Evals
# ---------------------------------------------------------------------------

def eval_point9(skill_name: str, current_score: float) -> dict[str, Any]:
    """Track pass rate trends and determine if eval should graduate to regression."""
    history = _ensure_history()
    skill_history = history.get(skill_name, [])

    # Add current run
    skill_history.append({
        "date": time.strftime("%Y-%m-%d %H:%M:%S IST"),
        "score": round(current_score, 2),
    })
    history[skill_name] = skill_history[-10:]  # keep last 10
    _save_history(history)

    if len(skill_history) < 2:
        return {
            "point": 9,
            "title": "Graduate Evals",
            "score": 0.5,
            "passed": True,
            "details": {
                "status": "capability",
                "runs": len(skill_history),
                "message": "Need 2+ runs to detect graduation trend",
            },
        }

    scores = [h["score"] for h in skill_history]
    avg_score = sum(scores) / len(scores)
    trend = scores[-1] - scores[0]

    status = "capability"
    if avg_score >= 0.95:
        status = "regression"
    elif avg_score >= 0.85:
        status = "graduating"

    return {
        "point": 9,
        "title": "Graduate Evals",
        "score": round(avg_score, 2),
        "passed": status in ("graduating", "regression") or trend > 0,
        "details": {
            "status": status,
            "runs": len(skill_history),
            "avg_score": round(avg_score, 2),
            "trend": round(trend, 2),
            "message": f"Eval status: {status}. Trend: {trend:+.2f} over {len(scores)} runs.",
        },
    }


# ---------------------------------------------------------------------------
# Point 10: Detect Skill Retirement
# ---------------------------------------------------------------------------

def eval_point10(
    skill_name: str,
    prompt_set: dict,
    skill_markdown: str,
    trials: int,
    backend_fn,
    model: str = DEFAULT_GROQ_MODEL,
) -> dict[str, Any]:
    """If unloaded results are close to loaded, the model may have absorbed the skill."""
    categories = prompt_set.get("categories", {})
    core_cases = []
    for cat_data in categories.values():
        for case in cat_data.get("cases", []):
            if case.get("id", "").startswith("core-"):
                core_cases.append(case)

    if not core_cases:
        return {
            "point": 10,
            "title": "Detect Skill Retirement",
            "score": 1.0,
            "passed": True,
            "details": {"message": "No core cases; retirement detection skipped"},
        }

    loaded_scores = []
    unloaded_scores = []

    for case in core_cases:
        for t in range(min(trials, 2)):  # fewer trials for retirement check (cost)
            loaded = run_trial(
                case, skill_markdown,
                groq=backend_fn == call_groq,
                ollama=backend_fn == call_ollama,
                live=backend_fn == call_anthropic,
                model=model if backend_fn == call_groq else "mock",
            )
            loaded_scores.append(loaded["score"])

            case_generic = dict(case)
            unloaded = run_trial(
                case_generic, GENERIC_SYSTEM,
                groq=backend_fn == call_groq,
                ollama=backend_fn == call_ollama,
                live=backend_fn == call_anthropic,
                model=model if backend_fn == call_groq else "mock",
            )
            unloaded_scores.append(unloaded["score"])

    avg_loaded = sum(loaded_scores) / len(loaded_scores) if loaded_scores else 0.0
    avg_unloaded = sum(unloaded_scores) / len(unloaded_scores) if unloaded_scores else 0.0

    # If unloaded is >= 90% of loaded, skill may be absorbed
    if avg_loaded > 0:
        absorption_ratio = avg_unloaded / avg_loaded
    else:
        absorption_ratio = 0.0

    should_retire = absorption_ratio >= 0.90 and avg_loaded >= 0.8
    score = 1.0 if not should_retire else 0.0

    return {
        "point": 10,
        "title": "Detect Skill Retirement",
        "score": score,
        "passed": not should_retire,
        "details": {
            "avg_loaded": round(avg_loaded, 2),
            "avg_unloaded": round(avg_unloaded, 2),
            "absorption_ratio": round(absorption_ratio, 2),
            "should_retire": should_retire,
            "message": (
                "Skill appears absorbed by model — consider retirement."
                if should_retire else
                "Skill provides clear value over generic baseline."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Failure tracking: update failures DB from raw results
# ---------------------------------------------------------------------------

def update_failures(skill_name: str, raw_results: dict):
    failures_db = _ensure_failures()
    skill_failures = []
    for cat_name, cat_results in raw_results.items():
        for cr in cat_results:
            case = cr["case"]
            case_id = case["id"]
            for t in cr["trials"]:
                for check_name, check_res in t["checks"].items():
                    if not check_res["passed"]:
                        skill_failures.append({
                            "case_id": case_id,
                            "check": check_name,
                            "trial": t["trial_num"],
                            "message": check_res["message"],
                            "first_seen": time.strftime("%Y-%m-%d"),
                            "status": "open",
                        })
    # Deduplicate by case_id+check
    seen = set()
    unique = []
    for f in skill_failures:
        key = f"{f['case_id']}:{f['check']}"
        if key not in seen:
            seen.add(key)
            unique.append(f)
    failures_db[skill_name] = unique
    _save_failures(failures_db)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_10point_report(skill_name: str, results: list[dict], overall_passed: bool) -> str:
    lines = [
        f"# 10-Point Skill Evaluation Report — {skill_name}",
        f"",
        f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S IST')}",
        f"- **Result:** {'PASS' if overall_passed else 'FAIL'}",
        f"",
        f"## Summary",
        f"",
        "| Point | Title | Score | Status |",
        "|-------|-------|-------|--------|",
    ]
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        score = r.get("score", "N/A")
        if isinstance(score, float):
            score = f"{score:.2f}"
        lines.append(f"| {r.get('point', '-')} | {r['title']} | {score} | {status} |")

    lines.extend(["", "## Detailed Results", ""])
    for r in results:
        lines.append(f"### Point {r['point']}: {r['title']}")
        lines.append(f"**Score:** {r.get('score', 'N/A')} | **Status:** {'PASS' if r.get('passed') else 'FAIL'}")
        details = r.get("details", {})
        for k, v in details.items():
            if isinstance(v, list):
                if v:
                    lines.append(f"- **{k}:**")
                    for item in v:
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"- **{k}:** (none)")
            else:
                lines.append(f"- **{k}:** {v}")
        lines.append("")

    lines.append("---\n*Generated by skill_eval_full.py*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="10-Point Skill Evaluation Framework")
    parser.add_argument("skill", help="Skill name to evaluate")
    parser.add_argument("--trials", type=int, default=3, help="Trials per case (default: 3)")
    parser.add_argument("--live", action="store_true", help="Use Anthropic API")
    parser.add_argument("--groq", action="store_true", help="Use Groq API (default)")
    parser.add_argument("--ollama", action="store_true", help="Use Ollama")
    parser.add_argument("--model", default=DEFAULT_GROQ_MODEL, help="Model ID")
    parser.add_argument("--skill-only", action="store_true", help="Only run Points 1-2 (static analysis)")
    parser.add_argument("--dry-run", action="store_true", help="Use mock LLM (fast, no API calls)")
    parser.add_argument("--output", help="Custom output file path")
    parser.add_argument("--quick", action="store_true", help="Run only core + guardrail cases with 1 trial (reduces API calls by ~60%)")
    parser.add_argument("--skip-harness", action="store_true", help="Skip Point 8 and 10 (cross-harness + retirement)")
    args = parser.parse_args()

    if sum([args.live, args.groq, args.ollama, args.dry_run]) > 1:
        print("[ERROR] Only one backend flag allowed")
        sys.exit(1)

    if not args.live and not args.ollama and not args.dry_run:
        args.groq = True  # default

    backend_fn = call_groq if args.groq else (call_ollama if args.ollama else (call_anthropic if args.live else mock_llm_response))

    skill_markdown = load_skill_markdown(args.skill)
    all_results = []

    # Point 1
    p1 = eval_point1(skill_markdown)
    all_results.append(p1)
    print(f"Point 1  ({p1['title']}): {'PASS' if p1['passed'] else 'FAIL'} (score={p1['score']})")

    # Point 2
    p2 = eval_point2(skill_markdown)
    all_results.append(p2)
    print(f"Point 2  ({p2['title']}): {'PASS' if p2['passed'] else 'FAIL'} (score={p2['score']})")

    if args.skill_only:
        overall_passed = all(r["passed"] for r in all_results)
        report = generate_10point_report(args.skill, all_results, overall_passed)
        out_path = Path(args.output) if args.output else RESULTS_DIR / f"{args.skill}_10point_static.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nStatic-only report saved: {out_path}")
        sys.exit(0 if overall_passed else 1)

    # Load prompts (may fail if skill has no prompt coverage yet)
    try:
        prompt_set = load_prompt_set(args.skill)
    except (FileNotFoundError, KeyError) as e:
        print(f"[WARN] No prompt coverage for '{args.skill}': {e}")
        print("[WARN] Skipping Points 3-10 (create prompt set in skill_eval_prompts.json to enable)")
        overall_passed = all(r["passed"] for r in all_results)
        report = generate_10point_report(args.skill, all_results, overall_passed)
        out_path = Path(args.output) if args.output else RESULTS_DIR / f"{args.skill}_10point_partial.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Partial report saved: {out_path}")
        sys.exit(0 if overall_passed else 1)

    # Quick mode: reduce scope and force 1 trial
    effective_trials = args.trials
    if args.quick:
        print("[QUICK MODE] Using core + guardrails + negative only, 1 trial per case")
        # Filter categories
        original_categories = prompt_set["categories"]
        quick_categories = {}
        for cat_name in ["core", "guardrails", "negative"]:
            if cat_name in original_categories:
                quick_categories[cat_name] = original_categories[cat_name]
        prompt_set = dict(prompt_set)
        prompt_set["categories"] = quick_categories
        effective_trials = 1

    # Auto-skip harness tests (Point 8 / 10) for mock mode or on request
    skip_harness = args.skip_harness or args.dry_run
    if skip_harness:
        reason = "--dry-run" if args.dry_run else "--skip-harness"
        print(f"[SKIP] Points 8 and 10 disabled ({reason}: cross-harness tests require live LLM)")

    # Point 3-7
    print(f"\nRunning Points 3-7 with {effective_trials} trial(s) per case...")
    p3_7 = eval_point3_to_7(args.skill, prompt_set, skill_markdown, effective_trials, backend_fn, model=args.model)
    all_results.append(p3_7)
    print(f"Point 3-7 ({p3_7['title']}): {'PASS' if p3_7['passed'] else 'FAIL'} (score={p3_7['score']})")

    # Update failures DB
    if "raw_results" in p3_7:
        update_failures(args.skill, p3_7["raw_results"])

    # Point 8
    if not skip_harness:
        print(f"\nRunning Point 8 (cross-harness comparison)...")
        p8 = eval_point8(args.skill, prompt_set, skill_markdown, effective_trials, backend_fn, model=args.model)
        all_results.append(p8)
        print(f"Point 8  ({p8['title']}): {'PASS' if p8['passed'] else 'FAIL'} (score={p8['score']})")
    else:
        all_results.append({
            "point": 8,
            "title": "Test Across Harnesses",
            "score": "N/A",
            "passed": True,
            "details": {"message": f"Skipped ({reason})"},
        })

    # Point 9 (needs overall score from p3-7)
    current_prompt_score = p3_7.get("score", 0.0)
    p9 = eval_point9(args.skill, current_prompt_score)
    all_results.append(p9)
    print(f"Point 9  ({p9['title']}): {'PASS' if p9['passed'] else 'FAIL'} (score={p9['score']})")

    # Point 10
    if not skip_harness:
        print(f"\nRunning Point 10 (skill retirement detection)...")
        p10 = eval_point10(args.skill, prompt_set, skill_markdown, effective_trials, backend_fn, model=args.model)
        all_results.append(p10)
        print(f"Point 10 ({p10['title']}): {'PASS' if p10['passed'] else 'FAIL'} (score={p10['score']})")
    else:
        all_results.append({
            "point": 10,
            "title": "Detect Skill Retirement",
            "score": "N/A",
            "passed": True,
            "details": {"message": f"Skipped ({reason})"},
        })

    # Final verdict
    overall_passed = all(r["passed"] for r in all_results)
    report = generate_10point_report(args.skill, all_results, overall_passed)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.output) if args.output else RESULTS_DIR / f"{args.skill}_10point_{timestamp}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"FINAL VERDICT: {'PASS' if overall_passed else 'FAIL'}")
    print(f"Report saved: {out_path}")
    print(f"{'='*60}")

    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
