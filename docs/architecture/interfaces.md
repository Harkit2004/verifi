# Interfaces (binding contracts)

Names, module paths, and signatures below are **binding**. Implement them exactly. Fields may be *added*
by an issue; renaming or removing requires an ADR. All models are Pydantic v2 `BaseModel` with
`model_config = ConfigDict(frozen=True, extra="forbid")` unless stated otherwise. Timestamps are
timezone-aware UTC `datetime`. All JSON serialization of hashed content uses `verifi.util.jsonio.canonical_json`.

---

## L0: `verifi.errors`

```python
class VerifiError(Exception):
    code: str            # stable machine code, UPPER_SNAKE
    exit_code: int       # see cli-contract.md
    def __init__(self, message: str, *, code: str | None = None, hint: str | None = None,
                 details: dict[str, object] | None = None) -> None: ...
    message: str; hint: str | None; details: dict[str, object]

class InvalidInputError(VerifiError):       exit_code = 2; code = "INVALID_INPUT"
class SpecInvalidError(InvalidInputError):  code = "SPEC_INVALID"      # details["errors"]: list[{"path": "/policy/controls/0", "message": str}]
class NotFoundError(InvalidInputError):     code = "NOT_FOUND"          # e.g. RUN_NOT_FOUND, SPEC_NOT_FOUND via code=
class VerifiEnvironmentError(VerifiError):  exit_code = 3; code = "ENVIRONMENT"   # DOCKER_UNAVAILABLE, SANDBOX_CREATE_FAILED
class BudgetExceededError(VerifiError):     exit_code = 4; code = "BUDGET_EXCEEDED"  # raised inside episodes, caught by orchestrator
class IntegrityError(VerifiError):          exit_code = 1; code = "INTEGRITY_FAILED"
class InternalError(VerifiError):           exit_code = 4; code = "INTERNAL"
```

## L0: `verifi.util`

```python
# clock.py
class Clock(Protocol):
    def now(self) -> datetime: ...
class SystemClock: ...                                   # now() -> datetime.now(UTC)
class FixedClock:                                        # tests
    def __init__(self, start: datetime, step: timedelta = timedelta(seconds=1)) -> None: ...
    def now(self) -> datetime: ...                       # returns start, start+step, ...

# ids.py
class IdGenerator(Protocol):
    def new(self, prefix: str) -> str: ...               # e.g. "run_...", "ep_...", "fnd_..."
class RandomIds:                                         # f"{prefix}_{utc:%Y%m%dT%H%M%SZ}_{8 hex chars from secrets}"
    def __init__(self, clock: Clock) -> None: ...
class SequentialIds:                                     # tests: f"{prefix}_{n:04d}", per-prefix counter starting at 1
    def __init__(self) -> None: ...

# jsonio.py
def canonical_json(value: object) -> bytes: ...          # sort_keys, separators=(",", ":"), ensure_ascii=False, UTF-8; pydantic models via model_dump(mode="json")
# hashing.py
def sha256_hex(data: bytes) -> str: ...
def sha256_json(value: object) -> str: ...               # sha256_hex(canonical_json(value))
```

## L4: `verifi.app`

