# Spike #70: search strategy for the adaptive attacker

**Status: draft, agent-produced, NOT binding.** This file is the deliverable of spike #70. It cannot be
landed by an agent because its destinations are protected paths. A human must:

1. move **Part A** to `docs/adr/0009-adaptive-search-strategy.md` (status `accepted`),
2. merge **Part B** into `docs/architecture/interfaces.md` (new `## L3: verifi.adaptive (Phase 3)` section),
3. add the proposed `adaptive.search` row to `docs/architecture/cli-contract.md`, and
4. hand **Part C** to the planner/triager for #71.

Part A is the ADR in final prose so it can be moved with only a status edit. The analysis uses the
*dream-rsi* method (self-improving exploration for expensive, repeated discovery) as a lens only; it
adds no dependency and no new runtime code.

---

## Part A — ADR-0009 (draft)

# ADR-0009: Adaptive attacker searches mutator arms with a deterministic bandit first

- Status: proposed (draft; to become `accepted` when moved to `docs/adr/`)
- Date: 2026-09-23

## Context

Phase 3 turns the fixed attack packs of Phase 2 into a search: verifi must *discover* attacks it was not
given. #71 must show an adaptive run finding at least one successful mutated case that the static pack
missed, within a fixed episode budget, against a susceptible `scripted` target.

That search has three properties that decide the design:

- **Evaluation is expensive.** Every candidate is an *episode*: a full target run through the sandbox and
  broker, charged against `budget` (steps, tokens, wall clock).
- **The score is already trustworthy.** A candidate succeeds iff its `AttackCase.success` predicate
  matches **trusted evidence** (INV-1). The Phase-2 `injection` detector already computes exactly this;
  nothing needs to be read from the transcript.
- **The search repeats.** It runs on every CI run and every spec revision, and #69 stores successful
  `(case, mutation chain, seed)` tuples as a private regression pack — a growing pool of recorded
  outcomes.

This is the shape the *dream-rsi* method targets: when an automatic evaluator scores candidates, each
evaluation is expensive, and the same search will run again, the durable win is to make the search policy
explicit and deterministic and to **record every attempt as a tree**, so the policy can later be improved
offline by replaying history without paying for new episodes. Two of that method's invariants constrain
us: **replay is prefix-observable** (a policy sees only revealed nodes) and **no generation happens during
replay** (an unrecorded branch is empty, not invented).

Options considered: (1) multi-armed bandit over `(case, mutator)` arms; (2) evolutionary search over
payloads; (3) LLM attacker proposing from failure feedback; (4) hybrid bandit-selection + LLM-proposal.

## Decision

**Adopt a deterministic multi-armed bandit over `(attack case, mutator chain)` arms for the first
adaptive attacker (Phase 3a).** Shape the policy and the recorded tree so that an LLM proposer (3) and an
evolutionary payload search (2) can later be added as alternative arm sources/policies without changing
the loop, the reward, or the evidence path.

Concretely:

1. **Arms are finite and enumerable:** `(case_id, mutator_ids[])` drawn from the spec's packs and the
   Phase-2 mutators (#60). The empty chain is the unmutated case, kept as a control arm.
2. **Reward is trusted-evidence-only.** `success = 1` iff the `injection` detector matches the mutated
   case's `SuccessPredicate` in that episode's trusted evidence. Transcript content never influences the
   search (INV-1). Severity may weight the reward later; the MVP uses binary success.
3. **Policy is code, deterministic, and batched.** A policy answers
   `select(tree, eligible, width) -> arms[]` (`()` = stop). MVP algorithm: UCB1 with deterministic
   tie-breaking; the RNG is seeded from `spec.attacks.seed`. Evaluating a batch of `width` arms is one
   round, matching the method's cost model (reward the best success, penalise episodes spent, reward
   batching).
4. **Record the search tree.** Every attempt is a node
   `(parent, arm, seed, episode_id, success, control_ids, evidence_ids, steps, tokens)`, persisted under
   the run directory. This is the replay substrate; the MVP does not yet improve the policy offline.
5. **Stop** on the first success (the MVP objective) or when the adaptive budget is exhausted, then
   export successes to the #69 regression store.
6. **Defer** the LLM attacker and evolutionary search to Phase 3b behind the same `AdaptivePolicy` seam.

## Why the bandit first (dream-rsi axes)

