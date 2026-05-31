"""Pure, testable decision math (ROADMAP §7.4). No I/O, no LLM."""
from __future__ import annotations

from ..schemas import Position, Stance


def weighted_score(scores: dict[str, float], weights: dict[str, float]) -> float:
    """Σ(wᵢ·sᵢ) / Σ(wᵢ) over agents present in `scores`."""
    ids = [i for i in scores if weights.get(i, 0) > 0]
    total_w = sum(weights[i] for i in ids)
    if total_w == 0:
        return 0.0
    return sum(weights[i] * scores[i] for i in ids) / total_w


def normalized_variance(values: list[float], lo: float = 0.0, hi: float = 10.0) -> float:
    """Variance scaled to 0..1 (max variance for a 2-point split at the extremes)."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    max_var = ((hi - lo) / 2) ** 2
    return min(1.0, var / max_var) if max_var else 0.0


def consensus(scores: list[float]) -> float:
    """1 = unanimous, 0 = maximally split."""
    return 1.0 - normalized_variance(scores)


def decision_from_score(score: float) -> Stance:
    if score >= 7.0:
        return Stance.YES
    if score >= 5.0:
        return Stance.CONDITIONAL
    return Stance.NO


def apply_veto_cap(decision: Stance, agents, positions: dict[str, Position]) -> Stance:
    """A structural 'veto' agent (e.g. the Skeptic) can block a clean win but not
    force a loss: if any veto agent is not itself convinced (its final stance is
    not YES), a YES verdict is capped down to CONDITIONAL. NO/CONDITIONAL verdicts
    pass through untouched."""
    if decision != Stance.YES:
        return decision
    for a in agents:
        if getattr(a, "veto", False):
            p = positions.get(a.id)
            if p and p.stance != Stance.YES:
                return Stance.CONDITIONAL
    return decision


def blended_confidence(positions: list[Position]) -> float:
    """Half consensus, half average self-reported confidence."""
    if not positions:
        return 0.0
    cons = consensus([p.score for p in positions])
    avg_conf = sum(p.confidence for p in positions) / len(positions)
    return round(0.5 * cons + 0.5 * avg_conf, 3)