```python
# envelope.py
class ErrorInfo(BaseModel):
    code: str; message: str; hint: str | None = None; path: str | None = None; details: dict[str, object] = {}

class EnvelopeMeta(BaseModel):
    verifi_version: str; duration_ms: int; run_id: str | None = None

class Envelope(BaseModel):
    schema_: Literal["verifi.envelope/v1"] = Field("verifi.envelope/v1", alias="schema")
    ok: bool
    command: str                       # operation name, e.g. "spec.validate"
    data: dict[str, object] | None
    errors: list[ErrorInfo] = []
    warnings: list[ErrorInfo] = []
    meta: EnvelopeMeta

# context.py
@dataclass(frozen=True)
class AppContext:
    home: Path                         # VERIFI_HOME
    clock: Clock
    ids: IdGenerator
    env: Mapping[str, str]             # the only allowed source of environment values
    @classmethod
    def default(cls, home: Path | None = None) -> "AppContext": ...

# registry.py
I = TypeVar("I", bound=BaseModel); O = TypeVar("O", bound=BaseModel)

@dataclass(frozen=True)
class OperationSpec(Generic[I, O]):
    name: str                          # "<group>.<verb>" (lowercase, dot-separated, 2 or 3 segments)
    summary: str
    input: type[I]
    output: type[O]
    func: Callable[[AppContext, I], O]
    exit_code: Callable[[O], int] | None = None   # e.g. runs.start returns 1 when gate failed
    cli_aliases: tuple[str, ...] = ()             # e.g. ("run",) for runs.start

def operation(*, name: str, summary: str, input: type[I], output: type[O],
              exit_code: Callable[[O], int] | None = None,
              cli_aliases: tuple[str, ...] = ()) -> Callable[[Callable[[AppContext, I], O]], Callable[[AppContext, I], O]]: ...
def registry() -> Mapping[str, OperationSpec[Any, Any]]: ...     # imports verifi.app.operations first
def invoke(ctx: AppContext, name: str, raw_input: Mapping[str, object]) -> Envelope: ...  # validation errors -> INVALID_INPUT; VerifiError -> errors; other exceptions -> INTERNAL
```

`verifi.app.operations` only imports the `operations.py` modules of each package so their decorators run.

---

## L1: `verifi.spec`

```python
class ControlId(StrEnum):
    NO_SECRET_ACCESS = "no_secret_access"
    NO_DATA_EXFILTRATION = "no_data_exfiltration"
    NO_UNAUTHORIZED_TOOL_USE = "no_unauthorized_tool_use"
    NO_PRIVILEGE_ESCALATION = "no_privilege_escalation"
    NO_SANDBOX_ESCAPE = "no_sandbox_escape"
    NO_PROMPT_INJECTION_COMPLIANCE = "no_prompt_injection_compliance"
    NO_DESTRUCTIVE_ACTIONS = "no_destructive_actions"

class Severity(StrEnum):
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"; CRITICAL = "critical"

class ControlDefinition(BaseModel):        # controls.py catalog entry
    id: ControlId; title: str; description: str; default_severity: Severity
    evidence_kinds: tuple["EvidenceKind", ...]   # evidence the control's detectors consume
def control_catalog() -> Mapping[ControlId, ControlDefinition]: ...

# models.py (full field list: spec-v1.md)
class VerificationSpec(BaseModel): api_version: Literal["verifi.dev/v1"] (alias "apiVersion"); kind: Literal["VerificationSpec"]; metadata: Metadata; target: TargetSpec; environment: EnvironmentSpec; tools: list[ToolGrant]; policy: PolicySpec; attacks: AttacksSpec; budget: BudgetSpec; gate: GateSpec
class LockedSpec(BaseModel):
    spec: VerificationSpec            # env refs NOT resolved (secrets never locked)
    sha256: str                       # sha256_json(spec.model_dump(mode="json", by_alias=True))
    verifi_version: str

# loader.py
def load_spec(path: Path) -> VerificationSpec: ...                 # raises SpecInvalidError / NotFoundError(code="SPEC_NOT_FOUND")
def parse_spec(text: str, *, source: str = "<string>") -> VerificationSpec: ...
# envrefs.py
def resolve_env_refs(value: str, env: Mapping[str, str]) -> str: ...  # "${env:NAME}" -> env[NAME]; missing -> InvalidInputError(code="ENV_REF_MISSING")
# lock.py
def lock_spec(spec: VerificationSpec) -> LockedSpec: ...
# schema.py
def spec_json_schema() -> dict[str, object]: ...                   # committed at schemas/verification-spec.v1.json
```

## L1: `verifi.evidence.models`

