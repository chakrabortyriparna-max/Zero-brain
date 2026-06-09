"""
apply_verdict.py — Dark Factory PR verdict application.

Reads synthesizer verdict files from $ARTIFACTS_DIR, applies the deterministic
infrastructure backstop, and posts the final GitHub verdict (approve / request_changes /
reject) with labels, merge/close, and issue updates.

Called from the apply-verdict bash node in dark-factory-validate-pr.yaml.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def run(args: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess command with GH_TOKEN forwarded."""
    env = {**os.environ, "GH_PAGER": "cat"}
    if "GH_TOKEN" not in env and "GITHUB_TOKEN" in env:
        env["GH_TOKEN"] = env["GITHUB_TOKEN"]
    return subprocess.run(args, capture_output=True, text=True, check=check, env=env, **kwargs)


def gh_api(args: list[str], check: bool = False) -> str:
    """Run a gh CLI command and return stdout (empty on failure)."""
    result = run(["gh", *args], check=check)
    return result.stdout.strip() if result.returncode == 0 else ""


def pr_view(pr_number: str, fields: list[str]) -> dict:
    """Fetch PR metadata via gh pr view --json."""
    out = gh_api(["pr", "view", pr_number, "--json", ",".join(fields)])
    try:
        return json.loads(out) if out else {}
    except Exception:
        return {}


