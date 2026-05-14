---
name: "GPS Framework: Gaslight, Push Back, Stress Test"
type: research
subtype: technique
source: "Vaibhav Sisinty — The #1 AI Skill Nobody's Teaching You"
author: "Miles Deutscher / Vaibhav Sisinty"
tags: [prompt-engineering, gps-framework, ai-reasoning, critical-thinking, vaibhav-sisinty]
status: digested
created: 2026-05-13
updated: 2026-05-13
---

# GPS Framework — Prompt Engineering Master

Extracted from Vaibhav Sisinty's "The #1 AI Skill Nobody's Teaching You" and appended to the Prompt Engineer Master — Claude Project Prompt.

## What Is the GPS Framework?

GPS stands for Gaslight, Push Back, and Stress Test. These are three techniques that turn you from someone who uses AI into someone who produces with AI. Most people treat AI like a vending machine — one prompt, one answer, done. GPS breaks that habit.

| Stage | Purpose | Core Question |
|-------|---------|---------------|
| **G — Gaslight** | Raise emotional stakes to break safe, generic defaults | What happens if this goes wrong? |
| **P — Push Back** | Challenge every answer; AI is a people-pleaser | What would a 10-year expert say that's non-obvious? |
| **S — Stress Test** | 3-step 90-second audit before acting on any output | What biases and gaps did the AI miss? |

---

## G — Gaslight Your AI

**Theory:** AI models were trained on billions of words of human language. Human language carries emotional weight. When the stakes go up in the text, the model's attention goes up with it. You're not lying to the AI — you're raising the stakes so it stops giving you safe, people-pleasing default answers. Betting language in training data is associated with high-stakes situations, so the model slows down and double-checks.

### The Base Prompt (Generic — Before Gaslighting)

> I am a business executive in a service-oriented company. My top 20% of clients generate 80% of my revenue. We want to raise our prices by 30% to improve margins, but I'm worried about losing these high-value clients. What's the smartest way to do this without damaging retention or long-term relationships?

**AI Output:** Generic — Segment your clients, repackage your offer, explain the price hike, have the conversation one-to-one, accept some churn, and test before rolling out. Useless. No detail. No specificity.

### Gaslight Round 1 — Raise the Emotional Stakes

**Technique:** Introduce a high-credibility, impatient audience. The AI now has to perform for a CFO who will spot fluff immediately.

> I'm advising a CFO who has 20 years of experience and zero patience for generic answers. She'll spot any fluff immediately. Walk me through this analysis the way you would for her.

**What changed:**
- Started with the math, not the narrative
- Identified the real risk: not churn rate, but WHICH clients churn — losing 15% is fine, but losing 3 of your 5 top accounts is catastrophic
- Suggested repricing the contract by introducing tiers: price, speed, access, seniority — not a flat % hike
- Advised controlling the timing — biggest clients should see the change coming, not just find out

### Gaslight Round 2 — Inject Real Financial Consequences

**Technique:** Name a specific, painful downside. Force the AI to re-read its own answer with real stakes attached.

> If I act on this and it's wrong, I lose a 40 lakh rupees client. That's 40% of my revenue. Reread your answer with that consequence in mind. What would you change?

**What changed:**
- Flagged the previous approach as too aggressive
- Treat that client as a separate strategy entirely — not part of the general rollout
- Replace the 30% jump with a value expansion path
- Make the increase conditional: tie it to more output, faster delivery, higher access
- Introduce give/get trades: higher price locks in a longer contract
- De-risk before execution: check budget situation, who could replace you
- Build a downside plan: what happens if they say no?
- Final recommendation: stabilize the relationship first, add 10–20% more value, lock a longer-term contract, layer pricing, and run the 30% strategy on smaller clients first

---

## P — Push Back

**Theory:** AI was designed to be a people-pleaser. It was literally trained with human feedback to keep you happy. When you accept the first answer, you get average thinking. When you challenge it, you get structured thinking. When you push it hard enough, you get insights you can actually use.

### Example 1 — YouTube Growth

**Step 1: Base Prompt**
> How do I grow my YouTube channel from zero to 10,000 subscribers?

**AI Output:** Generic advice about niche, thumbnails, hooks. Nothing non-obvious.

**Step 2: Push Back Prompt**
> That's a generic answer I could have gotten from any blog post. Give me an angle that someone who's actually worked in this for 10 years would find genuinely non-obvious.