```python
class EvidenceKind(StrEnum):
    TOOL_CALL = "tool_call"                 # broker audit (trusted)
    NETWORK_EVENT = "network_event"         # sinkhole capture (trusted)
    FS_SNAPSHOT = "fs_snapshot"             # host-side snapshot (trusted)
    WORLD_DIFF = "world_diff"               # host-side world diff (trusted)
    EXEC_RESULT = "exec_result"             # sandbox exec observed by host (trusted)
    CANARY_REGISTRY = "canary_registry"     # planted honeytokens (trusted)
    SANDBOX_INSPECTION = "sandbox_inspection"  # effective isolation settings (trusted)
    ESCAPE_PROBE = "escape_probe"           # host-side escape sentinel observations (trusted)
    TARGET_TRANSCRIPT = "target_transcript" # what the target said (UNTRUSTED)

class EvidenceSource(StrEnum):
    BROKER = "broker"; SANDBOX_HOST = "sandbox_host"; SINKHOLE = "sinkhole"; ORCHESTRATOR = "orchestrator"; TARGET = "target"

TRUSTED_SOURCES: frozenset[EvidenceSource] = frozenset({BROKER, SANDBOX_HOST, SINKHOLE, ORCHESTRATOR})

class EvidenceRecord(BaseModel):
    id: str                  # "ev_" + sha256_json(content fields excluding id)[:32]
    run_id: str
    episode_id: str | None
    kind: EvidenceKind
    source: EvidenceSource
    trusted: bool            # MUST equal (source in TRUSTED_SOURCES and kind != TARGET_TRANSCRIPT); validator enforces
    created_at: datetime
    payload: dict[str, object]
def make_evidence(*, run_id: str, episode_id: str | None, kind: EvidenceKind, source: EvidenceSource,
                  created_at: datetime, payload: dict[str, object]) -> EvidenceRecord: ...   # computes id and trusted
```

## L2: `verifi.evidence.store`

```python
class EvidenceStore:
    def __init__(self, run_dir: Path) -> None: ...        # objects under run_dir/evidence/objects/<id>.json, index run_dir/evidence/index.jsonl
    def put(self, record: EvidenceRecord) -> str: ...     # idempotent; returns id
    def get(self, evidence_id: str) -> EvidenceRecord: ...
    def iter(self, *, kind: EvidenceKind | None = None, episode_id: str | None = None) -> Iterator[EvidenceRecord]: ...
    def trusted_view(self) -> "EvidenceView": ...

class EvidenceView:                                       # read-only; yields ONLY trusted records
    def records(self, *, kind: EvidenceKind | None = None, episode_id: str | None = None) -> Iterator[EvidenceRecord]: ...
    def get(self, evidence_id: str) -> EvidenceRecord: ...   # raises IntegrityError(code="UNTRUSTED_EVIDENCE") for untrusted ids
```

## L1/L2: `verifi.runs`

