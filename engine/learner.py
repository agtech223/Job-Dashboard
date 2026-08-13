# -*- coding: utf-8 -*-
"""
LEARNING FROM YOUR RATINGS
==========================
Every job carries a "Fit" / "Not a fit" control. Those verdicts do two things:

  1. A "not a fit" posting is dropped from the dashboard on the next refresh.
  2. Both verdicts train a small model that nudges future scores toward the
     kind of job you keep and away from the kind you reject.

The model is a Naive Bayes log-odds classifier over coarse features (research
area, role, country, source, and notable title words). It is deliberately
timid, because feedback data here will always be small:

  * it does nothing at all until MIN_FEEDBACK ratings exist;
  * Laplace smoothing stops one rating from dominating a feature;
  * the total adjustment is squashed through tanh and hard-clamped to
    +/- MAX_ADJUST points, so learning re-orders near-ties, it never
    overturns the agriculture gate or invents a strong match.

Feedback lives in docs/data/feedback.json, and each record keeps the features
of the job as it was when you rated it -- so training still works after the
posting itself has expired off the boards.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEEDBACK_FILE = os.path.join(ROOT, "docs", "data", "feedback.json")

MIN_FEEDBACK = 8          # ratings needed before the model is consulted at all
MIN_PER_CLASS = 3         # ...and at least this many of EACH verdict
MAX_ADJUST = 8.0          # hard ceiling on the score nudge, in points
SMOOTHING = 1.0           # Laplace alpha
LOG_ODDS_SCALE = 4.0      # tanh scale: how much evidence saturates the nudge

_STOPWORDS = {
    "the", "and", "for", "with", "position", "professor", "assistant",
    "associate", "faculty", "lecturer", "senior", "junior", "research",
    "researcher", "fellow", "postdoctoral", "postdoc", "scientist", "officer",
    "university", "college", "school", "department", "tenure", "track",
    "full", "time", "part", "term", "limited", "chair", "head", "level",
    "rank", "open", "new", "job", "role", "work", "team", "you", "our",
}


# ---------------------------------------------------------------------------
# Feedback store
# ---------------------------------------------------------------------------
def load_feedback() -> dict:
    """-> {job_id: {"verdict": "fit"|"not_fit", "at": iso, ...features}}"""
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_feedback(feedback: dict) -> None:
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as fh:
        json.dump(feedback, fh, ensure_ascii=False, indent=1)


def rejected_ids(feedback: dict) -> set:
    return {jid for jid, rec in feedback.items()
            if isinstance(rec, dict) and rec.get("verdict") == "not_fit"}


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
def features(job: dict) -> list[str]:
    """
    Coarse, human-readable features. The same function runs at training time
    and at scoring time, so a stored rating and a live posting are described
    the same way.
    """
    out = []
    for area in (job.get("ag_areas") or []):
        out.append(f"ag:{area}")
    for area in (job.get("tech_areas") or []):
        out.append(f"tech:{area}")
    if job.get("role"):
        out.append(f"role:{job['role']}")
    if job.get("country"):
        out.append(f"country:{job['country']}")
    if job.get("source"):
        out.append(f"source:{job['source']}")
    if job.get("is_faculty"):
        out.append("flag:faculty")
    if job.get("is_tenure_track"):
        out.append("flag:tenure")
    if job.get("is_government"):
        out.append("flag:government")
    if job.get("via_discipline"):
        out.append("flag:discipline")
    if job.get("synergy"):
        out.append("flag:synergy")

    title = re.sub(r"[^a-z0-9 ]+", " ", (job.get("title") or "").lower())
    for word in title.split():
        if len(word) > 3 and word not in _STOPWORDS:
            out.append(f"word:{word}")

    return sorted(set(out))


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
def train(feedback: dict) -> dict | None:
    """Count features per class. Returns None when there is too little data."""
    fit_docs = nofit_docs = 0
    fit = defaultdict(int)
    nofit = defaultdict(int)

    for rec in feedback.values():
        if not isinstance(rec, dict):
            continue
        verdict = rec.get("verdict")
        if verdict not in ("fit", "not_fit"):
            continue
        feats = rec.get("features") or features(rec)
        if verdict == "fit":
            fit_docs += 1
            for f in feats:
                fit[f] += 1
        else:
            nofit_docs += 1
            for f in feats:
                nofit[f] += 1

    total = fit_docs + nofit_docs
    if total < MIN_FEEDBACK or fit_docs < MIN_PER_CLASS or nofit_docs < MIN_PER_CLASS:
        # Sparse or lopsided feedback carries no reliable signal. Three
        # rejections and one approval is not a preference, it is noise, and
        # acting on it would teach the ranker to avoid whole research areas
        # that merely happened to appear in the rejected postings.
        return None

    return {"fit": dict(fit), "nofit": dict(nofit),
            "fit_docs": fit_docs, "nofit_docs": nofit_docs, "total": total}


def _log_odds(model: dict, feature: str) -> float:
    """Smoothed log P(feature | fit) / P(feature | not fit)."""
    p_fit = (model["fit"].get(feature, 0) + SMOOTHING) / (model["fit_docs"] + 2 * SMOOTHING)
    p_no = (model["nofit"].get(feature, 0) + SMOOTHING) / (model["nofit_docs"] + 2 * SMOOTHING)
    return math.log(p_fit / p_no)


def adjustment(job: dict, model: dict | None) -> float:
    """Bounded score nudge in points. 0.0 when the model is not ready."""
    if not model:
        return 0.0
    feats = features(job)
    if not feats:
        return 0.0
    # Average rather than sum: a long title must not out-vote a short one.
    total = sum(_log_odds(model, f) for f in feats) / math.sqrt(len(feats))
    return round(MAX_ADJUST * math.tanh(total / LOG_ODDS_SCALE), 2)


def explain(model: dict | None, limit: int = 6) -> dict:
    """The strongest learned signals, for the dashboard and the log."""
    if not model:
        return {"ready": False, "ratings": 0, "likes": [], "dislikes": []}
    seen = set(model["fit"]) | set(model["nofit"])
    scored = sorted(((_log_odds(model, f), f) for f in seen), reverse=True)
    pretty = lambda f: f.split(":", 1)[1] if ":" in f else f
    return {
        "ready": True,
        "ratings": model["total"],
        "fit": model["fit_docs"],
        "not_fit": model["nofit_docs"],
        "likes": [pretty(f) for _, f in scored[:limit]],
        "dislikes": [pretty(f) for _, f in scored[-limit:]][::-1],
    }
