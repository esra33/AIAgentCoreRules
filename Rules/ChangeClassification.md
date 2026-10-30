## apply: on-demand — loaded by [[MetaRouter]], [[Phase1_Intake]], [[Phase3_Design]], [[ExternalDocPass]]

# Change Classification — NEW / MODIFIED / DELETED

Standard for documenting what a feature touches: every file or type a TDD's Architecture section
or File Plan names is classified **NEW**, **MODIFIED**, or **DELETED**, with a terse, scannable
summary and the same three colors carried into its structural diagrams.

This formalizes a scheme `RemoteDebugger_TDD.md` already used on its own (one-off, never written
down here). It is now the project standard — no edit is needed to `RemoteDebugger_TDD.md` itself,
it already conforms.

---

## The three-way tag

```yaml
tags:
  new:      "🟢 NEW — does not exist yet."
  modified: "🟡 MODIFIED — exists, behavior or shape changes."
  deleted:  "🔴 DELETED — exists today, removed by this feature."
```

Prose and tables use the emoji + bold label (`🟢 **NEW**`, `🟡 **MODIFIED**`, `🔴 **DELETED**`) —
portable across GitHub markdown, Confluence, and the local doc-review preview's `marked.js`
renderer. Do not use inline CSS spans for this: Confluence's storage format can strip them.

### Mermaid `classDef` colors (structural diagrams only — see scope below)

```
classDef newStyle      fill:#1f7a4d,stroke:#2ea043,stroke-width:2px,color:#ffffff;
classDef modifiedStyle fill:#7a6a1f,stroke:#d4a72c,stroke-width:2px,color:#ffffff;
classDef deletedStyle  fill:#7a1f24,stroke:#e5484d,stroke-width:2px,color:#ffffff;
classDef existingStyle fill:#dcdfe4,stroke:#626f86,color:#172b4d;
```

`existingStyle` is a 4th, neutral tag for a framework or unchanged type shown only for context
(e.g. `IPlayerData`, `HomeFlowAction`) — it is not one of the three change tags and never appears
in a file/type list, only in a diagram.

These exact hex values are `RemoteDebugger_TDD.md`'s own (`newStyle`/`modifiedStyle`/`deletedStyle`);
`existingStyle` is GameProgressSave's pre-existing "framework" grey. Picked over inventing a fourth
palette because they already render correctly in the local preview, which is hard-coded to
`theme: "dark"` (`Tools/doc-review/review_server.py`).

### Legend, per diagram type

A diagram using these colors carries its own legend, so it is self-explanatory even viewed alone
(e.g. the local preview's own tab for that `.mmd`, outside any surrounding document text):

- **Flowchart**: an in-diagram `subgraph Legend[...]` box, one node per tag —
  `RemoteDebugger_CurrentState_Components.mmd`'s exact pattern:
  ```
  subgraph Legend["Legend — change status"]
      direction LR
      LNEW["NEW"]
      LMOD["MODIFIED"]
      LDEL["DELETED"]
  end
  ...
  class LNEW newStyle
  class LMOD modifiedStyle
  class LDEL deletedStyle
  ```
- **classDiagram** (no `subgraph` support): three small marker classes instead, styled the same way:
  ```
  class LegendNew["🟢 NEW"]
  class LegendModified["🟡 MODIFIED"]
  class LegendDeleted["🔴 DELETED"]
  style LegendNew fill:#1f7a4d,stroke:#2ea043,color:#ffffff
  style LegendModified fill:#7a6a1f,stroke:#d4a72c,color:#ffffff
  style LegendDeleted fill:#7a1f24,stroke:#e5484d,color:#ffffff
  ```
  (classDiagram styles individual classes with `style ClassName fill:...`, not `classDef`/`class`
  grouping — see any existing `ClassDiagram.mmd` for the pattern.)

---

## Scope: structural diagrams only

This 3(+1)-color scheme applies to diagrams that depict **files or types** — class diagrams,
component diagrams, a file/type dependency graph. It does **not** apply to a **process-flow**
diagram (a flowchart or sequence diagram showing control flow, e.g. `ResumeFlow.mmd`,
`ForgivenessFlow.mmd`) — a flow step is not a file or a type, and recoloring it NEW/MODIFIED/DELETED
has no meaning. Flow diagrams keep their own, separate, already-used palette instead:

```
classDef general     fill:#FFE86D,stroke:#A28E26,color:#574900;   /* an ordinary step        */
classDef decision     fill:#9CE6FF,stroke:#2C97BB,color:#1C4657;  /* a branch point           */
classDef terminator  fill:#B3E65F,stroke:#6E9A24,color:#2F440B;   /* flow start/end           */
classDef failure      fill:#FFB575,stroke:#CC7830,color:#542700;  /* an error/failure path    */
```

(From `ResumeFlow.mmd`, also now used by `ForgivenessFlow.mmd` — written down here for the first
time; no values changed.)

---

## File/type list format

Used in a TDD's **Architecture** section (Phase 1, type-level — exact paths may still be TBD,
pending Phase 2 Discovery) and in its **File Plan** (Phase 3/4, file-level, exact paths).

Group items under three headings, in this order, every time — state "None for this feature"
explicitly rather than omitting an empty group (same convention already used for Best Practices /
Data Reconciliation when a feature has nothing to say there):

```markdown
### 🟢 New
### 🟡 Modified
### 🔴 Deleted
```

Each item gets exactly this shape — three lines visible, anything beyond that collapsed:

```markdown
#### `TypeOrFileName`
- **Nature:** one line — what kind of change (new class, new interface, deleted file, …).
- **Reason:** one line — why this change exists.
- **Implementation:** 2–4 lines — concrete and checkable, not prose padding.

<details>
<summary>More detail</summary>

(anything beyond the three lines above: deeper rationale, edge cases, gotchas, code sketches)
</details>
```

Omit the `<details>` block entirely when there is nothing beyond the three lines — an empty
collapsible is worse than no collapsible. The group heading is where the tag lives — don't repeat
it on the item heading too (`#### 🟢 NEW — \`X\`` under `### 🟢 New` says the same thing twice).

### File Plan table

The existing `| Task | Path | New / Modified | Responsibility |` table's third column becomes
`Change`, using the same tags (adds Deleted, which the table never supported):

```markdown
| Task | Path | Change | Responsibility |
|---|---|---|---|
| T1 | relative/path/FileName.cs | 🟢 New | one-line description |
```

---

## Common gotchas

```yaml
gotchas:
  - "A type named in Phase 1 Architecture before Discovery has run may not have a real file path yet — classify by type, mark the path TBD, and let Phase 3's File Plan pin down the exact path."
  - "Don't force every node in a structural diagram into NEW/MODIFIED/DELETED: a framework type shown only for context is existingStyle, not one of the three tags."
  - "Don't recolor a process-flow diagram with this scheme — it has its own palette (see Scope above)."
  - "mermaid classDiagram has no subgraph; use the marker-class legend form, not the flowchart subgraph form, or mmdc will fail to parse it."
```
