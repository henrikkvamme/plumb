"""The contract between the harness, the solvers and the tools.

Every type here is frozen. A solver sees a `Question` and returns an `AnswerRecord`.
A solver never sees an `Item`: the item holds the key.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Kind(StrEnum):
    COUNT = "count"
    MEASURE = "measure"
    LOOKUP = "lookup"
    TEXT = "text"
    UNANSWERABLE = "unanswerable"


class Dimension(StrEnum):
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    RATIO = "ratio"


class MissingReason(StrEnum):
    """Why a question has no answer on this document."""

    NO_SCALE = "no_scale"
    NOT_ON_DOCUMENT = "not_on_document"
    NOT_A_DRAWING = "not_a_drawing"
    AMBIGUOUS = "ambiguous"
    UNREADABLE = "unreadable"
    NOT_IN_MODEL = "not_in_model"
    UNSUPPORTED = "unsupported"


# ----------------------------------------------------------------------------- keys


class CountKey(Frozen):
    kind: Literal["count"] = "count"
    value: int
    # Other counts that a careful person could defend (a second convention). Scored in a separate column.
    alternates: tuple[int, ...] = ()
    # For a count whose key is a measurement itself, such as the door swings of a sheet: right within
    # max(1, tolerance * value). 0 is an exact count.
    tolerance: float = Field(default=0.0, ge=0.0, le=0.2)


class MeasureKey(Frozen):
    kind: Literal["measure"] = "measure"
    value: float
    unit: str
    tolerance: float = 0.02
    decimals: int = 2  # the places that the key was rounded to
    alternates: tuple[float, ...] = ()


class LookupKey(Frozen):
    """A short string or code that is printed on the document."""

    kind: Literal["lookup"] = "lookup"
    accepted: tuple[str, ...]


class TextKey(Frozen):
    """A free-text reference. `facts` are the numbers, codes and names that a correct answer must hold."""

    kind: Literal["text"] = "text"
    reference: str
    facts: tuple[str, ...]


class UnanswerableKey(Frozen):
    kind: Literal["unanswerable"] = "unanswerable"
    reasons: tuple[MissingReason, ...]
    # The value that becomes correct after the user supplies what is missing (for the calibrate step).
    after_calibration: MeasureKey | None = None


Key = Annotated[CountKey | MeasureKey | LookupKey | TextKey | UnanswerableKey, Field(discriminator="kind")]


# ----------------------------------------------------------------------------- items


class Question(Frozen):
    """What a solver receives. No key, no source name, no original file name."""

    qid: str
    text: str


class Calibration(Frozen):
    """What a user gives after an abstention: a scale ratio, or two points with their real distance."""

    scale_ratio: float | None = None  # 100.0 means 1:100
    points: tuple[tuple[float, float], tuple[float, float]] | None = None
    real_length_m: float | None = None


class Item(Frozen):
    """One scored question. `twins` are translations of the same question: the item is right when all are."""

    item_id: str
    doc: str  # path relative to the dataset root; the harness hides it from the solver
    question: str
    twins: tuple[str, ...] = ()
    key: Key
    source: str
    family: str
    group: str  # the cluster for statistics and splits (plan id, site, IFC project)
    cell: str  # skill x kind of input, see EVALUATION.md
    suite: str
    condition: str = "native"
    partition: Literal["dev", "val", "lock"] = "dev"
    origin: Literal["stoa", "derived", "hand", "synthetic"] = "stoa"
    # What the harness gives the solver after a correct abstention, to test that the answer then arrives.
    calibration: Calibration | None = None


# ----------------------------------------------------------------------------- answers


class Evidence(Frozen):
    """Where an answer comes from. Coordinates are in the pixel or point space of the page that was read."""

    kind: Literal["mark", "polygon", "text_span", "table_cell", "ifc_element", "scale", "calc"]
    page: int = 0
    points: tuple[tuple[float, float], ...] = ()
    ref: str = ""  # GlobalId, cell address, the text that was read
    note: str = ""


class Check(Frozen):
    """One reason for a confidence: what was tested, how it went, and the factor it puts on the confidence."""

    id: str  # "scale", "closed", "error_band", "cross_check", "provenance"
    label: str
    state: Literal["pass", "warn", "fail"]
    detail: str = ""
    factor: float = Field(default=1.0, ge=0.0, le=1.0)


def confidence_of(checks: tuple[Check, ...]) -> float:
    """The product of the factors: each weak point lowers the confidence, and no check alone hides another."""
    value = 1.0
    for check in checks:
        value *= check.factor
    return round(value, 3)


class Conflict(Frozen):
    """Facts of one document that do not add up, such as a measured area against the printed area of the room."""

    id: str
    entity_ids: tuple[str, ...]  # every entity that takes part
    text: str  # one plain sentence for a person
    # The entities whose values are in doubt: an answer that uses one of them is less sure. A printed value is what
    # the drawing states, so it is not in doubt; the measurement that disagrees with it is.
    doubtful: tuple[str, ...] = ()
    # A measured length or area of any entity depends on it (a scale conflict).
    all_measured: bool = False


class Step(Frozen):
    """One tool call of an answer. A reader can check the answer from the steps alone."""

    tool: str
    method: Literal["deterministic", "model"]
    summary: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    result: str = ""  # what the tool returned, as JSON text, cut to RESULT_CHARS
    evidence: tuple[Evidence, ...] = ()
    error: str = ""
    confidence: float | None = None  # of this result, from its evidence; None when the tool gives none
    checks: tuple[Check, ...] = ()  # the reasons for the confidence
    latency_ms: float = 0.0


class Abstain(Frozen):
    reason: MissingReason
    detail: str
    request: str  # what the user can give so that an answer becomes possible


class AnswerRecord(Frozen):
    status: Literal["answered", "abstained", "error"]
    value: float | int | str | None = None
    unit: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    model_confidence: float | None = None  # the claim of the model, before the tool checks lower it
    convention: str = ""
    abstain: Abstain | None = None
    best_estimate: float | int | str | None = None
    evidence: tuple[Evidence, ...] = ()
    steps: tuple[Step, ...] = ()
    checks: tuple[Check, ...] = ()  # the reasons for the confidence, from the steps that the answer used
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    detail: str = ""  # the error text, or a note for a person who reads the run
    # Error margin of a measured answer: plus or minus `margin` in `unit`. `margin_share` of the test items of the
    # tool benchmark were inside it. None: no measured value, or no benchmark for it.
    margin: float | None = Field(default=None, ge=0.0)
    margin_share: float | None = Field(default=None, ge=0.0, le=1.0)
    margin_basis: str = ""
    entity_ids: tuple[str, ...] = ()  # the document facts that the answer used (`DocumentFacts.entities` ids)


class IngestReport(Frozen):
    ok: bool
    detail: str = ""
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)


class Solver(Protocol):
    """One solver instance serves one document. The harness creates a new instance for each session."""

    name: str

    def ingest(self, path: str) -> IngestReport: ...

    def ask(self, question: Question) -> AnswerRecord: ...

    def calibrate(self, calibration: Calibration) -> None: ...