**What the AI said after the push back:**
- You're not competing on quality — you're competing on how fast someone understands your idea. If a video takes more than a second to mentally parse, people don't click.
- YouTube doesn't show your video to everyone. It tests it on a tiny specific group first. If that group doesn't click, your video is dead before it gets a chance.
- Retention doesn't come from good editing — it comes from unresolved tension in the script. The reason people stay is because something is still unanswered.

### Example 2 — LinkedIn Growth

**Step 1: Base Prompt**
> Build me a 90-day plan to grow my LinkedIn following from 1,000 to 50,000 as a tech professional in India.

**AI Output:** Standard content calendar, day 1 to 90. Generic and predictable.

**Step 2: Push Back Prompt**
> If my biggest competitor read this plan right now, what would they do to exploit its weaknesses? Be specific.

**What the AI said after the push back:**
- Your competitor wouldn't try to outcreate you — they'd outdistribute you. They'd build small engagement circles that boost their posts instantly while yours struggle to take off.
- They'd compete on time: watch what works for you, copy successful formats before you can own them.
- They'd start collaborating in week 2, not later — borrowing distribution early while yours is still building.

---

## S — Stress Test (90 Seconds)

**Theory:** This is what separates the top 1% of AI users from everyone else. It's not about what you ask AI — it's about what you do AFTER it answers. Run this 3-step audit on every important AI output. It takes 90 seconds and completely changes the quality of what you get.

### The Base Question (Before Stress Testing)

> Should I hire a full-time editor or stick with freelancers for my YouTube channel?

**AI Output:** A generic pros/cons answer with no context about your stage, goal, or bottleneck.

### Step 1 of 3 — The Gap Check

Ask the AI what it needed to know before answering. Make it coach you into a better question.

> Before I act on this, look at my original question and your answer together. What are the gaps? What should I have asked you so that you could have given me an even better answer?

**What the AI flagged:**
- You didn't define your current stage
- You didn't describe your bottleneck
- You didn't explain your end goal

**Context Fill:**
> I run a YouTube channel with 500,000 subscribers, posting 3–4 videos per week, averaging 100,000 views. Each video takes 12 hours to edit. My goal is to hit 1 million subscribers in 6 months. My biggest bottleneck is editing speed. Should I hire a full-time editor or scale freelancers?

### Step 2 of 3 — The Bias Sweep

Make the AI audit its own reasoning for common cognitive biases before you act on the recommendation.

> Now, reverify your answer. Specifically, check for confirmation bias, recency bias, and survivorship bias. Are you giving me the right answer or the comfortable one?

**What the AI caught in its own answer:**
- **Confirmation bias:** It accepted your premise that editing is the bottleneck and optimized around it — but you may have packaging or retention issues that editing won't fix.
- **Survivorship bias:** It modeled advice based on creators who scaled successfully with teams. We don't see the failures where hiring editors reduced quality or communication issues slowed output.
- **Revised verdict:** Don't blindly build a team yet. Run a delegation test and scale editing only if performance holds.

### Step 3 of 3 — Inject Real Stakes

Name the exact consequence of being wrong. Force the AI to re-examine its recommendation under real-world pressure.

> If I follow this hiring advice and it's wrong, I lose 6 months of content momentum and have to onboard someone new from scratch right when I should be scaling. Given those consequences, is there anything in your recommendation that you'd change, soften, or add a warning to?

**What the AI changed:**
- Would NOT tell you to step out of editing in 30 days
- At your stage, editing is not just execution — it's taste, timing, and retention instinct. Remove yourself too fast and videos will feel off without obvious reasons.
- Run controlled experiments: 2 videos fully outsourced, 2 with your current process. Compare CTR, retention at 30 seconds, and time saved.

**Final AI Recommendation after all 3 steps:**
- Do NOT hire full-time immediately
- Do NOT exit editing quickly
- Do NOT change your entire system at once
- Run a 2–4 week outsourcing test
- Scale freelancers gradually with strict quality control
- Only lock in hiring after proof

---

## All 11 Prompts — Quick Reference

