# AI Agent Processes — Overview

This space documents **AIAgentCoreRules**, the portable framework we use to work with AI coding
agents (Claude Code) on Unity projects: which rules the agent follows, which process it runs for
each kind of task, how sessions are tracked, and how the rules improve over time.

Project-specific knowledge — a project's own rules, system docs and analysis tools — lives in a
separate **host project layer** repository. For Magic Match 3D that is **TripleMatchAiMetaData**,
documented in its own page tree.

## Contents

- **[[01_Setup|Setup]]** — installing the core framework in a Unity project
  - [[01_Setup#1. Clone and link the repository|1. Clone and link the repository]]
  - [[01_Setup#2. Create CLAUDE.md|2. Create CLAUDE.md]]
  - [[01_Setup#3. Install the session hooks|3. Install the session hooks]]
  - [[01_Setup#4. Link the core skills (slash commands)|4. Link the core skills (slash commands)]]
  - [[01_Setup#5. Verify|5. Verify]]
  - [[01_Setup#Requirements|Requirements]]
- **[[02_WorkModes|Work Modes and Routing]]** — how the agent picks a process and which files it loads
  - [[02_WorkModes#The five modes|The five modes]]
  - [[02_WorkModes#Loading rules on demand|Loading rules on demand]]
  - [[02_WorkModes#Delegation|Delegation]]
  - [[02_WorkModes#Stop and Verify|Stop and Verify]]
- **[[03_CreateFeature|Create Feature Process]]** — the 8-phase gated feature workflow, including checkpoint and resume
  - [[03_CreateFeature#Working folder|Working folder]]
  - [[03_CreateFeature#The phases|The phases]]
  - [[03_CreateFeature#Gate handoffs|Gate handoffs]]
  - [[03_CreateFeature#Working across sessions — checkpoint and resume|Working across sessions — checkpoint and resume]]
- **[[04_BugFix|Bug Fix Process]]** — symptom → diagnosis → approved fix → regression test
  - [[04_BugFix#Steps|Steps]]
  - [[04_BugFix#Key rules|Key rules]]
  - [[04_BugFix#What the retrospective expects to see loaded|What the retrospective expects to see loaded]]
- **[[05_SmallTask|Small Task Process]]** — bounded changes with a single proposal checkpoint
  - [[05_SmallTask#When it fits|When it fits]]
  - [[05_SmallTask#Steps|Steps]]
  - [[05_SmallTask#What the retrospective expects to see loaded|What the retrospective expects to see loaded]]
- **[[06_Investigation|Investigation Mode]]** — feasibility, comparison and design work that produces a document, not code
  - [[06_Investigation#Rules|Rules]]
  - [[06_Investigation#The output document|The output document]]
  - [[06_Investigation#Closing summary|Closing summary]]
- **[[07_SessionTracking|Session Tracking and Retrospectives]]** — metrics, router trace, corrections and the retrospective loop
  - [[07_SessionTracking#Lifecycle|Lifecycle]]
  - [[07_SessionTracking#Output|Output]]
  - [[07_SessionTracking#Retrospectives|Retrospectives]]
  - [[07_SessionTracking#The improvement gate|The improvement gate]]
  - [[07_SessionTracking#Meta-analysis report|Meta-analysis report]]
- **[[08_Commands|Command Reference]]** — the core slash commands
  - [[08_Commands#Session lifecycle|Session lifecycle]]
  - [[08_Commands#Feature work|Feature work]]
  - [[08_Commands#Analysis and review|Analysis and review]]
  - [[08_Commands#Reporting|Reporting]]
- **[[09_CodingRules|Coding Rules]]** — the non-negotiables, rule tags and rule files
  - [[09_CodingRules#Non-negotiables|Non-negotiables]]
  - [[09_CodingRules#Rule tags|Rule tags]]
  - [[09_CodingRules#Rule files|Rule files]]
  - [[09_CodingRules#Project rules|Project rules]]
- **[[10_HostProjectLayer|Host Project Layer]]** — what a project must provide for the core processes to work
  - [[10_HostProjectLayer#What a host layer provides|What a host layer provides]]
  - [[10_HostProjectLayer#Runnable tools the core processes expect|Runnable tools the core processes expect]]
  - [[10_HostProjectLayer#Paths the core processes assume|Paths the core processes assume]]
  - [[10_HostProjectLayer#Growing the host layer|Growing the host layer]]
- **[[11_Contributing|Contributing]]** — how to change a core rule, process, skill or tool
  - [[11_Contributing#Where a change belongs|Where a change belongs]]
  - [[11_Contributing#Where improvements come from|Where improvements come from]]
  - [[11_Contributing#Conventions|Conventions]]
  - [[11_Contributing#Publishing to Confluence|Publishing to Confluence]]
- **[[12_DocReview|Doc Review Tool]]** — local doc + diagram preview with in-page comments and the feature Progress tab
  - [[12_DocReview#Commands|Commands]]
  - [[12_DocReview#Commenting in the page|Commenting in the page]]
  - [[12_DocReview#Progress tab|Progress tab]]
  - [[12_DocReview#Tests|Tests]]

## Why this exists

Without guidance an agent guesses API signatures, drifts from our coding standards, skips
verification, and forgets everything between sessions. The framework fixes that with three
things:

- **Rules** — standards every generated line must meet (explicit types, Allman braces, no
  `ServiceLocator.Instance`, symmetric resource handling, project Logger only, and more).
- **Processes** — step-by-step workflows chosen by the kind of task: build a feature, fix a
  bug, make a small change, or investigate a question. Each has checkpoints where the engineer
  must confirm before the agent continues.
- **Feedback loop** — every session is measured (tokens, corrections, which rule files were
  actually loaded) and closed with a retrospective that proposes rule improvements.

## How it is organised

| Layer | Repository | Contains |
|---|---|---|
| **Core** (portable) | AIAgentCoreRules | Rules, Processes, Templates, Skills (slash commands), session-lifecycle tooling, this documentation |
| **Host project layer** | One per project — e.g. TripleMatchAiMetaData | Project rules, SystemIndex, Systems and SystemPatterns docs, Runnable analysis tools, project skills |

The core is linked under the project's externals folder. The host layer can live there or in
the project root as files committed to the project repository.

The project's `CLAUDE.md` imports a small set of always-on files. Everything else is loaded
**on demand**: the agent classifies the task, then reads only the rule and process files that
task needs. This keeps the agent's context budget free for the actual work.

## How a session flows

1. **Start** — a SessionStart hook creates a tracking folder for the session automatically.
2. **Classify** — the agent picks a work mode (feature, bug fix, small task, investigation,
   other) and records it.
3. **Load** — it reads the process file for that mode and the rule files the work touches.
4. **Work** — it follows the process, stopping at each gate for engineer confirmation.
5. **Correct** — the engineer logs agent mistakes with `/inaccuracy` and deliberate changes
   of direction with `/iteration`.
6. **Close** — `/end-session` compiles metrics and writes a retrospective with proposed rule
   changes, which the engineer approves or rejects.

**Source files:** [[MetaRouter|MetaRouter]] · [[README]]

---

[[01_Setup|Setup]] →
