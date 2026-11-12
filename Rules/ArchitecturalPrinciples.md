## apply: on-demand — loaded by [[MetaRouter]]

# Architectural Principles

> Companion to [[CodingStandards]]. Enforces SOLID design at the structural level.
> Load when: designing classes, interfaces, system structure, or refactoring.

---

## S — Single Responsibility [SRP]

- One class = one reason to change.
- If a class name needs "And" or "Manager" to describe two unrelated things, split it.
- Prefer small, focused classes over large orchestrators.
- A class that mixes flow control, state tracking, and completion signalling is violating SRP. → See [[MultyStepOperationsRules]].

## O — Open / Closed [OCP]

- Extend behavior via new subclasses or strategy injection, not by editing existing logic.
- Use virtual/abstract hooks for variation points; seal stable paths.
- Adding a feature must not require modifying a tested class.

## L — Liskov Substitution [LSP]

- Every subclass must be usable wherever the base type is expected, with no surprises.
- Do not override a method to throw `NotImplementedException` or silently no-op.
- If a subclass cannot honor the base contract, prefer composition over inheritance.

## I — Interface Segregation [ISP]

- Interfaces must be narrow; callers depend only on what they use.
- Split a fat interface the moment a mock or stub would need to leave methods empty.
- One interface per behavioral role.
- **Split read-state from mutation.** Any interface that both exposes observable state and mutates it must be split into a readonly contract and a functional contract. The readonly interface extends nothing (or `IDisposable` if ownership is relevant); the functional interface extends the readonly one.

```csharp
// ✅ Callers that only observe get IReadonlyTimer
public interface IReadonlyTimer : IDisposable { ... }

// ✅ Callers that control get ITimer
public interface ITimer : IReadonlyTimer
{
    void Start();
    void Stop();
    ...
}
```

Pass the readonly interface to UI, analytics, and logging. Pass the full interface only to the owner that drives the object.

## D — Dependency Inversion [DIP]

- High-level modules depend on abstractions, not concrete types.
- Inject dependencies via constructor (managers) or `LazyService<T>` (everything else).
- [DI]
- [IFACE]

```csharp
// ❌ Breaks the abstraction boundary
((MissionCenterStageController)stageController).ForceComplete();

// ✅ Add the operation to the interface
stageController.ForceComplete();
```

### Create interfaces only as needed

An interface is a decoupling tool, not a default wrapper around every class. One interface per class inflates the API surface, doubles the files a developer must open to answer a single question, and forces a jump through an indirection that has exactly one implementation on the other side.

**Default to the concrete type.** Introduce an interface when one of the two triggers below applies — then it is mandatory, not optional.

#### Trigger 1 — Polymorphism

The high-level system must interact with the contract only and stay agnostic of implementation details.

```yaml
signals:
  - Two or more implementations exist, or the next one is already scoped.
  - The concrete type is selected at runtime (config, factory, platform, event category).
  - A test double is substituted into a production system.
```

`IGemUserEventPointer<TConfig, TUserData>` qualifies: the event system drives the pointer contract and never learns whether it holds the live GEM-backed pointer or `DummyGemEventPointer<TConfig, TUserData>` from the test assembly.

#### Trigger 2 — Reducing exposure

The owner needs the full type; the outside world must see less. The field keeps the mutable type, the property hands out the narrow contract.

```csharp
// ✅ Owner mutates the list; callers can only read it
private readonly List<GemEvent> _activeEvents = new List<GemEvent>();
public IReadOnlyList<GemEvent> ActiveEvents => _activeEvents;
```

The same reasoning applies to a class's own surface: when only part of its members are safe for callers, declare that subset as an interface and hand out the interface — this is the read-state / mutation split under [ISP] above.

#### Not a reason to add an interface

```yaml
insufficient_reasons:
  - "It might get a second implementation someday." → add the interface when that implementation arrives.
  - "Every other class in the folder has one."
  - "To make it mockable." → a concrete instance or a Dummy subclass is enough unless Trigger 1 applies.
  - "It looks more decoupled." → IFoo sitting next to a lone Foo is indirection, not decoupling.
```

#### The test

> Would a caller ever hold a *different* implementation, or need to see *fewer* members than the concrete type exposes?

No to both → no interface. Yes to either → the interface is required, and the public surface must expose it rather than the concrete type.

---

## Composition over Inheritance

Avoid deep concrete class inheritance chains. They create tight coupling and make classes difficult to refactor. Interface-based `is-a` is fine — the problem is chaining concrete implementations.

- Implement interfaces freely — they are contracts, not coupling.
- Extend a concrete base class only one level deep. If a second extension is needed, extract the shared behavior into a composed object instead.
- Extract independent concerns into focused controller/handler objects and hold them as fields.
- The owning class exposes their contracts as properties — never the concrete type.

```csharp
// ✅ MissionCenterEvent owns controllers, does not inherit from them
public EventTimerController timerController { get; }
public MissionCenterStageController stageController { get; }
```

Multi-step sequences are a common composition target — an async loop runner is a composed object, not a base class. → See [[MultyStepOperationsRules]].

---

## Assembly Structure *(Unity projects)*

New high-level systems and services must live in their own `.asmdef` subassembly — not in the main assembly.

**Coupling test:** "Would this system compile cleanly in a separate assembly with only its declared dependencies?" If yes, it belongs in a subassembly. If not, extract the coupling first.

```yaml
assembly_rules:
  - New system → new .asmdef subassembly.
  - Main assembly is only for code with unavoidable cross-cutting coupling.
  - Test assemblies mirror the assembly they test: MySystem.Tests.asmdef tests MySystem.asmdef.
  - Never add a reference from a lower-level assembly to a higher-level one.
```

---

## Hard Rules

```yaml
hard_rules:
  - Do not add a dependency unless its interface is in scope — request the source if missing.
  - "[SRP] Do not merge two responsibilities into one class to save files."
  - New behavior requires a new class or override — not a flag on an existing method.
  - "[DIP] Add an interface only for polymorphism or to reduce exposure — never one interface per class by default."
  - "[DIP] When either trigger applies, the public surface must expose the interface, never the concrete type."
  - Never expose a mutable collection field — the property returns the readonly contract.
  - Split any interface mixing read-state and mutation into readonly + functional contracts.
  - Avoid concrete inheritance chains deeper than one level — compose instead.
  - "Multi-step/multi-frame sequences use an async loop, not a callback pump. → [[MultyStepOperationsRules]]"
```