| Axis | Bandit over mutators | Evolutionary | LLM attacker | Hybrid |
|---|---|---|---|---|
| Candidate cost | low authoring (reuses #60); evaluation dominates | evaluation-dominated; needs a payload grammar | extra model call per proposal + evaluation | extra model call |
| Sample efficiency at a small budget | high — space is small and enumerable | poor early | high iff priors are good, else expensive | medium |
| Determinism / replay (INV-7) | yes: seeded, discrete arms, scripted target | yes if seeded, but noisy fitness | no: nondeterministic endpoint | no |
| Testable without infrastructure | yes (`FakeSandbox` + `ScriptedTarget`) | yes | no (endpoint + network + new dependency) | no |
| Expressiveness | limited to existing cases × mutators | high over payload space | highest (semantic, multi-turn) | high |
| Verdict integrity | reward is a `SuccessPredicate` over trusted evidence | same | same, but feedback must stay trusted-only and never leak payloads (INV-6) | same |

The decisive constraints are determinism, offline testability, and budget. With the current attack model
the candidate space is a small finite set, so the bandit is near-optimal *and* provably reaches any
reachable success within at most `|arms|` episodes (UCB1 tries every arm before exploiting). Evolutionary
search would spend the MVP budget rediscovering what the bandit finds immediately, and crossover needs a
payload grammar that does not exist yet. The LLM attacker breaks INV-7, needs an endpoint and a new
dependency, and cannot run in the gate, so it cannot be the first, testable implementation.

The bandit also fits the method's staging: the recorded tree *is* the pool. Once arms include generated
payloads (3b) the arm space stops being enumerable and offline policy improvement over the recorded trees
becomes worth its cost — at which point an LLM/evolutionary proposer plugs in as another `AdaptivePolicy`
and the loop, reward, and evidence path are unchanged.

## Consequences

- #71 delivers a deterministic, hermetic adaptive loop: `FakeSandbox` + `ScriptedTarget` + seeded bandit
  gives byte-identical `adaptive/tree.json` and result (INV-7).
- A new user-facing operation must be added to `docs/architecture/cli-contract.md` (protected) before or
  with #71. Proposed: `adaptive.search` → `verifi adaptive search SPEC_PATH`.
- The adaptive loop drives **episodes**, not whole runs, so the orchestrator needs a small reusable seam
  that provisions once and runs a supplied episode list (Part B). Without it #71 would either re-provision
  a sandbox per attempt or duplicate orchestrator logic.
- Phase 3b adds a `Proposer` (LLM/evolutionary) as an alternative policy. It must stay outside the verdict
  path and must not put private payloads into reports/logs (INV-6).
- No new runtime dependency is introduced by this decision (`random` is stdlib).

## Alternatives rejected

- **Evolutionary first** — high ceiling, but no payload grammar, poor sample efficiency at the MVP budget,
  and it adds no determinism. Deferred to 3b, not rejected permanently.
- **LLM attacker first** — highest ceiling, but nondeterministic, expensive, needs network/a model
  endpoint in tests, and is untestable in the gate. Deferred to 3b.
- **Hybrid first** — inherits the LLM's nondeterminism with none of the bandit's testability. Build the
  deterministic core first.

### Assumptions and limits (where the method does not transfer cleanly)

- Replay-based policy improvement assumes a deterministic evaluator. A stochastic `openai-compatible`
  target makes the recorded tree only *approximately* replayable; that is a 3b concern, not the MVP's.
- The method's batching term rewards opening many nodes per round. verifi's episodes may be
  resource-bound rather than parallel, so `width` is a scheduling knob, not a speed claim.
- The regression store (#69) is the durable pool; the MVP records into it but does not dream over it.

---

## Part B — proposed `verifi.adaptive` interfaces

Proposed addition to `docs/architecture/interfaces.md`. Layer: **L3** (may import L2 components and
`verifi.runs.orchestrator`). Names are proposals until a human lands them; #71 must copy them exactly
once accepted.

```python
## L3: `verifi.adaptive` (Phase 3)

# models.py
class Arm(BaseModel):
    id: str                               # materialized case id: case_id or "case~mut1~mut2~n"
    case_id: str                          # source case
    mutator_ids: tuple[str, ...] = ()     # () = the unmutated case (control arm)
    seed: int

class Attempt(BaseModel):                 # one node of the search tree
    id: str                               # "att_" + sha256_json({parent_id, arm.id, seed})[:24]
    parent_id: str | None
    arm: Arm
    episode_id: str | None
    success: bool                         # SuccessPredicate match over TRUSTED evidence only
    control_ids: tuple[ControlId, ...]
    evidence_ids: list[str] = []          # trusted evidence backing `success`
    steps: int; tokens: int
    created_at: datetime

class SearchTree(BaseModel):
    run_id: str; seed: int
    attempts: list[Attempt] = []
    def add(self, attempt: Attempt) -> None: ...
    def children(self, node_id: str | None) -> list[Attempt]: ...   # None -> roots
    def revealed(self) -> int: ...                                  # non-root attempts (cost proxy)
    def best(self) -> Attempt | None: ...                           # deterministic tie-break

class AdaptiveResult(BaseModel):
    run_id: str; seed: int
    rounds: int; attempts: int; successes: int
    best_attempt_id: str | None
    remaining: dict[str, int]
    exported_pack: str | None             # from verifi.adaptive.regression_store (#69)

# policy.py
class AdaptivePolicy(Protocol):
    id: str
    def select(self, tree: SearchTree, eligible: Sequence[Arm], width: int) -> Sequence[Arm]: ...
    # deterministic for a given (tree, eligible, width, seed); () means stop

class BanditPolicy:
    def __init__(self, *, algorithm: Literal["ucb1"] = "ucb1", exploration: float = 1.0,
                 rng: random.Random) -> None: ...

# loop.py
class AdaptiveLoop:
    def __init__(self, ctx: AppContext, *, orchestrator: Orchestrator, policy: AdaptivePolicy,
                 packs: Sequence[AttackPack], mutators: Sequence[Mutator],
                 regression_store: RegressionStore) -> None: ...
    def search(self, locked: LockedSpec, *, seed: int, width: int = 4,
               max_episodes: int | None = None) -> AdaptiveResult: ...
    # writes run_dir/adaptive/tree.json and adaptive/result.json; exports successes via #69

# operations.py
# adaptive.search -> CLI `verifi adaptive search SPEC_PATH` (row to confirm in cli-contract.md)
```

Proposed minimal seam on the existing orchestrator (L3), so both `run()` and the adaptive loop share one
provisioning:

```python
class Orchestrator:
    def run_episodes(self, locked: LockedSpec, *, scenarios: Sequence[Scenario],
                     sandbox: Sandbox | None = None) -> tuple[list[EpisodeResult], EvidenceView]: ...
    # provisions once when sandbox is None; runs exactly the supplied scenarios; returns results and the
    # trusted evidence view. run() delegates to it, so existing behavior and tests are unchanged.
```

The reward is computed by the existing `injection` detector over that `EvidenceView` (build a
`DetectionContext`; a finding whose `attack_case_id` equals the arm's materialized id means success).
`verifi.adaptive` never reads transcripts and never marks new evidence trusted.

---

## Part C — refined MVP tasks for #71

Suggested decomposition for the planner/triager to fold into #71 (size `m`). No new dependencies; each
unit has a negative/false-positive test where the behavior is security-relevant.

1. **`src/verifi/adaptive/models.py`** — `Arm`, `Attempt`, `SearchTree`, `AdaptiveResult`; deterministic
   ids via `sha256_json`; tree persistence JSON via `verifi.util.jsonio.canonical_json`.
   Tests: `tests/unit/adaptive/test_models.py::test_tree_is_deterministic_and_prefix_observable`.
2. **`src/verifi/adaptive/policy.py`** — `AdaptivePolicy` protocol + `BanditPolicy` (UCB1, seeded,
   batched `select`).
   Tests: `tests/unit/adaptive/test_policy.py::test_ucb1_tries_every_arm_before_exploiting`,
   `::test_seeded_policy_is_deterministic`.
3. **`src/verifi/runs/orchestrator.py`** — add the `run_episodes` seam and make `run()` delegate to it
   (no behavior change).
   Tests: `tests/unit/runs/test_orchestrator_episodes.py` (existing `run` tests stay green).
4. **`src/verifi/adaptive/loop.py`** — `AdaptiveLoop.search`: materialize arms from packs + mutators, run
   episodes through the seam, score with the `injection` detector over trusted evidence, stop on first
   success or budget, record the tree, export successes via the #69 store.
   Tests: `tests/unit/adaptive/test_loop.py::test_reward_uses_trusted_evidence_only` (a transcript-only
   "success" is ignored), `::test_stops_on_first_success`.
5. **Operation + CLI** — register `adaptive.search` with `--json`; add the CLI parity test.
   Blocked on the human adding the `cli-contract.md` row.
6. **`tests/e2e/test_adaptive.py::test_finds_case_missed_by_static_pack`** (the issue's named test) —
   fixture: a `ScriptedTarget` that refuses the base case but complies with one mutation (e.g. a
   base64/split-payload variant). Assert the adaptive run discovers the mutated success, exports it to the
   regression store, and is byte-identical on a second run with the same seed (INV-7).

**Out of scope for #71 (Phase 3b):** LLM/evolutionary proposers and offline policy improvement over the
recorded tree.
