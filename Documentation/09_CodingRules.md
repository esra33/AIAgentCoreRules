# Coding Rules

The standards every piece of agent-generated code must meet. They are enforced by the process
checklists, by `cslint.py` (the mechanical tags, run by a hook on every `.cs` edit) and by
`/audit` (the judgement review).

## Non-negotiables

| Tag | Rule |
|---|---|
| EXPLICIT | No `var` — explicit types everywhere. |
| ALLMAN | Allman braces — `{` always on its own line. |
| FIELD | No public fields, ever — wrap in a property. Every injected dependency is `private readonly`. |
| ACCESS | Every member has an explicit access modifier. |
| DI | No `ServiceLocator.Instance` — use constructor injection or `LazyService<T>`. |
| IFACE | Never cast to a concrete type inside a high-level system — widen the interface instead. |
| RES | Every resource acquisition (subscription, load, timer, guard) has a matching release in the same scope. |
| ASYNC | No `async void` except event handlers and synchronous overrides bridging into async, which must have a full try/catch. |
| LOG | All logging through the project Logger wrapper — never `Debug.Log`, `Debug.LogWarning` or `Debug.LogError`. |
| DELEGATE | Breadth goes to subagents: "where / which files / who implements" questions are delegated, and so is multi-round exploratory/trial-and-error work (browser-automation probing, iterative debug scripts) — only the final working script and its conclusion need to come back. |
| SHAPE | A tool, script or report request goes through the scope gate before any exploration. |
| TRIM | Tool output stays out of context unless the task needs it or verbosity is requested — pipe through `tail`/`grep`/`head`, use `Read` with `limit`/`offset`, summarize instead of pasting raw output. A grep for a C# type or member name has a `usages.py` / `codeindex.py` equivalent; the hook-bash suggestion is a hard redirect — re-run the suggested command instead of reading the grep output. |

## Rule tags

Short labels used across all rule and process files. Beyond the non-negotiables above:

| Tag | Rule |
|---|---|
| CTX | Every required dependency is confirmed in context before generating; if missing, look it up, and if it cannot be found, stop and ask. |
| SIG | No signature guessing — every property, method and field is located in source before use. |
| PRES | Existing comments, XML summaries, regions and TODOs are preserved unchanged. |
| SURG | Surgical edits — only the required lines change. |
| SO | ScriptableObjects are created with `CreateInstance<T>()`, never `new T()`. |
| SYM | Subscribe and unsubscribe live in the same method pair (SetUp/TearDown, Enable/Disable). |
| SRP | One class or method, one reason to change. If the name needs "And", split it. |
| GEN | Auto-generated files are never edited by hand — re-run the generator. |

## Rule files

Loaded on demand by the routing table (see [[02_WorkModes#Loading rules on demand|Work Modes and Routing]]).

| File | Covers |
|---|---|
| **Coding Standards** | Naming and semantic naming; file organization (constants → delegates → events → fields → properties → constructors → methods); accessibility (hidden fields, most restrictive setters); method design (single responsibility, readable composition, size heuristics, guard clauses, mathematical integrity, async from synchronous overrides, Try-pattern over direct get); auto-generated files. |
| **Architectural Principles** | SOLID applied to our code, creating interfaces only as needed, composition over inheritance, Unity assembly structure, hard rules. |
| **Multi-Step Operations Rules** | Favour an async loop over the callback-pump pattern; bridging callback-based APIs; state tracking; guarding against mutation during execution. |
| **Resource Management Rules** | The symmetry principle; `IDisposable` scoped state instead of boolean flags; event subscriptions; Addressables. |
| **Testing Rules** | Container setup, test doubles, assertions, state reset, async tests, naming, **idle-behavior tests for poll handlers and event listeners** (verify state unchanged across multiple ticks when data has not changed). |

## Project rules

Each host project adds its own always-loaded rules on top of these — logging wrapper setup,
release-build guards, config loading and similar. See the host project's documentation.

**Source files:** [[CoreTags]] · [[MetaRouter]] · [[CodingStandards]] · [[ArchitecturalPrinciples]] · [[MultyStepOperationsRules]] · [[ResourceManagementRules]] · [[TestingRules]]

---

← [[08_Commands|Command Reference]] · [[00_Overview|Overview]] · [[10_HostProjectLayer|Host Project Layer]] →
