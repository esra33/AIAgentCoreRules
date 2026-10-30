# Host Project Layer

The core framework is project-agnostic. Each project that uses it supplies a **host project
layer**: a separate repository with the project's own rules, system knowledge and tooling. The
core processes refer to these pieces by role, so a project that provides them gets the full
benefit of every process.

For Magic Match 3D the host layer is **TripleMatchAiMetaData** — see its own documentation.

## What a host layer provides

| Piece | Purpose | Used by |
|---|---|---|
| **Project rules** (always loaded) | Project-wide conventions the core rules cannot know: logging wrapper setup, release-build guards, config loading, forbidden file types | Every process, `/audit` |
| **SystemIndex** (always loaded) | A router for project knowledge: maps task phrases to the right Systems or SystemPatterns doc | Discovery in every process |
| **Systems/** | One overview per game system: responsibility, key interfaces, entry point, integration points, **common gotchas** | Bug Fix step 2, Small Task step 2, Create Feature Phase 2, `/discover` |
| **SystemPatterns/** | Step-by-step guides for building a feature in a system | When writing the TDD Architecture (Create Feature Phase 1) and in the Phase 3 design delta, Small Task step 2 |
| **Testing setup** | Project test infrastructure: container setup, test doubles, assertion helpers | Bug Fix step 6, Create Feature Phase 5 |
| **Runnable tools** | Scripts that verify work or answer structural questions without reading files | See below |
| **Project skills** | Extra slash commands wrapping the Runnable tools | Optional |

## Runnable tools the core processes expect

The core process files name these tools directly. A host layer that uses different tools
should keep the same roles.

| Role | Name in the core processes | Question it answers |
|---|---|---|
| Compile check | `typecheck.py` | Does my change compile? Required before any multi-file C# change is reported complete. |
| Code index | `codeindex.py` | What members does a type have, where is it declared, who implements or derives from it? |
| Usages | `usages.py` | Who uses a type, and which sites call specific members? |

The session metrics count how often each Runnable tool ran, and retrospectives check them
against what the lane expected.

## Paths the core processes assume

These locations are set in the core process files and are personal, git-ignored folders in the
host project:

| Output | Path | Set in |
|---|---|---|
| Feature working folder | `Assets/GitIgnoreAssets/Features/<FeatureName>/` | `Processes/CreateFeature/index.md` |
| Investigation documents | `Assets/GitIgnoreAssets/DesignDocuments/<Topic>.md` | `Rules/InvestigationMode.md` |
| Session reports | `GitIgnoreReports/Sessions/` | `Tools/session-lifecycle` (override with `SESSION_REPORTS_ROOT`) |

## Growing the host layer

The layer improves through use. After Phase 2 Discovery, or after `/discover` maps a system
with no entry, the agent offers to save the map as a new Systems doc. Retrospectives trace
corrections with the root cause `missing-index-entry` to a concrete Systems or SystemPatterns
change.

**Source files:** [[CreateFeature/index]] · [[InvestigationMode]] · [[MetaRouter]]

---

← [[09_CodingRules|Coding Rules]] · [[00_Overview|Overview]] · [[11_Contributing|Contributing]] →
