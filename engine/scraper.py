# -*- coding: utf-8 -*-
"""
SCRAPER  --  fetches every source in parallel, scores against the CV,
de-duplicates, and writes data/jobs.json for the dashboard.

Run directly:      python scraper.py
Called by:         server.py  (the dashboard's Refresh button)
                   REFRESH-NOW.bat / the scheduled task
"""
from __future__ import annotations

import concurrent.futures as cf
import io
import json
import os
import sys
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import learner                                      # noqa: E402
from matcher import deduplicate, score_job          # noqa: E402
from profile import (CANDIDATE, GOOD_MATCH, MAX_AGE_DAYS, SCORE_FLOOR,       # noqa: E402
                     STRONG_MATCH)
from sources import SOURCE_NAMES, build_tasks       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Published data -- committed to the repo and served by GitHub Pages.
PUBLIC = os.path.join(ROOT, "docs", "data")
JOBS_FILE = os.path.join(PUBLIC, "jobs.json")
SEEN_FILE = os.path.join(PUBLIC, "seen.json")

# Machine-local runtime files -- never committed (see .gitignore).
DATA = os.path.join(HERE, "data")
LOG_FILE = os.path.join(DATA, "refresh.log")

MAX_WORKERS = 10

# A posting we have not re-seen on any board for this many days is treated as
# closed and drops off the dashboard.
STALE_AFTER_DAYS = 10

# The fields that come straight off a job board. Everything else on a record
# (score, role, country, matched keywords) is derived and always recomputed.
RAW_FIELDS = ("title", "org", "location", "url", "posted", "summary",
              "salary", "source")

# progress is shared with server.py so the dashboard can show a live bar
PROGRESS = {"running": False, "done": 0, "total": 0, "stage": "idle",
            "found": 0, "error": None, "finished_at": None}


def _utf8_stdout():
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _load_seen() -> dict:
    return _read_json(SEEN_FILE, {})


def _days_since(iso: str | None):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - d).days)
    except Exception:
        return None