```python
class RunStatus(StrEnum):
    CREATED = "created"; PROVISIONING = "provisioning"; RUNNING = "running"; VERIFYING = "verifying"
    COMPLETED = "completed"; FAILED = "failed"; CANCELLED = "cancelled"

class RunManifest(BaseModel):          # frozen=False (status changes); persisted as manifest.json
    run_id: str; created_at: datetime; verifi_version: str; spec_sha256: str; seed: int
    status: RunStatus; sandbox_provider: str; target_type: str
    host: dict[str, str]               # os, python, platform only (no env, no user names)
    finished_at: datetime | None = None; error: ErrorInfo | None = None

class Event(BaseModel):
    seq: int; ts: datetime; type: str; data: dict[str, object]; prev_hash: str; hash: str
    # hash = sha256_json({"seq","ts","type","data","prev_hash"}); first prev_hash = "0"*64

class EventLog:                         # events.py
    def __init__(self, path: Path, clock: Clock) -> None: ...
    def append(self, type: str, data: dict[str, object]) -> Event: ...
    def verify(self) -> None: ...        # raises IntegrityError(code="EVENT_CHAIN_BROKEN", details={"seq": n})

class RunStore:                          # store.py
    def __init__(self, home: Path) -> None: ...                     # runs under home/"runs"
    def create(self, manifest: RunManifest, locked: LockedSpec) -> Path: ...   # writes manifest.json + spec.lock.json
    def run_dir(self, run_id: str) -> Path: ...                     # NotFoundError(code="RUN_NOT_FOUND")
    def load_manifest(self, run_id: str) -> RunManifest: ...
    def update_status(self, run_id: str, status: RunStatus, *, error: ErrorInfo | None = None) -> RunManifest: ...  # illegal transition -> InternalError(code="ILLEGAL_TRANSITION")
    def list(self) -> list[RunManifest]: ...                        # newest first

class BudgetMeter:                       # budget.py
    def __init__(self, *, max_steps: int, max_tokens: int, deadline: datetime, clock: Clock) -> None: ...
    def charge(self, *, steps: int = 0, tokens: int = 0) -> None: ...   # raises BudgetExceededError(code="STEPS"|"TOKENS"|"TIME")
    @property
    def remaining(self) -> dict[str, int]: ...

class EpisodeResult(BaseModel):
    episode_id: str; scenario_id: str; attack_case_ids: list[str]
    status: Literal["completed", "budget_exceeded", "target_error", "sandbox_error"]
    steps: int; tokens: int; started_at: datetime; finished_at: datetime

class RunResult(BaseModel):
    run_id: str; status: RunStatus; score: "Score | None"; gate: "GateResult | None"
    findings_count: dict[Severity, int]; verification_id: str | None; run_dir: str

class Orchestrator:                      # orchestrator.py
    def __init__(self, ctx: AppContext, *, sandbox_provider: "SandboxProvider", target_factory: "TargetFactory",
                 detectors: Sequence["Detector"], store: RunStore) -> None: ...
    def run(self, locked: LockedSpec, *, seed: int) -> RunResult: ...  # never leaves a sandbox alive (teardown in finally)
```

## L2: `verifi.sandbox`

```python
class NetworkMode(StrEnum):  NONE = "none"; SINKHOLE = "sinkhole"
class IsolationTier(StrEnum): FAKE = "fake"; DOCKER = "docker"; VM = "vm"

class SandboxRequest(BaseModel):
    run_id: str; image: str = "verifi/sandbox-base:1"; network: NetworkMode = NetworkMode.NONE
    cpus: float = 1.0; memory_mb: int = 1024; pids: int = 256; workdir: str = "/workspace"
    read_only_root: bool = True; env: dict[str, str] = {}          # env is an explicit allowlist, never host env
    relaxations: list[str] = []                                     # e.g. ["network:sinkhole"]; each surfaces as SECURITY_RELAXED

class ExecResult(BaseModel):
    argv: list[str]; exit_code: int; stdout: str; stderr: str; duration_ms: int; timed_out: bool

class NetworkEvent(BaseModel):
    ts: datetime; protocol: Literal["dns", "http", "tls", "tcp", "udp"]; dst_host: str | None; dst_ip: str | None
    dst_port: int | None; method: str | None = None; path: str | None = None; body_sample: str | None = None  # first 64 KiB

class FsEntry(BaseModel): path: str; sha256: str | None; size: int; mode: int      # sha256 None for dirs
class FsSnapshot(BaseModel): label: str; taken_at: datetime; entries: dict[str, FsEntry]
class FsDiff(BaseModel): added: list[str]; removed: list[str]; modified: list[str]
def diff_snapshots(before: FsSnapshot, after: FsSnapshot) -> FsDiff: ...

class SandboxInspection(BaseModel):     # EFFECTIVE settings read back from the runtime, not the request
    tier: IsolationTier; network: NetworkMode; read_only_root: bool; cap_drop_all: bool; no_new_privileges: bool
    user: str; pids_limit: int | None; memory_limit_mb: int | None; privileged: bool; mounts: list[str]; isolated: bool

class Sandbox(Protocol):
    id: str
    def exec(self, argv: Sequence[str], *, timeout_s: float, stdin: bytes | None = None) -> ExecResult: ...
    def put_file(self, path: str, data: bytes, *, mode: int = 0o644) -> None: ...
    def get_file(self, path: str) -> bytes: ...                  # host-side read
    def snapshot(self, label: str, *, root: str = "/workspace") -> FsSnapshot: ...   # host-side
    def network_events(self) -> list[NetworkEvent]: ...          # host-side (sinkhole); [] for NONE
    def inspect(self) -> SandboxInspection: ...
    def destroy(self) -> None: ...                               # idempotent

class SandboxProvider(Protocol):
    name: str                                                    # "fake" | "docker"
    tier: IsolationTier
    def available(self) -> bool: ...
    def create(self, request: SandboxRequest) -> Sandbox: ...    # VerifiEnvironmentError(code="SANDBOX_CREATE_FAILED")

def get_provider(name: str) -> SandboxProvider: ...              # NotFoundError(code="PROVIDER_NOT_FOUND")
```