def post_review(pr_number: str, flag: str, body: str, self_review: bool) -> None:
    """Post a PR review or comment (fallback for self-review)."""
    if self_review:
        run(["gh", "pr", "comment", pr_number, "--body", body], check=False)
    else:
        run(["gh", "pr", "review", pr_number, flag, "--body", body], check=False)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: apply_verdict.py <PR_NUMBER> <ARTIFACTS_DIR>", file=sys.stderr)
        return 1

    pr_number = sys.argv[1]
    artifacts_dir = Path(sys.argv[2])

    p1_file = artifacts_dir / "p1-verdict.json"
    p2_file = artifacts_dir / "p2-verdict.json"
    verdict_file = p1_file
    pass_label = "pass-1"

    if p2_file.exists() and p2_file.stat().st_size > 0:
        try:
            data = json.loads(p2_file.read_text().strip("'").replace("'\\''", "'"))
            if data.get("verdict"):
                verdict_file = p2_file
                pass_label = "pass-2"
        except Exception:
            pass

    # Defensive fallback for empty / unparseable verdict
    if not verdict_file.exists() or verdict_file.stat().st_size == 0:
        print("WARN: verdict file missing or empty — emitting fallback reject+escalate", file=sys.stderr)
        fallback = {
            "verdict": "reject",
            "summary": "Validator infrastructure failed - no synthesizer output available. Manual investigation required.",
            "static_checks_status": "fail",
            "tests_status": "fail",
            "behavioral_status": "no",
            "security_status": "fail",
            "issues_to_fix": [],
            "should_escalate": True,
            "escalation_reason": "Upstream node failed and produced no verdict. Validator cannot render a substantive decision; human must investigate the broken run.",
            "reasoning": "Fallback verdict emitted because the selected verdict file was empty or unparseable JSON.",
        }
        verdict_file.write_text(json.dumps(fallback))

    try:
        verdict_json = json.loads(verdict_file.read_text().strip("'").replace("'\\''", "'"))
    except Exception as e:
        print(f"ERROR: Failed to parse verdict JSON: {e}", file=sys.stderr)
        return 1

    decision = verdict_json.get("verdict", "reject")
    summary = verdict_json.get("summary", "")
    should_escalate = verdict_json.get("should_escalate", False)
    escalation_reason = verdict_json.get("escalation_reason", "")
    issues = verdict_json.get("issues_to_fix", [])

    # Infrastructure backstop: if start-app never emitted APP_STARTED, override approve -> reject+escalate
    start_app_output = artifacts_dir / ".start-app-output"
    app_did_start = False
    e2e_intentionally_skipped = False
    if start_app_output.exists():
        text = start_app_output.read_text()
        if "APP_STARTED" in text:
            app_did_start = True
        elif "E2E_SKIPPED" in text:
            app_did_start = True
            e2e_intentionally_skipped = True

    print(f"INFRA_BACKSTOP: app_did_start={app_did_start} e2e_intentionally_skipped={e2e_intentionally_skipped} decision={decision}")

    if decision == "approve" and not app_did_start:
        print("INFRA_BACKSTOP_OVERRIDE: start-app did not emit APP_STARTED but synthesizer rendered approve — overriding to reject+escalate.", file=sys.stderr)
        decision = "reject"
        should_escalate = True
        escalation_reason = (
            "Deterministic infrastructure backstop fired: start-app output lacked the APP_STARTED marker, "
            "so no agent-browser E2E regression could have actually run against a live app. "
            "The synthesize-verdict node rendered an approve verdict anyway. "
            "A human must investigate both the infrastructure failure and the synthesizer's failure to catch it."
        )
        summary = (
            "Infrastructure backstop override: start-app never reached APP_STARTED, "
            "so the agent-browser E2E regression required by FACTORY_RULES could not have run. Auto-approve blocked."
        )
        issues = [
            {"category": "e2e", "severity": "critical", "description": "start-app node did not emit APP_STARTED — backend or frontend failed to boot and the mandatory agent-browser regression never ran."},
            {"category": "e2e", "severity": "critical", "description": "synthesize-verdict rendered approve despite the missing APP_STARTED marker — review why rule 0 of the synthesize-verdict command did not fire."},
        ]

    # Self-review detection
    pr_data = pr_view(pr_number, ["author"])
    pr_author = pr_data.get("author", {}).get("login", "")
    bot_login = ""
    try:
        bot_login = gh_api(["api", "user"], check=False)
        bot_login = json.loads(bot_login).get("login", "") if bot_login else ""
    except Exception:
        pass
    self_review = pr_author != "" and pr_author == bot_login
    if self_review:
        print(f"Self-review detected (PR author '{pr_author}' == bot '{bot_login}'); will post as comment instead of formal review.")

    # Build issues markdown
    issues_md = "\n".join(
        f"- **{i.get('severity','')}** [{i.get('category','')}]: {i.get('description','')}"
        for i in issues
    )

    # Execute verdict
    if decision == "approve":
        e2e_line = (
            "- Behavioral (E2E via agent-browser): skipped (no runnable app detected)"
            if e2e_intentionally_skipped
            else "- Behavioral (E2E via agent-browser): solves_issue=yes"
        )
        body = (
            f"**Dark Factory Validation**: APPROVED ({pass_label})\n\n"
            f"{summary}\n\n"
            f"All quality gates passed:\n"
            f"- Behavioral (static): solves_issue=yes\n"
            f"{e2e_line}\n"
            f"- Security: pass (no governance files modified)\n"
            f"- Static checks: pass\n"
            f"- Tests: pass or legitimately skipped\n"
            f"- Code review: no critical/high findings\n\n"
            f"Auto-merging via squash."
        )
        post_review(pr_number, "--approve", body, self_review)

        is_draft = pr_view(pr_number, ["isDraft"]).get("isDraft", False)
        if is_draft:
            print(f"PR #{pr_number} is draft — marking ready for review before merge")
            run(["gh", "pr", "ready", pr_number], check=False)

        merge_result = run(["gh", "pr", "merge", pr_number, "--squash"], check=False)
        if merge_result.returncode == 0:
            print(f"PR #{pr_number}: merged via squash")
        else:
            print(f"WARN: squash merge failed for PR #{pr_number} — leaving approved for manual merge", file=sys.stderr)

        run(["gh", "pr", "edit", pr_number, "--remove-label", "factory:needs-review", "--add-label", "factory:approved"], check=False)
        print(f"PR #{pr_number}: APPROVED ({pass_label})")

    elif decision == "request_changes":
        if pass_label == "pass-2" or should_escalate:
            body = (
                f"**Dark Factory Validation**: ESCALATED TO HUMAN ({pass_label})\n\n"
                f"{summary}\n\n"
                f"### Escalation reason\n"
                f"{escalation_reason or 'Autonomous fix pass did not resolve all blocking issues. Human review required.'}\n\n"
                f"### Issues remaining\n"
                f"{issues_md}"
            )
            post_review(pr_number, "--request-changes", body, self_review)
            run(["gh", "pr", "edit", pr_number, "--remove-label", "factory:needs-review", "--add-label", "factory:needs-human"], check=False)
            print(f"PR #{pr_number}: ESCALATED to human after {pass_label}")
        else:
            body = (
                f"**Dark Factory Validation**: Changes Requested ({pass_label})\n\n"
                f"{summary}\n\n"
                f"### Issues to fix\n"
                f"{issues_md}"
            )
            post_review(pr_number, "--request-changes", body, self_review)
            run(["gh", "pr", "edit", pr_number, "--remove-label", "factory:needs-review", "--add-label", "factory:needs-fix"], check=False)
            print(f"PR #{pr_number}: CHANGES REQUESTED ({pass_label})")

    elif decision == "reject":
        if should_escalate:
            body = (
                f"**Dark Factory Validation**: REJECTED + ESCALATED ({pass_label})\n\n"
                f"{summary}\n\n"
                f"### Escalation reason\n"
                f"{escalation_reason}\n\n"
                f"### Findings\n"
                f"{issues_md}\n\n"
                f"This PR is NOT being closed — a human needs to investigate."
            )
            post_review(pr_number, "--request-changes", body, self_review)
            run(["gh", "pr", "edit", pr_number, "--remove-label", "factory:needs-review", "--add-label", "factory:needs-human"], check=False)

            issue_num = None
            try:
                pr_body = pr_view(pr_number, ["body"]).get("body", "")
                import re
                m = re.search(r"(?i)(fixes|closes|resolves)\s+#(\d+)", pr_body)
                if m:
                    issue_num = m.group(2)
            except Exception:
                pass
            if issue_num:
                run(["gh", "issue", "edit", issue_num, "--add-label", "factory:needs-human"], check=False)
                icomment = (
                    f"**Dark Factory**: PR #{pr_number} was rejected and escalated to human review ({pass_label}).\n\n"
                    f"Reason: {summary}\n\n"
                    f"{escalation_reason}"
                )
                run(["gh", "issue", "comment", issue_num, "--body", icomment], check=False)
            print(f"PR #{pr_number}: REJECTED+ESCALATED ({pass_label}) — left open for human review")
        else:
            body = (
                f"**Dark Factory Validation**: REJECTED ({pass_label})\n\n"
                f"{summary}\n\n"
                f"### Blocking issues\n"
                f"{issues_md}\n\n"
                f"This PR cannot be fixed incrementally and has been closed."
            )
            post_review(pr_number, "--request-changes", body, self_review)
            run(["gh", "pr", "close", pr_number], check=False)

            issue_num = None
            try:
                pr_body = pr_view(pr_number, ["body"]).get("body", "")
                import re
                m = re.search(r"(?i)(fixes|closes|resolves)\s+#(\d+)", pr_body)
                if m:
                    issue_num = m.group(2)
            except Exception:
                pass
            if issue_num:
                run(["gh", "issue", "reopen", issue_num], check=False)
                run(["gh", "issue", "edit", issue_num, "--add-label", "factory:accepted", "--remove-label", "factory:in-progress"], check=False)
                icomment = (
                    f"**Dark Factory**: PR #{pr_number} was rejected during validation ({pass_label}). "
                    f"Issue re-queued for another implementation attempt.\n\n"
                    f"Reason: {summary}"
                )
                run(["gh", "issue", "comment", issue_num, "--body", icomment], check=False)
            print(f"PR #{pr_number}: REJECTED ({pass_label}) and closed")
    else:
        print(f"ERROR: Unknown verdict '{decision}' from {pass_label}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
