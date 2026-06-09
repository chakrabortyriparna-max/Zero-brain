import json

reports = [
    ("draft_ai_email_10point_20260518_002756", "draft-ai-email", "2026-05-18 00:27:56", "draft-ai-email_10point_20260518_002756.md", True),
    ("draft_ai_email_10point_20260518_031436", "draft-ai-email", "2026-05-18 03:14:36", "draft-ai-email_10point_20260518_031436.md", True),
    ("draft_ai_email_10point_20260518_115513", "draft-ai-email", "2026-05-18 11:55:13", "draft-ai-email_10point_20260518_115513.md", True),
    ("draft_ai_email_10point_20260519_115246", "draft-ai-email", "2026-05-19 11:52:46", "draft-ai-email_10point_20260519_115246.md", True),
    ("draft_ai_email_10point_static", "draft-ai-email", "Static", "draft-ai-email_10point_static.md", False),
    ("gps_prompt_engineer_10point_20260518_002820", "gps-prompt-engineer", "2026-05-18 00:28:20", "gps-prompt-engineer_10point_20260518_002820.md", True),
    ("gps_prompt_engineer_10point_20260518_031459", "gps-prompt-engineer", "2026-05-18 03:14:59", "gps-prompt-engineer_10point_20260518_031459.md", True),
    ("gps_prompt_engineer_10point_20260518_115708", "gps-prompt-engineer", "2026-05-18 11:57:08", "gps-prompt-engineer_10point_20260518_115708.md", True),
    ("gps_prompt_engineer_10point_20260519_115405", "gps-prompt-engineer", "2026-05-19 11:54:05", "gps-prompt-engineer_10point_20260519_115405.md", True),
    ("gps_prompt_engineer_10point_static", "gps-prompt-engineer", "Static", "gps-prompt-engineer_10point_static.md", False),
    ("learn_unfamiliar_code_10point_20260518_002939", "learn-unfamiliar-code", "2026-05-18 00:29:39", "learn-unfamiliar-code_10point_20260518_002939.md", True),
    ("learn_unfamiliar_code_10point_20260518_031618", "learn-unfamiliar-code", "2026-05-18 03:16:18", "learn-unfamiliar-code_10point_20260518_031618.md", True),
    ("learn_unfamiliar_code_10point_20260518_115810", "learn-unfamiliar-code", "2026-05-18 11:58:10", "learn-unfamiliar-code_10point_20260518_115810.md", True),
    ("learn_unfamiliar_code_10point_20260519_115428", "learn-unfamiliar-code", "2026-05-19 11:54:28", "learn-unfamiliar-code_10point_20260519_115428.md", True),
    ("learn_unfamiliar_code_10point_static", "learn-unfamiliar-code", "Static", "learn-unfamiliar-code_10point_static.md", False),
    ("organize_research_10point_20260518_003002", "organize-research", "2026-05-18 00:30:02", "organize-research_10point_20260518_003002.md", True),
    ("organize_research_10point_20260518_031641", "organize-research", "2026-05-18 03:16:41", "organize-research_10point_20260518_031641.md", True),
    ("organize_research_10point_20260518_115921", "organize-research", "2026-05-18 11:59:21", "organize-research_10point_20260518_115921.md", True),
    ("organize_research_10point_20260519_115549", "organize-research", "2026-05-19 11:55:49", "organize-research_10point_20260519_115549.md", True),
    ("organize_research_10point_static", "organize-research", "Static", "organize-research_10point_static.md", False),
    ("summarize_slack_10point_20260518_003123", "summarize-slack", "2026-05-18 00:31:23", "summarize-slack_10point_20260518_003123.md", True),
    ("summarize_slack_10point_20260518_031802", "summarize-slack", "2026-05-18 03:18:02", "summarize-slack_10point_20260518_031802.md", True),
]

skill_map = {
    "draft-ai-email": "skill_eval_results_draft_ai_email_10point_static_draft_ai_email",
    "gps-prompt-engineer": "skill_eval_results_gps_prompt_engineer_10point_static_gps_prompt_engineer",
    "learn-unfamiliar-code": "skill_eval_results_learn_unfamiliar_code_10point_static_learn_unfamiliar_code",
    "organize-research": "skill_eval_results_organize_research_10point_static_organize_research",
    "summarize-slack": "skill_eval_results_summarize_slack_10point_20260518_003123_summarize_slack",
}