def refresh(progress: dict | None = None) -> dict:
    """Fetch everything, score it, write jobs.json. Returns the payload."""
    p = progress if progress is not None else PROGRESS
    tasks = build_tasks()
    p.update({"running": True, "done": 0, "total": len(tasks),
              "stage": "Contacting job boards", "found": 0, "error": None})

    log(f"Refresh started -- {len(tasks)} source queries across {len(SOURCE_NAMES)} boards")

    raw: list[dict] = []
    per_source: dict[str, int] = {}
    failures = 0

    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fn): label for label, fn in tasks}
        for fut in cf.as_completed(futures):
            label = futures[fut]
            try:
                items = fut.result() or []
                for it in items:
                    if it.get("title") and it.get("url"):
                        raw.append(it)
                        per_source[it["source"]] = per_source.get(it["source"], 0) + 1
            except Exception:
                failures += 1
            p["done"] += 1
            p["found"] = len(raw)
            if p["done"] % 12 == 0:
                p["stage"] = f"Fetched {p['done']}/{p['total']} queries -- {len(raw)} postings"

    log(f"Fetched {len(raw)} raw postings ({failures} queries failed)")
    for s in SOURCE_NAMES:
        log(f"    {s:26s} {per_source.get(s, 0):5d}")

    # ---- score ----------------------------------------------------------
    p["stage"] = "Scoring against your CV"
    scored = []
    rejected_non_ag = 0
    for j in raw:
        try:
            sj = score_job(j)
            if sj.get("rejected") == "not agricultural":
                rejected_non_ag += 1
                continue
            if sj["score"] >= SCORE_FLOOR:
                if sj["age_days"] is None or sj["age_days"] <= MAX_AGE_DAYS:
                    scored.append(sj)
        except Exception:
            continue
    log(f"{rejected_non_ag} postings discarded as non-agricultural")
    log(f"{len(scored)} postings scored at or above the floor ({SCORE_FLOOR})")

    # ---- carry forward anything a source failed to serve this time ------
    # Boards go down, rate-limit, or bot-block. Without this, one bad response
    # would silently wipe that board's postings off the dashboard, which looks
    # exactly like "those jobs closed". Instead we keep the previous run's copy
    # until it goes stale.
    p["stage"] = "Merging with the previous run"
    carried = 0
    previous = _read_json(JOBS_FILE, {}).get("jobs", [])
    fresh_ids = {j["id"] for j in scored}
    for old in previous:
        if old.get("id") in fresh_ids:
            continue
        seen_days = _days_since(old.get("last_seen") or old.get("first_seen"))
        if seen_days is None or seen_days > STALE_AFTER_DAYS:
            continue
        # Re-score from the raw posting rather than reusing the stored result,
        # so a carried-over job reflects the current profile and matcher exactly
        # like a freshly fetched one.
        try:
            revived = score_job({k: old.get(k, "") for k in RAW_FIELDS})
        except Exception:
            continue
        if revived["score"] < SCORE_FLOOR:
            continue
        if revived["age_days"] is not None and revived["age_days"] > MAX_AGE_DAYS:
            continue
        revived["carried_over"] = True
        revived["is_new"] = False
        revived["first_seen"] = old.get("first_seen")
        revived["last_seen"] = old.get("last_seen")
        scored.append(revived)
        carried += 1
    if carried:
        log(f"Carried {carried} postings forward from the previous run "
            f"(source unavailable this time)")

    # ---- de-duplicate ---------------------------------------------------
    p["stage"] = "Removing cross-board duplicates"
    jobs = deduplicate(scored)

    # ---- your ratings ---------------------------------------------------
    # "Not a fit" postings leave the dashboard; both verdicts train the model
    # that nudges what is left. See engine/learner.py for why it is timid.
    p["stage"] = "Applying what your ratings taught"
    feedback = learner.load_feedback()
    rejected = learner.rejected_ids(feedback)
    if rejected:
        before = len(jobs)
        jobs = [j for j in jobs if j["id"] not in rejected]
        log(f"Removed {before - len(jobs)} posting(s) you marked as not a fit")

    model = learner.train(feedback)
    insight = learner.explain(model)
    if model:
        for j in jobs:
            delta = learner.adjustment(j, model)
            j["learned"] = delta
            j["score"] = round(max(0.0, min(100.0, j["score"] + delta)), 1)
        moved = sum(1 for j in jobs if abs(j.get("learned", 0)) >= 1)
        log(f"Learned from {insight['ratings']} ratings "
            f"({insight['fit']} fit / {insight['not_fit']} not) -- "
            f"adjusted {moved} posting(s)")
        log(f"    leaning toward: {', '.join(insight['likes'][:4])}")
        log(f"    leaning away  : {', '.join(insight['dislikes'][:4])}")
    elif feedback:
        log(f"{len(feedback)} rating(s) so far -- the model needs "
            f"{learner.MIN_FEEDBACK} including both verdicts before it acts")
    jobs.sort(key=lambda x: (x.get("priority", 3), -x["score"],
                             x.get("age_days") if x.get("age_days") is not None else 999))
    log(f"{len(jobs)} unique postings after de-duplication")

    # ---- flag what is new since the last run ----------------------------
    seen = _load_seen()
    now_iso = datetime.now(timezone.utc).isoformat()
    new_count = 0
    for j in jobs:
        if j.get("carried_over"):
            j.setdefault("first_seen", now_iso)
            j["is_new"] = False
        elif j["id"] in seen:
            j["first_seen"] = seen[j["id"]]
            j["is_new"] = False
            j["last_seen"] = now_iso
        else:
            j["first_seen"] = now_iso
            j["is_new"] = True
            j["last_seen"] = now_iso
            new_count += 1
        seen[j["id"]] = j["first_seen"]

    # ---- assemble payload ----------------------------------------------
    payload = {
        "generated_at": now_iso,
        "candidate": CANDIDATE,
        "thresholds": {"strong": STRONG_MATCH, "good": GOOD_MATCH, "floor": SCORE_FLOOR},
        "stats": {
            "total": len(jobs),
            "new": new_count,
            "raw_fetched": len(raw),
            "rejected_non_ag": rejected_non_ag,
            "queries_run": len(tasks),
            "queries_failed": failures,
            "strong": sum(1 for j in jobs if j["score"] >= STRONG_MATCH),
            "good": sum(1 for j in jobs if GOOD_MATCH <= j["score"] < STRONG_MATCH),
            "countries": len({j["country"] for j in jobs if j["country"] != "Unspecified"}),
            "carried_over": sum(1 for j in jobs if j.get("carried_over")),
            "learning": insight,
            "canada": sum(1 for j in jobs if j.get("is_priority_country")),
            "canada_faculty": sum(1 for j in jobs if j.get("priority") == 0),
            "tenure_track": sum(1 for j in jobs if j.get("is_tenure_track")),
            "faculty": sum(1 for j in jobs if j.get("is_faculty")),
            "per_source": per_source,
        },
        "jobs": jobs,
    }

    os.makedirs(PUBLIC, exist_ok=True)
    with open(JOBS_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    with open(SEEN_FILE, "w", encoding="utf-8") as fh:
        json.dump(seen, fh)

    p.update({"running": False, "stage": "done", "found": len(jobs),
              "finished_at": now_iso})
    log(f"Wrote {JOBS_FILE}  --  {len(jobs)} jobs, {new_count} new, "
        f"{payload['stats']['strong']} strong matches")
    return payload


def refresh_safe(progress: dict):
    try:
        refresh(progress)
    except Exception as exc:
        progress.update({"running": False, "stage": "error", "error": str(exc)})
        log("REFRESH FAILED: " + traceback.format_exc())


if __name__ == "__main__":
    _utf8_stdout()
    print("=" * 66)
    print(" Academic Job Radar  --  live refresh")
    print(" " + CANDIDATE["name"])
    print("=" * 66)
    data = refresh()
    print()
    print(f"  Total live matches : {data['stats']['total']}")
    print(f"  Strong matches     : {data['stats']['strong']}")
    print(f"  New since last run : {data['stats']['new']}")
    print(f"  Countries          : {data['stats']['countries']}")
    print()
    for j in data["jobs"][:10]:
        loc = j["country"] if j["country"] != "Unspecified" else (j["location"] or "-")
        print(f"  {j['score']:5.1f}  {j['title'][:58]:58s} | {loc[:18]:18s} | {j['source']}")