`FakeSandbox` (`sandbox/fake.py`): in-memory filesystem; `exec` supports a small registered command table (`echo`, `cat`, `ls`, `python -c` is NOT executed; tests register handlers via `FakeSandboxProvider(handlers={...})`); `inspect().isolated == False` and `tier == FAKE`.

## L1/L2: `verifi.world`

```python
class Honeytoken(BaseModel):
    id: str; kind: Literal["api_key", "password", "pii_email", "pii_ssn", "file_secret", "escape_sentinel"]
    value: str                        # generated with secrets, unique per run
    planted_at: str                   # locator, e.g. "fs:/workspace/.env", "db:crm.customers#12.ssn", "mail:msg_0003", "host:sentinel"
    protected: bool = True

class CanaryRegistry:
    def __init__(self, tokens: Iterable[Honeytoken] = ()) -> None: ...
    def add(self, token: Honeytoken) -> None: ...
    def tokens(self) -> list[Honeytoken]: ...
    def find_in(self, text: str) -> list[Honeytoken]: ...     # raw + base64 + hex + url-encoded forms
def generate_token(kind: Honeytoken.kind, *, rng: secrets.SystemRandom, ids: IdGenerator, planted_at: str) -> Honeytoken: ...

class WorldFixture(BaseModel):          # loaded from builtin:<name> or a directory
    name: str; files: dict[str, str]; crm_sql: str; mailbox: list["Email"]; http_routes: list["HttpRoute"]
    protected_paths: list[str]; protected_tables: list[str]
class World:                            # fixtures.py; lives on the host side
    def __init__(self, fixture: WorldFixture, canaries: CanaryRegistry, root: Path) -> None: ...
    def snapshot(self) -> dict[str, object]: ...             # deterministic state digest (files, db rows, mailbox, outbox)
    outbox: list["Email"]                                     # messages "sent" by tools
def diff_world(before: dict[str, object], after: dict[str, object]) -> dict[str, object]: ...
```

## L2: `verifi.broker`

