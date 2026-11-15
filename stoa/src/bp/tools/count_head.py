"""Count head: one image encoder with one classification head per count family, for raster floor plans.

The model reads the whole plan once and gives, for each family (doors, windows, toilets ...), a probability for
each count 0..cap. The last class of a family is an overflow bucket ("cap or more"). A count is trusted only when
its probability is over a threshold that was tuned on held-out DEV plans, and when the plan looks like the plans
that the model was trained on: a Mahalanobis distance on the pooled embedding, and a style gate (a logistic
regression on the same embedding, CubiCasa plans against raster drawings of other sources).

This module has no `bp` imports on purpose: the GPU job copies it as it is (`jobs/cubicasa-count/prepare.py`), so
training and inference share one preprocessing and one network definition.
"""

from __future__ import annotations

import re
import time
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import torch
from PIL import Image
from pydantic import BaseModel, ConfigDict
from torch import nn

if TYPE_CHECKING:
    from numpy.typing import NDArray

# The longest side that prepare stores. Inference caps at the same size first, so both see the same pixels.
STORE_SIDE = 1280
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")

# Stoa family code -> our name. The code is the suffix of `item.family` (`F:cubicasa5k/T010`).
FAMILY_CODES: dict[str, str] = {
    "T000": "floors",
    "T001": "windows",
    "T004": "toilets",
    "T006": "sinks",
    "T008": "showers_tubs",
    "T010": "doors",
    "T012": "saunas",
    "T014": "kitchens",
    "T016": "bedrooms",
    "T018": "bathrooms",
    "T020": "wc_rooms",
    "T022": "balconies",
}
FAMILIES: tuple[str, ...] = tuple(FAMILY_CODES.values())

DEFAULT_ARTIFACT = Path(__file__).resolve().parents[3] / "artifacts" / "cubicasa-count"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ----------------------------------------------------------------------------- question -> family

_COUNT_WORDS = re.compile(r"\b(how many|number of|count|kuinka monta|montako|lukumäärä|laske)\b", re.IGNORECASE)
# Questions about a printed label, an area or a length are not counts of drawn things.
_REFUSE = re.compile(
    r"labell?ed|nimetty|merkitty nimellä|['\"\u2018\u201c][^'\"\u2019\u201d]{1,120}['\"\u2019\u201d]|\barea\b|\bm2\b|m²|pinta-ala|\blength\b|pituus"
    r"|per floor|kerroksittain|\bsheet\b|schedule|\bin the model\b",
    re.IGNORECASE,
)
# First match wins. The order settles the overlaps: the sink question names the kitchen, the bathroom question
# names WC rooms, and the WC room question names toilets.
_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "showers_tubs",
        (re.compile(r"shower.*\b(bath)?tubs?\b|\b(bath)?tubs?\b.*shower|suihku.*amme|amme.*suihku", re.IGNORECASE),),
    ),
    # The CubiCasa sink count includes kitchen sinks, so a question about wash basins alone is not this family.
    ("sinks", (re.compile(r"\bsinks?\b|tiskiallas|tiskialta", re.IGNORECASE),)),
    ("bathrooms", (re.compile(r"bathrooms?|washrooms?|kylpyhuone|pesuhuone|kylpy- tai pesuhuone", re.IGNORECASE),)),
    ("wc_rooms", (re.compile(r"\bwc rooms?\b|toilet rooms?|wc-til|wc-huone", re.IGNORECASE),)),
    ("toilets", (re.compile(r"toilet|\bwc seats?\b|wc-istuin|istuin", re.IGNORECASE),)),
    ("doors", (re.compile(r"\bdoors?\b|\bov(i|ea|et|ia|ien)\b", re.IGNORECASE),)),
    ("windows", (re.compile(r"\bwindows?\b|ikkun", re.IGNORECASE),)),
    ("floors", (re.compile(r"\bfloors\b|\bstore(y|ys)\b|\bstories\b|\blevels\b|kerros", re.IGNORECASE),)),
    ("saunas", (re.compile(r"sauna", re.IGNORECASE),)),
    ("kitchens", (re.compile(r"kitchen|keittiö|keittokomero", re.IGNORECASE),)),
    ("bedrooms", (re.compile(r"bedrooms?|makuuhuone", re.IGNORECASE),)),
    ("balconies", (re.compile(r"balcon|parvek", re.IGNORECASE),)),
)


def family_of(question: str) -> str | None:
    """Map a count question (English or Finnish) to a family, or None when no rule fits."""
    if not _COUNT_WORDS.search(question) or _REFUSE.search(question):
        return None
    for name, patterns in _RULES:
        if any(p.search(question) for p in patterns):
            return name
    return None


# ----------------------------------------------------------------------------- images


def is_raster(path: Path) -> bool:
    return path.suffix.lower() in RASTER_SUFFIXES


