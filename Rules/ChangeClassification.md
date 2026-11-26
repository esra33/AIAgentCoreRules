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

### External publish — color substitution

The `color:#ffffff` values above (the three change-tag `classDef`s and the `classDiagram` legend
`style` lines) are tuned for the local preview's dark theme only. Confluence and Miro are both
light-background, so the same value renders as invisible text there — on a `classDiagram`, `style
ClassName fill:...,color:#ffffff` colors the whole box, including the member/method compartment,
not just the tag label (found and fixed by hand on GameProgressSaveSlim's `ClassDiagram.mmd`
before this rule existed).

Keep the local `.mmd` source and the local preview's `#ffffff` unchanged — do not darken the local
copy to fix this. Instead, a Publish pass (see [[ExternalDocPass]]) that pushes a structural
diagram to Confluence or Miro must substitute `color:#ffffff` → `color:#172b4d` (the same navy
`existingStyle` already uses) in the **published copy only**, for every `classDef`/`style` line
that sets it. This is a deterministic substitution applied every such pass, not a per-diagram
judgment call made only after someone notices missing text.

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

## Diagram types and naming

A feature's `Diagrams/*.mmd` can hold up to four diagram types, each its own `.mmd` file, its
own artifact role (`Tools/feature-state/feature_state.py`'s `artifact_roles`), and its own tab
in the local preview (`Tools/doc-review/project_server.py`'s `TITLES`/`ROLES`). Name new
diagrams this way — the first time this is written down as a forward convention, not just a
legacy-alias list:

```yaml
diagram_types:
  framework_class_diagram:
    file:    "01a_FrameworkClassDiagram.mmd"
    syntax:  "mermaid classDiagram"
    shows:   "Shared contracts and the provider-independent types that implement or coordinate them. Show existing types where they clarify a dependency."
    colors:  "This file's 3(+1)-color NEW/MODIFIED/DELETED/existingStyle scheme — existingStyle is the common case here."
  concrete_class_diagram:
    file:    "01b_ConcreteClassDiagram.mmd"
    syntax:  "mermaid classDiagram"
    shows:   "Concrete types for a specific implementation, such as a provider adapter and the existing transport it uses."
    colors:  "Same change colors, with existingStyle for unchanged implementation dependencies."
  flow_diagram:
    file:    "02_FlowDiagram.mmd"
    syntax:  "mermaid flowchart"
    shows:   "Process/control flow — unchanged, see Scope above."
    colors:  "The general/decision/terminator/failure palette above, not this scheme."
  sequence_diagram:
    file:    "03_SequenceDiagram.mmd"
    syntax:  "mermaid sequenceDiagram"
    shows:   "Participants on lifelines and the messages they exchange in time order. Use loop and alternative blocks where repeated calls or branches matter."
    colors:  "Use Mermaid's default sequence styling. The flowchart palette is for flowchart nodes."
```

A feature with only the historical single class diagram (pre-dating this split) still works:
`legacy_migration.py` maps its old filenames (`01_ClassStructure.mmd`, `01_ClassDiagram.mmd`)
to `framework_class_diagram` — that single diagram already mixed framework context with the
feature's own types. Add `01b_ConcreteClassDiagram.mmd` when an implementation-specific view
helps explain how a selected provider or other specialization works. Existing
`03_LifeCycleDiagram.mmd` files remain available in the preview under their historical role.

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

Each item gets exactly this shape — a short TLDR visible, everything else collapsed:

```markdown
#### `TypeOrFileName`
TLDR — what this item is and why, scannable on its own with no need to expand.

<details>
<summary>More detail</summary>

- **Nature:** one line — what kind of change (new class, new interface, deleted file, …).
- **Reason:** one line — why this change exists.
- **Implementation:** 2–4 lines — concrete and checkable, not prose padding.

(anything beyond Nature/Reason/Implementation: deeper rationale, edge cases, gotchas, code
sketches)
</details>
```

The TLDR is prose, not a fourth labeled field — it exists so the heading list alone is useful
without expanding every item. Aim for ~5 lines or fewer; go longer only if the item genuinely
needs it to stand on its own — this is a guideline, not a hard cap. Never omit the `<details>`
block: unlike the old shape, Nature/Reason/Implementation now live inside it, so an item without
one would have nothing but the TLDR. The group heading is where the tag lives — don't repeat it
on the item heading too (`#### 🟢 NEW — \`X\`` under `### 🟢 New` says the same thing twice).

`Tools/doc-review/progress_view.py` tracks a TDD's drafted/approved status by diffing each
heading's whitespace-collapsed body against the template's placeholder text — it does not parse
the Nature/Reason/Implementation sub-structure, so moving those fields inside the collapsible is
safe for that tool. A template and a real TDD must still move together: re-verify this against
the current `progress_view.py` before relying on it again, since tooling can change after this
note is written.

### File Plan table

The existing `| Task | Path | New / Modified | Responsibility |` table's third column becomes
`Change`, using the same tags (adds Deleted, which the table never supported). A fifth column,
`Use Cases`, cross-references the use-case ids (see [[Phase1_Intake]]'s `id_convention`) the
task's change exists to satisfy — optional, blank for a task with no specific use case:

```markdown
| Task | Path | Change | Responsibility | Use Cases |
|---|---|---|---|---|
| T1 | relative/path/FileName.cs | 🟢 New | one-line description | SlimF8-F11 |
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
