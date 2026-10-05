"""Performance-weighted strategy selector.

Each family keeps an EWMA of its realised R-multiples (P&L / initial risk,
after costs). On a bar where several families signal, the one with the best
score wins; families below `ensemble_min_score` are benched until their score
recovers (they keep being scored on paper so they can come back). Scores start
at 0, so a new family gets a fair trial. State is serialisable (engine.json).
"""
from __future__ import annotations

from .strategies.base import Signal


class Selector:
    def __init__(self, names: list[str], lookback: int = 30, min_score: float = -0.3):
        self.names = list(names)
        self.alpha = 1.0 / max(1, lookback)
        self.min_score = min_score
        self.score = {n: 0.0 for n in self.names}
        self.n = {n: 0 for n in self.names}

    def update(self, name: str, r_multiple: float) -> None:
        if name not in self.score:
            self.score[name], self.n[name] = 0.0, 0
        self.score[name] += self.alpha * (r_multiple - self.score[name])
        self.n[name] += 1

    def pick(self, candidates: list[Signal]) -> Signal | None:
        live = [c for c in candidates if c.side != 0]
        if not live:
            return None
        if len(live) == 1 and len(self.names) == 1:
            return live[0]
        ok = [c for c in live if self.score.get(c.strategy, 0.0) >= self.min_score]
        if not ok:
            return None
        # disagreement on direction between the two best: stand aside
        ok.sort(key=lambda c: (self.score.get(c.strategy, 0.0), -self.names.index(c.strategy)), reverse=True)
        if len(ok) > 1 and ok[0].side != ok[1].side and \
                abs(self.score[ok[0].strategy] - self.score[ok[1].strategy]) < 0.1:
            return None
        return ok[0]

    def to_dict(self) -> dict:
        return {"score": self.score, "n": self.n}

    def load(self, d: dict | None) -> None:
        if d:
            self.score.update({k: float(v) for k, v in d.get("score", {}).items()})
            self.n.update({k: int(v) for k, v in d.get("n", {}).items()})