def load_image(path: Path) -> Image.Image:
    """RGB on white, longest side at most STORE_SIDE. Prepare and inference both use this."""
    with Image.open(path) as raw:
        raw.load()
        image = raw
        if image.mode in {"RGBA", "LA", "P"}:
            rgba = image.convert("RGBA")
            canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(canvas, rgba)
        image = image.convert("RGB")
    longest = max(image.size)
    if longest > STORE_SIDE:
        scale = STORE_SIDE / longest
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


def letterbox(
    image: Image.Image, side: int, scale: float = 1.0, offset: tuple[float, float] = (0.5, 0.5)
) -> NDArray[np.float32]:
    """Fit the image in a white side x side square. `scale` < 1 shrinks it, `offset` places it (0..1 per axis).

    Returns a CHW float array, normalised.
    """
    fit = side * scale / max(image.size)
    size = (max(1, round(image.width * fit)), max(1, round(image.height * fit)))
    resized = image.resize(size, Image.Resampling.BILINEAR if fit > 1 else Image.Resampling.BOX)
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    left = round((side - size[0]) * offset[0])
    top = round((side - size[1]) * offset[1])
    canvas.paste(resized, (left, top))
    array = np.asarray(canvas, dtype=np.float32) / 255.0
    array = (array - np.asarray(MEAN, dtype=np.float32)) / np.asarray(STD, dtype=np.float32)
    return np.ascontiguousarray(array.transpose(2, 0, 1))


def dihedral(x: torch.Tensor, k: int) -> torch.Tensor:
    """One of the 8 flips and quarter turns of a (..., H, W) tensor. Counts do not change under them."""
    if k >= 4:
        x = torch.flip(x, dims=(-1,))
    return torch.rot90(x, k % 4, dims=(-2, -1))


# ----------------------------------------------------------------------------- network


