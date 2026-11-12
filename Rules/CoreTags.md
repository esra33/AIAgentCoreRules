## apply: always

# Core Rule Tags

Short labels defined here once and referenced across all rule and process files.
Any file that uses a tag inherits the full definition below — no re-statement needed.

---

## Tag Definitions

| Tag | Rule |
|---|---|
| **[CTX]** | All required dependencies must be confirmed in context before generating. If anything is missing: look it up; if it cannot be found, STOP — do not generate, request the file. |
| **[SIG]** | No signature guessing. Every property, method, and field must be physically located in provided source text before use. |
| **[BEHAV]** | What an engine, library, API or CLI does at runtime is a hypothesis until grounded in its source, `--help`, docs or a run. State it as a hypothesis, with how to check it. |
| **[PRES]** | Preserve all existing comments, XML summaries, regions, and TODOs unchanged. |
| **[SURG]** | Surgical edits only — change only the required lines; surrounding code must be character-perfect. |
| **[SO]** | Unity ScriptableObjects: `CreateInstance<T>()` only, never `new T()`. |
| **[RES]** | Every resource acquisition (subscription, load, timer, guard) requires a matching release in the same logical scope. |
| **[SYM]** | Subscribe and unsubscribe must be in the same method pair — `SetUp/TearDown`, `Enable/Disable`, `SetupEvent/CleanupEvent`. |
| **[DI]** | No `ServiceLocator.Instance` — use constructor injection or `LazyService<T>`. |
| **[IFACE]** | Never cast to a concrete type inside a high-level system — widen the interface instead. |
| **[ASYNC]** | No `async void` except event handlers and synchronous overrides bridging into async. Bridging overrides must have a full `try/catch`. |
| **[SRP]** | One class or method = one reason to change. If the name needs "And", split it. |
| **[GEN]** | Auto-generated files must not be edited manually — re-run the generator tool instead. |
| **[EXPLICIT]** | No `var` — all types must be declared explicitly everywhere. |
| **[ALLMAN]** | Allman braces — `{` always on its own new line. |
| **[ACCESS]** | All access modifiers must be explicit on every member — no implicit defaults. |
| **[FIELD]** | No public fields — wrap in a property. Every injected dependency is `private readonly`. |
| **[LOG]** | All logging via the project Logger wrapper only. Never `UnityEngine.Debug.Log`, `Debug.LogWarning`, or `Debug.LogError`. In a `catch`: `_logger.Breadcrumb(...)` for a non-fatal context note (not surfaced in Crashlytics — e.g. "treat as absent" per an Edge Case decision); `_logger.Error("<custom message>")` followed by `_logger.Exception(e)` for a genuine failure that should be tracked in Crashlytics (real call-site shape: `Assets/Scripts/UI/MissionCenter/MissionCenterMissionView.cs:144-147`). |
| **[SECRET]** | Never print, echo, log or slice any part of a credential value. Check a credential's shape with booleans only; if a fragment leaks, say so and recommend rotating it. |
| **[TRIM]** | Tool output (bash stdout, file dumps, logs) stays out of context unless the task needs it or the engineer asks for verbosity — pipe through `tail`/`grep`/`head`, use `Read` with `limit`/`offset`, summarize instead of pasting raw output. Every call that re-reads a bloated result pays for it again. A `grep` for a C# type or member name always has an indexed equivalent (`grep -rn "SuperLightBall" Assets/Scripts` → `usages.py SuperLightBallManager`; "where is X declared" → `codeindex.py where X`). When the hook-bash hook suggests one, treat it as a hard redirect, not an FYI: stop, re-run the suggested command, and do not read on from the grep output. |
| **[DELEGATE]** | Breadth goes to subagents: any "where / which files / who implements" survey runs in an Explore agent (one per area, in ONE message), not inline. When and when not to: [[MetaRouter]]'s [DELEGATE] section. |
| **[SHAPE]** | A tool/script/report request hits the [[StopAndVerify]] Scope Gate (one-off vs reusable; Editor/runtime/CLI) before any exploration. |