```python
class ToolDescriptor(BaseModel): name: str; description: str; input_schema: dict[str, object]; egress: bool   # egress tools can move data out (email.send, http.request)
class ToolCall(BaseModel): call_id: str; episode_id: str; name: str; arguments: dict[str, object]
class ToolDecision(StrEnum): ALLOW = "allow"; DENY = "deny"
class ToolResult(BaseModel): call_id: str; ok: bool; content: str; error_code: str | None = None
class ToolCallRecord(BaseModel):        # payload of TOOL_CALL evidence
    call: ToolCall; decision: ToolDecision; reason: Literal["granted", "not_granted", "unknown_tool", "constraint_violation", "invalid_arguments"]
    constraint: str | None; result: ToolResult | None; ts: datetime

class Tool(Protocol):
    descriptor: ToolDescriptor
    def invoke(self, arguments: Mapping[str, object], *, world: World, sandbox: Sandbox) -> ToolResult: ...
    def check_constraints(self, arguments: Mapping[str, object], constraints: Mapping[str, object]) -> str | None: ...  # violated constraint name or None

class ToolBroker:
    def __init__(self, *, grants: Sequence[ToolGrant], tools: Mapping[str, Tool], world: World, sandbox: Sandbox,
                 evidence: EvidenceStore, run_id: str, clock: Clock, ids: IdGenerator) -> None: ...
    def list_tools(self) -> list[ToolDescriptor]: ...           # granted tools only
    def call(self, call: ToolCall) -> ToolResult: ...
    # order: validate -> decide -> WRITE audit evidence -> (if allow) invoke -> write result evidence. Never raises for target mistakes.

def builtin_tools() -> Mapping[str, Tool]: ...   # fs.read fs.write fs.list crm.query crm.update email.list email.read email.send http.request python.execute
```

## L2: `verifi.targets`

```python
class Episode(BaseModel):
    episode_id: str; scenario_id: str; instructions: str; system_prompt: str | None
    initial_messages: list[dict[str, str]]     # may carry direct-injection vehicles
    max_steps: int

class ToolClient(Protocol):
    def list_tools(self) -> list[ToolDescriptor]: ...
    def call(self, name: str, arguments: Mapping[str, object]) -> ToolResult: ...

class EpisodeOutcome(BaseModel):
    stop_reason: Literal["finished", "max_steps", "budget", "error"]; transcript: list[dict[str, object]]  # UNTRUSTED
    steps: int; tokens: int; error: str | None = None

class Target(Protocol):
    type: str
    def run_episode(self, episode: Episode, tools: ToolClient, budget: BudgetMeter) -> EpisodeOutcome: ...

TargetFactory = Callable[[TargetSpec, AppContext], Target]
def default_target_factory(spec: TargetSpec, ctx: AppContext) -> Target: ...   # NotFoundError(code="TARGET_TYPE_NOT_FOUND")

class ScriptStep(BaseModel): tool: str; arguments: dict[str, object]; say: str | None = None
class ScriptedTarget:                   # type = "scripted"; replays steps in order; used for known-good and known-bad agents
    def __init__(self, steps: Sequence[ScriptStep] | Mapping[str, Sequence[ScriptStep]]) -> None: ...  # mapping: per scenario_id
```

## L2: `verifi.detectors`

```python
class Finding(BaseModel):
    id: str                               # "fnd_" + sha256_json({control, detector, episode, evidence_ids})[:24] (deterministic)
    control_id: ControlId; severity: Severity; detector_id: str; episode_id: str | None
    title: str; evidence_ids: list[str] = Field(min_length=1); attack_case_id: str | None = None

class DetectionContext(BaseModel, arbitrary_types_allowed=True):
    run_id: str; spec: VerificationSpec; evidence: EvidenceView; canaries: CanaryRegistry
    episodes: list[EpisodeResult]; attack_cases: Mapping[str, "AttackCase"]

class Detector(Protocol):
    id: str
    controls: frozenset[ControlId]
    def detect(self, ctx: DetectionContext) -> list[Finding]: ...

def default_detectors() -> list[Detector]: ...
def run_detectors(detectors: Sequence[Detector], ctx: DetectionContext) -> list[Finding]: ...
# only controls declared in spec.policy; dedupe by Finding.id; sort by (severity desc, control_id, episode_id, id);
# a finding whose evidence ids are not all trusted -> IntegrityError(code="UNTRUSTED_EVIDENCE")
```

## L2: `verifi.scoring`

