# Technical Design Document — [Feature Name]

> Fill all sections. This document is the output of Phase 1 and the input for Phase 2 Discovery. Phase 3 Design updates it in place (File Plan, resolved TBDs, diagram changes) — it is the feature's only design document.

---

# TDD Title

**Legend:** **⚠️ DESIGN** marks items that need a design answer before they can be finalized —
give each one an owner (due at kickoff, or sooner if it blocks a stage). **🔧 ENGINEERING** marks
items that still need engineering alignment before they can be finalized — give each one an owner
too. Remove either tag from this line if the document ends up not using it.

**Table of Contents**
- Objective
- Architecture
- Best Practices
- Related documentation
- Development plan
  - Stage Level (ie V0, V1 …)
  - Final touches
- Design And Support Tools
- Risks
- Data Reconciliation Strategy
- CS Strategy
- Edge Cases [Optional]
- CMS Data Pipeline [Optional — only for Airtable-driven or OTA-configurable content]
- Other Notes [Optional]
- Future Work
- Versions
  - 1.0.0

## Objective
[Insert summary of the system]

## Architecture
[Describe the high-level components and how they interact. Replace this bracket entirely — do not
leave it alongside the Architecture Diagrams subsection below once this section has real content.]

### Files & Types Changed
[Every file/type this section names, classified per [[ChangeClassification]]. Exact paths may still
be TBD before Phase 2 Discovery — classify by type anyway. State "None for this feature" under an
empty group rather than omitting it.]

### 🟢 New

#### `TypeOrFileName`
- **Nature:** [one line]
- **Reason:** [one line]
- **Implementation:** [2–4 lines, concrete and checkable]

<details>
<summary>More detail</summary>

[anything beyond the three lines above]
</details>

### 🟡 Modified

### 🔴 Deleted

### Architecture Diagrams [Optional — only if the architecture includes diagrams]
[Diagram sources live in `Diagrams/*.mmd` (classDiagram / sequenceDiagram / flowchart). Validate
every diagram locally before embedding it here or pushing it to a board — see "Validating a local
diagram" in [[ExternalDocPass]]. A structural diagram (class/component) uses
[[ChangeClassification]]'s NEW/MODIFIED/DELETED colors and legend; a process-flow diagram uses its
own separate palette, also defined there. Embed each diagram inline, right here, in its own
collapsible block so the document stays self-contained:

<details>
<summary>Mermaid Diagram: <Name></summary>

<one line describing what this diagram shows>

```mermaid
<diagram source>
```

</details>

Publishing to a Miro board follows the same file's "Diagrams reviewed on a board" section: iterate
the local source against a local render, push once per Publish/Review pass, never per revision. Its
Miro embed/frame links live in the page published to Confluence (see the host's doc-conventions
file), not in this local Markdown copy.]

### File Plan
[Filled or completed in Phase 3 from the Discovery report; Phase 4 works through it task by task.
May be partly filled in Phase 1 when the files are already known.]

| Task | Path | Change | Responsibility |
|---|---|---|---|
| T1 | | | |

## Best Practices
[Rules an implementer of this feature must follow, grouped by the strongest mechanism that can
realistically enforce each one: compile-time > generator/CI > test-time (a failing build or test)
> runtime guard > scaffolded (a wizard/tool gets it right by default) > process (code review only,
when nothing stronger is feasible). A rule that can't be enforced by anything stronger than
"remember to" is a rule that gets skipped — sort for the strongest mechanism before settling for
process.]

## Related documentation
[Insert links to related documentation]

## Development plan

[The `#` column is the task id (T1, T2 …), unique across the whole plan and never renumbered.
/publish-batch names the task's branch and PRs after it, and the doc-review Progress tab shows
the task's batch progress next to it.]

### Stage Level (ie V0, V1 …)
* **Level of effort:** [Insert t-shirt size plus estimate in days]

| # | Title | Task | Assignee | **Status** |
| --- | --- | --- | --- | --- |
| T1 | Sample task | Sample Task | Andrea Ramirez | [ ] |
| T2 | Designer show and tell | Show and tell to designer! | Andrea Ramirez | [ ] |

### Final touches
* **Level of effort:** At least 5 days.

| # | Title | Task | Assignee | **Status** |
| --- | --- | --- | --- | --- |
| T3 | Data reconciliation | Implement and validate data reconciliation strategy | Andrea Ramirez | [ ] |
| T4 | CS gifting | Implement CS Gifting Strategy | Andrea Ramirez | [ ] |
| T5 | BI calls | Add BI calls | Andrea Ramirez | [ ] |
| T6 | Unit tests | Add Unit Tests | Andrea Ramirez | [ ] |
| T7 | Design and support tools | Implement design and support tools | Andrea Ramirez | [ ] |
| T8 | QA debug functionality | Implement QA Debug functionality | Andrea Ramirez | [ ] |
| T9 | RST backport | Backport Systems to RST | Andrea Ramirez | [ ] |

## Design And Support Tools
List of tools and mechanisms that the feature will need long term. Following are some examples:
* Importing from Air Table or other source of truth.
* Testing in JCL vs Local.
* Taking snapshots of the feature to rout to Disney.
* Configuring an asset in Unity.

## Risks
* Risk to take into consideration
* Risk resolution, amortization or workaround

## Data Reconciliation Strategy
[How the feature will handle data reconciliation?]

## CS Strategy
[How the feature will handle CS Gifting?]

## Edge Cases [Optional]

| **#** | **Edge Case** | **Solution** |
| --- | --- | --- |
| 1 | On an event, what happens if the event is about to end and the player makes progress? | |
| 2 | What happens if the player closes the game during a progress point for an event that is ending or just ended? | |
| | Edge case description. | How it is handled |

## CMS Data Pipeline [Optional — only for Airtable-driven or OTA-configurable content; omit entirely otherwise]

### Airtable

| **Airtable Name** | **Description** | **Unity Import or Export?** |
| --- | --- | --- |
| [Table name — note if it is a new table or an existing one being extended] | [What it holds] | [Import into Unity / Export from Unity] |

### Unity Data And Serialization

| **Data Type** | **Data Destination Directory** | **Root vs Event vs other** | **JSON vs ScriptableObject** |
| --- | --- | --- | --- |
| [Type] | [Path] | [Root player data / Event config / Asset / Installer] | [JSON / ScriptableObject] |

### JCL Integration / Live ops

- **Feature switch:** [How this feature is turned on/off — a config flag, GEM scheduling, etc.]
- **Maintenance:**
    - How is new content added? → [...]
    - How often? → [...]
    - Who is intended to maintain it? → [Design / Live Ops tech / TechArt, per responsibility]
- **OTA vs. client split:**
    - **Client (requires build):** [new C# code, new prefab wiring, anything bundled with the client]
    - **OTA (LiveUpdate):** [config data pushed through JCL, Addressable assets, anything that ships without a build]

## Other Notes [Optional]
[Optional, any additional information not easily captured in the standard sections]

## Future Work
[Any future work that could be added to this system]

## Versions

### 1.0.0
First pass, added all tickets, architecture and first set of notes.

