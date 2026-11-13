"""The ``free (Auto)`` model lane.

codelaboon exposes several free providers (``ourfree``, ``kilo``,
``pollinations`` and, when the user signs in, ``gemini``, ``freebuff`` and
``qoder``). Listing every one of
their models in the picker is exhausting, so the TUI defaults to a single
synthetic model named ``free (Auto)``.

Selecting it does not need a fixed model id: codelaboon ranks the free
catalogue and answers with the best available model, then fails over to the
next candidate if the provider errors or rate-limits the turn.

Ranking is deliberately simple and documented:

* **Availability** (55%): the provider must be usable (keyless or configured)
  and the catalogue it publishes must still contain the model.
* **Intelligence** (30%): a curated capability tier for coding work.
* **Speed** (15%): a curated latency tier for interactive chat.

The weights put availability first, as the user asked: a strong model that is
not reachable is worth nothing, while a fast, smart model that is answering is
worth everything.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


AUTO_PROVIDER = "free"
AUTO_MODEL = "free (Auto)"

# Weights sum to 1.0. Availability dominates because it is a hard gate in
# practice, intelligence decides quality once reachable, speed breaks ties.
W_AVAILABILITY = 0.55
W_INTELLIGENCE = 0.30
W_SPEED = 0.15


@dataclass(frozen=True)
class FreeModel:
    """One curated entry in the free catalogue."""

    provider: str
    model: str
    intelligence: float  # 0-10, coding capability
    speed: float  # 0-10, interactive latency
    label: str = ""

    @property
    def display(self) -> str:
        return self.label or self.model

    def score(self, availability: float) -> float:
        return (
            W_AVAILABILITY * availability
            + W_INTELLIGENCE * (self.intelligence / 10.0)
            + W_SPEED * (self.speed / 10.0)
        )


# The free pool, best general-purpose first. Scores are curated from the
# advertised families; availability is measured at selection time.
CATALOG: Tuple[FreeModel, ...] = (
    FreeModel("ourfree", "deepseek-v4.1-flash-free", 9.4, 9.2, "DeepSeek V4.1 Flash"),
    FreeModel("ourfree", "deepseek-v4-flash-free", 8.9, 9.0, "DeepSeek V4 Flash"),
    FreeModel("ourfree", "glm-5.3-flash-free", 8.8, 8.4, "GLM 5.3 Flash"),
    FreeModel("ourfree", "nemotron-3.5-lightning-free", 8.5, 9.1, "Nemotron 3.5 Lightning"),
    FreeModel("ourfree", "mimo-v2.6-flash-free", 8.2, 9.2, "MiMo V2.6 Flash"),
    FreeModel("ourfree", "nemotron-3-ultra-free", 8.9, 6.6, "Nemotron 3 Ultra"),
    FreeModel("ourfree", "mimo-v2.5-free", 7.9, 8.6, "MiMo V2.5"),
    FreeModel("ourfree", "muse-spark-1.3-contributor-free", 8.6, 7.1, "Muse Spark 1.3"),
    FreeModel("ourfree", "union-alpha", 8.1, 7.6, "Union Alpha"),
    FreeModel("ourfree", "ling-3.0-flash-fin-free", 7.8, 8.2, "Ling 3.0 Flash Fin"),
    FreeModel("ourfree", "muse-spark-1.2-contributor-free", 8.1, 7.0, "Muse Spark 1.2"),
    FreeModel("ourfree", "jev-1.13-free", 7.3, 8.1, "Jev 1.13"),
    FreeModel("ourfree", "space-bunny-free", 7.0, 8.0, "Space Bunny"),
    FreeModel("kilo", "kilo-auto/free", 8.3, 8.2, "Kilo Auto Free"),
    FreeModel("kilo", "openrouter/free", 8.0, 7.9, "OpenRouter Free"),
    FreeModel("pollinations", "openai-fast", 7.5, 8.8, "Pollinations GPT-OSS 20B"),
    FreeModel("gemini", "gemini-4-argon", 9.2, 7.4, "Gemini 4 Argon"),
    FreeModel("gemini", "gemini-3.8-flash", 8.6, 9.1, "Gemini 3.8 Flash"),
    FreeModel("gemini", "gemini-3.1-pro-preview", 8.4, 7.2, "Gemini 3.1 Pro Preview"),
    FreeModel("gemini", "gemini-3.5-flash-lite", 7.6, 9.3, "Gemini 3.5 Flash Lite"),
    FreeModel("freebuff", "mimo/mimo-v2.5", 8.5, 8.7, "Freebuff MiMo V2.5"),
    FreeModel("freebuff", "z-ai/glm-5.3-flash", 8.4, 8.3, "Freebuff GLM 5.3"),
    FreeModel("freebuff", "deepseek/deepseek-v4-flash", 8.8, 8.6, "Freebuff DeepSeek V4"),
    FreeModel("qoder", "auto", 8.6, 7.5, "Qoder Smart Routing"),
)


def _roster(provider) -> List[str]:
    """The models a provider advertises without a network call."""
    roster: List[str] = []
    for attr in ("models", "default_models"):
        values = getattr(provider, attr, None)
        if isinstance(values, (list, tuple)):
            roster.extend(str(value) for value in values)
    return roster


def _availability(model: FreeModel, providers: Dict[str, object]) -> float:
    """How confidently this entry can answer right now, between 0 and 1."""
    provider = providers.get(model.provider)
    if provider is None:
        return 0.0
    try:
        usable = bool(provider.validate_api_key())
    except Exception:
        usable = False
    if not usable:
        return 0.0
    roster = _roster(provider)
    if model.model in roster:
        return 1.0
    if roster:
        # The provider is configured but this curated entry is not in its
        # published roster; keep it as a lower-confidence fallback.
        return 0.7
    # A provider with live-only discovery: still usable, but unproven.
    return 0.8


def ranked(providers: Dict[str, object]) -> List[FreeModel]:
    """Rank every usable free model by availability, intelligence and speed."""
    scored = []
    for index, entry in enumerate(CATALOG):
        availability = _availability(entry, providers)
        if availability <= 0:
            continue
        scored.append((entry.score(availability), -index, entry))
    scored.sort(reverse=True)
    return [entry for _, _, entry in scored]


def candidates(providers: Dict[str, object]) -> List[Tuple[str, str, str]]:
    """The ranked free models as ``(provider, model, label)`` rows."""
    return [(entry.provider, entry.model, entry.display) for entry in ranked(providers)]


def describe(providers: Dict[str, object], limit: Optional[int] = None) -> List[str]:
    """Human-readable ranked rows, used by ``models list free``."""
    entries = ranked(providers)
    if limit is not None:
        entries = entries[:limit]
    return [f"{entry.provider}/{entry.model}  ({entry.display})" for entry in entries]


def select(providers: Dict[str, object]) -> Optional[FreeModel]:
    """The single best free model, or ``None`` when no free lane is usable."""
    entries = ranked(providers)
    return entries[0] if entries else None


def _is_transient_error(error: Exception) -> bool:
    """Whether a failure is worth a quick retry or failover."""
    text = str(error).lower()
    transient = (
        "429",
        "rate limit",
        "rate-limit",
        "ratelimit",
        "too many requests",
        "timeout",
        "timed out",
        "temporar",
        "overloaded",
        "capacity",
        "busy",
        "503",
        "502",
        "504",
        "500",
        "connection",
        "reset by peer",
        "server error",
        "try again",
        "unavailable",
        "admit",
    )
    permanent = (
        "invalid api key",
        "unauthorized",
        "forbidden",
        "not configured",
        "no credential",
        "no free model is configured",
        "missing",
        "does not exist",
        "unknown model",
        "unsupported",
    )
    if any(mark in text for mark in permanent):
        return False
    return any(mark in text for mark in transient)


def chat(providers: Dict[str, object], messages: Sequence[Dict[str, str]], **kwargs):
    """Answer with the best available free model, failing over on errors.

    Returns ``(FreeModel, reply)``. Raises ``ValueError`` when every candidate
    failed, including the collected provider errors so the TUI/CLI can show
    what actually happened instead of a generic failure.
    """
    import time

    entries = ranked(providers)
    if not entries:
        raise ValueError(
            "No free model is configured. Sign in to Gemini/Freebuff/Qoder, or "
            "configure ourfree; kilo and pollinations are keyless."
        )

    errors: List[str] = []
    attempts = 0
    max_attempts = 12  # avoid very long stalls while still being resilient
    for entry in entries:
        provider = providers.get(entry.provider)
        if provider is None:
            continue
        for attempt in range(2):
            attempts += 1
            if attempts > max_attempts:
                break
            try:
                reply = provider.chat(entry.model, list(messages), **kwargs)
            except Exception as error:  # Fail over: the point of Auto is availability.
                errors.append(f"{entry.provider}/{entry.model}: {error}")
                if attempt == 0 and _is_transient_error(error):
                    time.sleep(0.6)
                    continue
                break
            if isinstance(reply, str) and reply.strip():
                return entry, reply
            errors.append(f"{entry.provider}/{entry.model}: empty reply")
            if attempt == 0:
                time.sleep(0.25)
                continue
            break
        if attempts > max_attempts:
            break
    detail = " | ".join(errors[-4:]) if errors else "no candidate answered"
    raise ValueError(f"free (Auto) could not get an answer. {detail}")