```python
class ControlResult(BaseModel):
    control_id: ControlId; severity: Severity; episodes: int; violating_episodes: int
    pass_rate: float | None; findings: int
class Score(BaseModel):
    overall: float | None; controls: list[ControlResult]; findings_by_severity: dict[Severity, int]
    episodes_completed: int; episodes_incomplete: int
def score_run(spec: VerificationSpec, episodes: Sequence[EpisodeResult], findings: Sequence[Finding]) -> Score: ...

class GateReason(BaseModel): code: Literal["NO_EPISODES", "OVERALL_BELOW_MIN", "TOO_MANY_FINDINGS", "CONTROL_BELOW_MIN", "INCOMPLETE_EPISODES"]; message: str
class GateResult(BaseModel): passed: bool; reasons: list[GateReason]
def evaluate_gate(gate: GateSpec, score: Score) -> GateResult: ...
```

Formulas: see `detectors-and-scoring.md`.

## L2: `verifi.reports`

```python
class Report(BaseModel):
    schema_: Literal["verifi.report/v1"] = Field(alias="schema"); run: RunManifest; spec_sha256: str
    score: Score; gate: GateResult; findings: list[Finding]; warnings: list[ErrorInfo]   # includes SECURITY_RELAXED, NOT_ISOLATED
    episodes: list[EpisodeResult]
def build_report(...) -> Report: ...
def render_markdown(report: Report) -> str: ...        # golden-tested
class VerificationRecord(BaseModel):
    schema_: Literal["verifi.verification/v1"] = Field(alias="schema"); verification_id: str; files: dict[str, str]  # relpath -> sha256
def write_verification(run_dir: Path) -> VerificationRecord: ...
def verify_run_dir(run_dir: Path) -> list[str]: ...    # list of problems; [] means intact
```

## L1/L2: `verifi.attacks` (Phase 2)

```python
class AttackFamily(StrEnum):
    PROMPT_INJECTION = "prompt_injection"; INDIRECT_INJECTION = "indirect_injection"; CREDENTIAL_DISCOVERY = "credential_discovery"
    DATA_EXFILTRATION = "data_exfiltration"; TOOL_ABUSE = "tool_abuse"; PRIVILEGE_ESCALATION = "privilege_escalation"
    SANDBOX_ESCAPE = "sandbox_escape"; GOAL_HIJACKING = "goal_hijacking"; PERSISTENCE = "persistence"; MULTI_TURN = "multi_turn"

class VehicleKind(StrEnum): USER_MESSAGE = "user_message"; EMAIL = "email"; FILE = "file"; WEB_PAGE = "web_page"; DB_ROW = "db_row"; TOOL_OUTPUT = "tool_output"

class SuccessPredicate(BaseModel):     # evaluated over TRUSTED evidence only; exactly one field set
    tool_called: ToolMatch | None = None          # name + args_contains (supports "{canary:<kind>}" placeholders)
    network_contacted: NetworkMatch | None = None # host glob / port
    canary_leaked: Literal["any_egress", "network", "tool_egress"] | None = None
    world_changed: WorldMatch | None = None       # path glob / table
    all_of: list["SuccessPredicate"] | None = None; any_of: list["SuccessPredicate"] | None = None

class AttackCase(BaseModel):
    id: str; family: AttackFamily; title: str; vehicle: VehicleKind; payload: str   # payload may contain {{placeholders}}
    targets: list[ControlId]; severity: Severity; success: SuccessPredicate; turns: list[str] = []
class AttackPack(BaseModel): name: str; version: str; private: bool = False; cases: list[AttackCase]

class Mutator(Protocol):
    id: str
    def mutate(self, case: AttackCase, rng: random.Random) -> AttackCase: ...     # new id = f"{case.id}~{self.id}~{n}"

class Scenario(BaseModel): id: str; task: str; attack_case_ids: list[str]; repeat_index: int
def build_scenarios(spec: VerificationSpec, packs: Sequence[AttackPack], mutators: Sequence[Mutator], seed: int) -> list[Scenario]: ...
```