class CountNet(nn.Module):
    """A timm encoder, then one small classifier per family over counts 0..cap."""

    def __init__(self, backbone: str, caps: dict[str, int], *, side: int, pretrained: bool = False) -> None:
        super().__init__()
        import timm  # noqa: PLC0415 - heavy import, only when a model is built

        if backbone.startswith("vit"):
            encoder = timm.create_model(
                backbone, pretrained=pretrained, num_classes=0, img_size=side, dynamic_img_size=True
            )
        else:
            encoder = timm.create_model(backbone, pretrained=pretrained, num_classes=0)
        self.encoder: nn.Module = encoder
        dim = int(getattr(self.encoder, "num_features", 0))
        self.families = tuple(caps)
        self.heads = nn.ModuleDict(
            {f: nn.Sequential(nn.LayerNorm(dim), nn.Dropout(0.1), nn.Linear(dim, caps[f] + 1)) for f in caps}
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        embedding = self.encoder(x)
        return embedding, {f: head(embedding) for f, head in self.heads.items()}


# ----------------------------------------------------------------------------- loaded model and results


class Calib(_Frozen):
    """What calibration fitted on held-out DEV plans, for one family."""

    temperature: float = 1.0
    threshold: float = 0.5
    hold_n: int = 0
    hold_accuracy: float = 0.0
    hold_score: float = 0.0  # mean +1/0/-1 per plan at the threshold


class ModelMeta(_Frozen):
    """One trained member: how to build it and how far its training plans spread in embedding space."""

    name: str
    backbone: str
    side: int
    caps: dict[str, int]
    ood_threshold: float  # Mahalanobis distance at the 99.5th percentile of held-out DEV plans


class EnsembleSpec(_Frozen):
    """What the solver loads: members (paths relative to this file), views, and the fitted calibration."""

    name: str
    members: tuple[str, ...]
    tta: int = 1  # how many dihedral views each member averages
    ood_scale: float = 1.0  # a plan is out of distribution when distance / member threshold is over this
    calib: dict[str, Calib]


class FamilyCount(_Frozen):
    family: str
    value: int
    probability: float  # after temperature scaling and averaging over views and models
    threshold: float
    overflow: bool  # the top class is the "cap or more" bucket
    top: tuple[tuple[int, float], ...]  # the three most probable counts

    @property
    def trusted(self) -> bool:
        return not self.overflow and self.probability >= self.threshold


class CountEvidence(_Frozen):
    page: int = 0
    width: int
    height: int
    box: tuple[tuple[float, float], tuple[float, float]]  # the region the model read, in source pixels


class PlanCounts(_Frozen):
    """Every family count for one raster plan, with how sure the model is and why."""

    models: tuple[str, ...]
    in_distribution: bool
    ood_distance: float
    ood_threshold: float
    style_margin: float | None  # the style gate: over 0 is a CubiCasa-style plan; None when no gate is fitted
    counts: dict[str, FamilyCount]
    evidence: CountEvidence
    method: Literal["model"] = "model"
    latency_ms: float


class _Member:
    def __init__(self, folder: Path, device: torch.device) -> None:
        self.meta = ModelMeta.model_validate_json((folder / "meta.json").read_text())
        net = CountNet(self.meta.backbone, self.meta.caps, side=self.meta.side)
        state = torch.load(folder / "model.pt", map_location="cpu", weights_only=True)
        net.load_state_dict({k: v.float() for k, v in state.items()})
        self.net = net.to(device).eval()
        stats = np.load(folder / "ood.npz")
        self.ood_mean = torch.from_numpy(stats["mean"].astype(np.float32)).to(device)
        self.ood_precision = torch.from_numpy(stats["precision"].astype(np.float32)).to(device)
        self.gate: dict[str, torch.Tensor] | None = None
        if (folder / "gate.npz").exists():
            gate = np.load(folder / "gate.npz")
            self.gate = {k: torch.from_numpy(np.asarray(gate[k], dtype=np.float32)).to(device) for k in gate.files}

    def style_margin(self, embedding: torch.Tensor) -> float:
        """Gate score minus its threshold: over 0 means a CubiCasa-style plan. No gate gives +inf."""
        if self.gate is None:
            return float("inf")
        g = self.gate
        value = (((embedding - g["mean"]) / g["scale"]) @ g["w"] + g["b"] - g["threshold"]).item()
        return float(value)


class CountModel:
    """One or more trained members. Logits average over dihedral views and members, then a fitted temperature."""

    def __init__(self, spec_path: Path, device: torch.device) -> None:
        self.spec = EnsembleSpec.model_validate_json(spec_path.read_text())
        self.device = device
        self.members = [_Member(spec_path.parent / m, device) for m in self.spec.members]
        self.caps = dict(self.members[0].meta.caps)
        if any(m.meta.caps != self.caps for m in self.members):
            msg = "ensemble members must share their caps"
            raise ValueError(msg)

    @torch.inference_mode()
    def probabilities(self, image: Image.Image) -> tuple[dict[str, NDArray[np.float64]], float, float]:
        """Per family, the distribution over counts, the largest OOD ratio and the smallest style margin."""
        sums: dict[str, torch.Tensor] = {}
        ood_ratio = 0.0
        style = float("inf")
        for member in self.members:
            x = torch.from_numpy(letterbox(image, member.meta.side)).unsqueeze(0).to(self.device)
            views = torch.cat([dihedral(x, k) for k in range(self.spec.tta)])
            embedding, logits = member.net(views)
            centred = embedding[:1].float() - member.ood_mean  # view 0, as in training
            distance = torch.sqrt(torch.einsum("bi,ij,bj->b", centred, member.ood_precision, centred)).item()
            ood_ratio = max(ood_ratio, distance / member.meta.ood_threshold)
            style = min(style, member.style_margin(embedding[0].float()))
            for family, value in logits.items():
                mean = value.float().mean(dim=0)
                sums[family] = sums[family] + mean if family in sums else mean
        out: dict[str, NDArray[np.float64]] = {}
        for family, total in sums.items():
            temperature = self.spec.calib[family].temperature if family in self.spec.calib else 1.0
            p = torch.softmax(total / len(self.members) / temperature, dim=-1)
            out[family] = p.cpu().numpy().astype(np.float64)
        return out, ood_ratio, style


def pick_device() -> torch.device:
    """The fastest device this machine has: CUDA, then Apple MPS, then the CPU."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@cache
def get_model(spec: str = "e1.json") -> CountModel:
    """Load once per process. The sandboxed worker serves many documents, so this saves the load time."""
    return CountModel(DEFAULT_ARTIFACT / spec, pick_device())


def count_plan(path: Path, model: CountModel | None = None) -> PlanCounts:
    """Read one raster plan and give a count with its probability for every family."""
    started = time.perf_counter()
    model = model or get_model()
    image = load_image(path)
    with Image.open(path) as raw:
        width, height = raw.size
    distributions, ood_ratio, style = model.probabilities(image)
    counts: dict[str, FamilyCount] = {}
    for family, p in distributions.items():
        order = np.argsort(-p)
        value = int(order[0])
        calib = model.spec.calib.get(family, Calib(threshold=1.01))
        counts[family] = FamilyCount(
            family=family,
            value=value,
            probability=float(p[value]),
            threshold=calib.threshold,
            overflow=value >= model.caps[family],
            top=tuple((int(i), round(float(p[i]), 4)) for i in order[:3]),
        )
    evidence = CountEvidence(width=width, height=height, box=((0.0, 0.0), (float(width), float(height))))
    return PlanCounts(
        models=tuple(m.meta.name for m in model.members),
        in_distribution=ood_ratio <= model.spec.ood_scale and style >= 0.0,
        ood_distance=round(ood_ratio, 4),
        ood_threshold=model.spec.ood_scale,
        style_margin=round(style, 4) if style != float("inf") else None,
        counts=counts,
        evidence=evidence,
        latency_ms=(time.perf_counter() - started) * 1000.0,
    )