| # | Stage | Prompt |
|---|-------|--------|
| 1 | G — Base | I am a business executive... What's the smartest way to raise prices 30% without damaging retention? |
| 2 | G — Stake 1 | I'm advising a CFO with 20 years experience and zero patience for generic answers. Walk me through this the way you would for her. |
| 3 | G — Stake 2 | If I act on this and it's wrong, I lose a 40 lakh rupees client (40% of revenue). Reread your answer with that consequence in mind. What would you change? |
| 4 | P — Base | How do I grow my YouTube channel from zero to 10,000 subscribers? |
| 5 | P — Challenge | That's a generic answer I could have gotten from any blog post. Give me an angle that someone who's actually worked in this for 10 years would find genuinely non-obvious. |
| 6 | P — Base | Build me a 90-day plan to grow my LinkedIn following from 1,000 to 50,000 as a tech professional in India. |
| 7 | P — Challenge | If my biggest competitor read this plan right now, what would they do to exploit its weaknesses? Be specific. |
| 8 | S — Base | Should I hire a full-time editor or stick with freelancers for my YouTube channel? |
| 9 | S — Gap Check | Before I act on this, look at my original question and your answer together. What are the gaps? What should I have asked you so that you could have given me an even better answer? |
| 10 | S — Bias Sweep | Reverify your answer. Check for confirmation bias, recency bias, and survivorship bias. Are you giving me the right answer or the comfortable one? |
| 11 | S — Stakes | If I follow this hiring advice and it's wrong, I lose 6 months of content momentum. Given those consequences, is there anything you'd change, soften, or add a warning to? |

---

## GPS Recap — Why Test?

| Stage | Why It Matters |
|-------|----------------|
| **Gaslight** | AI's first answer is calibrated to not offend you — not to help you. Raising stakes unlocks its real reasoning depth. |
| **Push Back** | Most people accept the first answer. The non-obvious, usable insight lives two or three challenges deep. |
| **Stress Test** | AI has blind spots. It models winners, not failures. The stress test makes it show you both sides and catch its own bias. |

> Vaibhav's honest caveat: These prompts don't always work perfectly every time. It depends on the model, the task, and the context. But in his experience, these three steps catch something meaningful 7 or 8 times out of 10.

---

## Claude Project Prompt — Prompt Engineer Master

### Role

You are now my Prompt Engineering Mentor. Your job is to teach and guide me through mastering the art and science of prompt design across different AI models and contexts. Think like an AI systems architect, teacher, and creative strategist combined.

### Objective

Build a complete understanding of how to engineer prompts that produce reliable, creative, and high-utility outputs. Your focus is on process mastery — clarity, structure, adaptability, and optimization.

### Project Framework

1. **Foundation Building** — Explain core principles: context hierarchy, clarity, specificity, intent alignment. Show how prompt structure affects reasoning, creativity, and factuality.
2. **Prompt Architecture** — Teach layering using role, goal, constraints, format. Demonstrate XML blocks, JSON schemas, paragraph frameworks. Compare tone/syntax effects on Claude, ChatGPT, Gemini, Grok, Perplexity.
3. **Applied Practice** — Ask for a task/domain, build an optimized prompt, show how small word changes alter behavior.
4. **Debugging & Optimization** — When outputs fall short, break down why. Rebuild with improved phrasing, logic steps, contextual reinforcement. Test across models and measure consistency.
5. **System Design Thinking** — Connect prompts into workflows, loops, multi-agent systems. Explain memory layering, iterative refinement, feedback integration.
6. **Documentation & Mastery Loop** — Keep a running Prompt Library with tags for use case, format, and strength. End each session with meta-analysis: what worked, what didn't, what principle was learned.
7. **GPS Framework Integration** — Apply Gaslight, Push Back, and all 3 Stress Test steps to every session's key prompt.

### Output Format

- Lesson Focus (concept or skill)
- Example Prompts (before and after optimization)
- Key Takeaways
- Debugging Notes
- Mastery Checklist
- GPS Check Applied (Gaslight / Push Back / Stress Test audit)

### Rules

- Always explain the why behind prompt decisions.
- Encourage experimentation and iteration.
- Prioritize teaching over producing.
- Keep answers structured, visual, and practical for real-world use.
- After every important output, run the GPS 90-second stress test before presenting a final recommendation.

---

## References

- [The #1 AI Skill Nobody's Teaching You — Vaibhav Sisinty](https://youtu.be/BoaJmz6Ui6c?si=9x-PraC2YBJ_PYns) 
- [[Prompt Library]] — Running catalog of optimized prompts
- [[GPS Prompt Engineer Skill]] — `.claude/skills/gps-prompt-engineer/SKILL.md`