criteria = [
    ("skill_eval_results_draft_ai_email_10point_20260518_002756_skill_description_trigger_check", "Skill Description Trigger Check"),
    ("skill_eval_results_draft_ai_email_10point_20260518_002756_directives_vs_information", "Directives vs Information"),
    ("skill_eval_results_draft_ai_email_10point_20260518_002756_prompt_based_evaluation_suite", "Prompt-Based Evaluation Suite"),
    ("skill_eval_results_draft_ai_email_10point_20260518_002756_test_across_harnesses", "Test Across Harnesses"),
    ("skill_eval_results_draft_ai_email_10point_20260518_002756_graduate_evals", "Graduate Evals"),
    ("skill_eval_results_draft_ai_email_10point_20260518_002756_detect_skill_retirement", "Detect Skill Retirement"),
]

generator_id = "skill_eval_results_draft_ai_email_10point_20260518_002756_skill_eval_full_py"

nodes = []
edges = []

for stem, skill_label, date, filename, is_full in reports:
    report_id = f"skill_eval_results_{stem}_report"
    source_file = f"Memory/research/skill-eval-results/{filename}"
    nodes.append({
        "id": report_id,
        "label": f"10-Point Skill Evaluation Report — {skill_label} ({date})",
        "file_type": "document",
        "source_file": source_file,
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
    })
    # report -> skill
    edges.append({
        "source": report_id,
        "target": skill_map[skill_label],
        "relation": "references",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": source_file,
        "source_location": None,
        "weight": 1.0,
    })
    # report -> generator
    edges.append({
        "source": report_id,
        "target": generator_id,
        "relation": "references",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": source_file,
        "source_location": None,
        "weight": 1.0,
    })
    # report -> criteria
    if is_full:
        for c_id, _ in criteria:
            edges.append({
                "source": report_id,
                "target": c_id,
                "relation": "references",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
                "source_file": source_file,
                "source_location": None,
                "weight": 1.0,
            })
    else:
        for c_id, _ in criteria[:2]:
            edges.append({
                "source": report_id,
                "target": c_id,
                "relation": "references",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
                "source_file": source_file,
                "source_location": None,
                "weight": 1.0,
            })

# skill nodes
skill_nodes = [
    ("skill_eval_results_draft_ai_email_10point_static_draft_ai_email", "draft-ai-email skill", "Memory/research/skill-eval-results/draft-ai-email_10point_static.md"),
    ("skill_eval_results_gps_prompt_engineer_10point_static_gps_prompt_engineer", "gps-prompt-engineer skill", "Memory/research/skill-eval-results/gps-prompt-engineer_10point_static.md"),
    ("skill_eval_results_learn_unfamiliar_code_10point_static_learn_unfamiliar_code", "learn-unfamiliar-code skill", "Memory/research/skill-eval-results/learn-unfamiliar-code_10point_static.md"),
    ("skill_eval_results_organize_research_10point_static_organize_research", "organize-research skill", "Memory/research/skill-eval-results/organize-research_10point_static.md"),
    ("skill_eval_results_summarize_slack_10point_20260518_003123_summarize_slack", "summarize-slack skill", "Memory/research/skill-eval-results/summarize-slack_10point_20260518_003123.md"),
]
for sid, lbl, sfile in skill_nodes:
    nodes.append({
        "id": sid,
        "label": lbl,
        "file_type": "concept",
        "source_file": sfile,
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
    })

# generator node
nodes.append({
    "id": generator_id,
    "label": "skill_eval_full.py generator",
    "file_type": "concept",
    "source_file": "Memory/research/skill-eval-results/draft-ai-email_10point_20260518_002756.md",
    "source_location": None,
    "source_url": None,
    "captured_at": None,
    "author": None,
    "contributor": None,
})

# criteria nodes
for c_id, c_label in criteria:
    nodes.append({
        "id": c_id,
        "label": c_label,
        "file_type": "concept",
        "source_file": "Memory/research/skill-eval-results/draft-ai-email_10point_20260518_002756.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
    })

payload = {
    "nodes": nodes,
    "edges": edges,
    "hyperedges": [],
    "input_tokens": 8000,
    "output_tokens": 3000,
}

with open(r"C:\Users\chakr\OneDrive\Desktop\zero BRAIN\second-brain-starter\graphify-out\.graphify_chunk_07.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)
