# -*- coding: utf-8 -*-
"""
LIVE JOB SOURCES
================
Every source here was probed against the live internet and returns real,
machine-readable postings. Each adapter yields normalised dicts:

    {title, org, location, url, posted, summary, salary, source}

Adding a source = write one generator and register it in SOURCES.
"""
from __future__ import annotations

import html
import random
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests

from profile import BROAD_QUERIES, GOV_QUERIES, SEARCH_QUERIES

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 25

# --------------------------------------------------------------------------
# Polite HTTP layer
# --------------------------------------------------------------------------
# Several boards (HigherEdJobs especially) sit behind Imperva/Incapsula and will
# quietly serve a bot-challenge page instead of the feed if hit too fast. We pace
# per host, keep cookies on a shared session, and retry a blocked response.
_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)

HOST_MIN_INTERVAL = {
    "www.higheredjobs.com": 4.0,     # Imperva-protected -- tread lightly
    "www.jobs.ac.uk": 0.9,
    "euraxess.ec.europa.eu": 0.6,
    "jobrxiv.org": 0.6,
}
DEFAULT_INTERVAL = 0.25

_host_locks: dict[str, threading.Lock] = {}
_host_last: dict[str, float] = {}
_meta_lock = threading.Lock()

BLOCK_MARKERS = ("_Incapsula_Resource", "Request unsuccessful", "Access Denied",
                 "Pardon Our Interruption", "captcha-delivery")


def _throttle(host: str):
    with _meta_lock:
        lock = _host_locks.setdefault(host, threading.Lock())
    interval = HOST_MIN_INTERVAL.get(host, DEFAULT_INTERVAL)
    with lock:
        wait = interval - (time.time() - _host_last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _host_last[host] = time.time()


def _blocked(body: str) -> bool:
    return any(m in body[:1500] for m in BLOCK_MARKERS)


def _get(url: str, retries: int = 3) -> str | None:
    host = urlparse(url).netloc
    for attempt in range(retries):
        _throttle(host)
        try:
            r = _SESSION.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                body = r.text
                if not _blocked(body):
                    return body
            elif r.status_code in (400, 404, 410):
                return None            # genuinely not there -- do not retry
        except Exception:
            pass
        time.sleep(1.6 * (attempt + 1) + random.random())
    return None


def _clean(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _iso(entry) -> str:
    """Best-effort published date -> ISO string."""
    for key in ("published_parsed", "updated_parsed"):
        tp = entry.get(key)
        if tp:
            try:
                return datetime(*tp[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return ""


def _quote(q: str) -> str:
    return requests.utils.quote(q)


# --------------------------------------------------------------------------
# 1. MADGEX-PLATFORM BOARDS  (Nature Careers, THE, Chronicle, Inside Higher Ed)
#    All expose /jobsrss/?keywords=...&page=N  -- 20 results per page.
# --------------------------------------------------------------------------
MADGEX_BOARDS = [
    ("Nature Careers", "https://www.nature.com/naturecareers/jobsrss/"),
    ("Times Higher Education", "https://www.timeshighereducation.com/unijobs/jobsrss/"),
    ("Chronicle of Higher Ed", "https://jobs.chronicle.com/jobsrss/"),
    ("Inside Higher Ed", "https://careers.insidehighered.com/jobsrss/"),
]
MADGEX_PAGES = 3


def madgex(board_name: str, base: str, query: str, page: int):
    url = f"{base}?keywords={_quote(query)}" + (f"&page={page}" if page > 1 else "")
    body = _get(url)
    if not body:
        return
    for e in feedparser.parse(body).entries:
        raw_title = _clean(e.get("title", ""))
        summary = _clean(e.get("summary", ""))
        # Madgex titles look like "University of X: Assistant Professor of Y"
        org, _, title = raw_title.partition(": ")
        if not title:
            org, title = "", raw_title
        # Summary looks like "Salary: Org: description ... Location (CC)"
        salary = ""
        m = re.match(r"^([^:]{2,40}):\s", summary)
        if m and any(c.isdigit() or c in "$£€" for c in m.group(1)) or \
           (m and m.group(1).lower() in ("competitive", "negotiable", "not specified")):
            salary = m.group(1).strip()
        location = ""
        m = re.search(r"([A-Z][A-Za-z .,'\-]{2,60}\([A-Z]{2}\))\s*$", summary)
        if m:
            location = m.group(1).strip()
        yield {
            "title": title.strip() or raw_title,
            "org": org.strip(),
            "location": location,
            "url": (e.get("link", "") or "").split("?TrackID")[0],
            "posted": _iso(e),
            "summary": summary,
            "salary": salary,
            "source": board_name,
        }


# --------------------------------------------------------------------------
# 2. HIGHEREDJOBS  --  per-discipline RSS feeds (US-heavy, very deep)
# --------------------------------------------------------------------------
# HigherEdJobs sits behind Imperva and will IP-block a client that pulls many
# feeds in quick succession -- so we take only the highest-value categories,
# slowly (see HOST_MIN_INTERVAL). If it blocks anyway, the carry-over merge in
# scraper.py keeps the previous run's HigherEdJobs postings on the dashboard.
HEJ_CATEGORIES = {
    111: "Agricultural Engineering",
    283: "Farming and Agriculture",
    58:  "Other Agriculture Faculty",
    49:  "Plant and Soil Science",
    120: "Other Engineering Faculty",
    54:  "Environmental Science & Forestry",
}


def higheredjobs(cat_id: int, cat_name: str):
    body = _get(f"https://www.higheredjobs.com/rss/categoryFeed.cfm?catID={cat_id}")
    if not body:
        return
    for e in feedparser.parse(body).entries:
        title = _clean(e.get("title", ""))
        summary = _clean(e.get("summary", ""))
        # summary is "Institution Name (City, ST)"
        org, location = summary, ""
        m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", summary)
        if m:
            org, location = m.group(1).strip(), m.group(2).strip()
        yield {
            "title": re.sub(r"\s*\(\d+\)\s*$", "", title),
            "org": org,
            "location": location,
            "url": e.get("link", ""),
            "posted": _iso(e),
            "summary": f"{cat_name}. {summary}",
            "salary": "",
            "source": "HigherEdJobs",
        }


# --------------------------------------------------------------------------
# 3. JOBS.AC.UK  --  HTML scrape (UK + international, the major academic board)
# --------------------------------------------------------------------------
def jobs_ac_uk(query: str):
    body = _get(f"https://www.jobs.ac.uk/search/?keywords={_quote(query)}")
    if not body:
        return
    for block in body.split('data-advert-id="')[1:]:
        block = block[:4000]
        m = re.search(r'<a href="(/job/[^"]+)">\s*([^<]+)', block)
        if not m:
            continue
        href, title = m.group(1), _clean(m.group(2))
        org = ""
        m = re.search(r'j-search-result__employer">\s*<b>(.*?)</b>', block, re.S)
        if m:
            org = _clean(m.group(1))
        dept = ""
        m = re.search(r'j-search-result__department">(.*?)</div>', block, re.S)
        if m:
            dept = _clean(m.group(1))
        location = ""
        m = re.search(r'<div>Location:\s*(.*?)</div>', block, re.S)
        if m:
            location = _clean(m.group(1))
        salary = ""
        m = re.search(r'<strong>Salary:\s*</strong>(.*?)</div>', block, re.S)
        if m:
            salary = _clean(m.group(1))[:80]
        posted = ""
        m = re.search(r'<strong>Date Placed:\s*</strong>\s*([^<]+)', block)
        if m:
            posted = _parse_uk_date(_clean(m.group(1)))
        yield {
            "title": title,
            "org": org,
            "location": location or "United Kingdom",
            "url": "https://www.jobs.ac.uk" + href,
            "posted": posted,
            "summary": " ".join(x for x in (dept, org, location) if x),
            "salary": salary,
            "source": "jobs.ac.uk",
        }


def _parse_uk_date(s: str) -> str:
    """'24 Jul' / '24 Jul 2026' -> ISO."""
    s = s.strip()
    now = datetime.now(timezone.utc)
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    for fmt in ("%d %b", "%d %B"):
        try:
            d = datetime.strptime(s, fmt).replace(year=now.year, tzinfo=timezone.utc)
            if d > now:                      # date rolled over the new year
                d = d.replace(year=now.year - 1)
            return d.isoformat()
        except ValueError:
            pass
    return ""


# --------------------------------------------------------------------------
# 4. EURAXESS  --  European Commission researcher mobility portal (HTML)
# --------------------------------------------------------------------------
EURAXESS_PAGES = 2


def euraxess(query: str, page: int):
    url = f"https://euraxess.ec.europa.eu/jobs/search?keywords={_quote(query)}"
    if page > 0:
        url += f"&page={page}"
    body = _get(url)
    if not body:
        return
    for block in body.split('<div id="job-teaser-content">')[1:]:
        block = block[:6000]
        m = re.search(r'<h3 class="ecl-content-block__title">.*?href="(/jobs/\d+)".*?<span>(.*?)</span>',
                      block, re.S)
        if not m:
            continue
        href, title = m.group(1), _clean(m.group(2))
        country = ""
        m2 = re.search(r'ecl-label--highlight"\s*>([^<]+)</span>', block)
        if m2:
            country = _clean(m2.group(1))
        org = ""
        m3 = re.search(r'primary-meta-item"><a href="[^"]*"[^>]*>([^<]+)</a>', block)
        if m3:
            org = _clean(m3.group(1))
        posted = ""
        m4 = re.search(r'Posted on:\s*([0-9]{1,2}\s+\w+\s+[0-9]{4})', block)
        if m4:
            try:
                posted = datetime.strptime(m4.group(1).strip(), "%d %B %Y").replace(
                    tzinfo=timezone.utc).isoformat()
            except ValueError:
                posted = ""
        desc = ""
        m5 = re.search(r'ecl-content-block__description"><p>(.*?)</p>', block, re.S)
        if m5:
            desc = _clean(m5.group(1))
        yield {
            "title": title,
            "org": org,
            "location": country,
            "url": "https://euraxess.ec.europa.eu" + href,
            "posted": posted,
            "summary": desc,
            "salary": "",
            "source": "EURAXESS",
        }


# --------------------------------------------------------------------------
# 5. jobRxiv  --  research-community job board (global)
# --------------------------------------------------------------------------
def jobrxiv(query: str):
    url = f"https://jobrxiv.org/?feed=job_feed&search_keywords={_quote(query)}"
    body = _get(url)
    if not body:
        return
    for e in feedparser.parse(body).entries:
        yield {
            "title": _clean(e.get("title", "")),
            "org": _clean(e.get("job_listing_company", "")),
            "location": _clean(e.get("job_listing_location", "")),
            "url": e.get("link", ""),
            "posted": _iso(e),
            "summary": _clean(e.get("summary", ""))[:1200],
            "salary": "",
            "source": "jobRxiv",
        }


# --------------------------------------------------------------------------
# 6. CAUT / AcademicWork.ca  --  the Canadian academic job board
#    (Canadian Association of University Teachers). Every posting here is a
#    Canadian post, which is why it is paged in full rather than searched.
# --------------------------------------------------------------------------
CAUT_PAGES = 12


def caut(page: int):
    url = "https://www.academicwork.ca/jobs" + (f"?page={page}" if page > 1 else "")
    body = _get(url)
    if not body:
        return
    for block in re.split(r'<article class="[^"]*">', body)[1:]:
        block = block[:5000]
        m = re.search(r'href="([^"]+)"\s+class="job-title">\s*(.*?)\s*</a>', block, re.S)
        if not m:
            continue
        href, title = m.group(1), _clean(m.group(2))
        org = ""
        m2 = re.search(r'class="job-institution">\s*(.*?)\s*</a>', block, re.S)
        if m2:
            org = _clean(m2.group(1))
        posted = ""
        m3 = re.search(r'class="date-posted-value">\s*([^<]+)', block)
        if m3:
            for fmt in ("%B %d, %Y", "%b %d, %Y"):
                try:
                    posted = datetime.strptime(_clean(m3.group(1)), fmt).replace(
                        tzinfo=timezone.utc).isoformat()
                    break
                except ValueError:
                    pass
        desc = ""
        m4 = re.search(r'class="job-short-description">\s*(.*?)\s*</p>', block, re.S)
        if m4:
            desc = _clean(m4.group(1))
        yield {
            "title": title,
            "org": org,
            "location": "Canada",
            "url": href if href.startswith("http") else "https://www.academicwork.ca" + href,
            "posted": posted,
            "summary": desc or org,
            "salary": "",
            "source": "CAUT (Canada)",
        }


# --------------------------------------------------------------------------
# 7. CANADIAN UNIVERSITY CAREER PORTALS (Workday)
#    Workday exposes a clean public JSON API, so faculty postings that never
#    reach the aggregator boards are picked up directly from the university.
#
#    To add another university: find its careers URL of the shape
#      https://<tenant>.<wdN>.myworkdayjobs.com/en-US/<site>
#    and add (label, tenant, wdN, site) below. Verify with:
#      POST https://<tenant>.<wdN>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs
#    Only tenants confirmed to return HTTP 200 are listed here; several other
#    Canadian universities use non-standard site slugs or are not on Workday.
# --------------------------------------------------------------------------
WORKDAY_SITES = [
    ("McGill University", "mcgill", "wd3", "McGill_Careers"),
    ("University of British Columbia", "ubc", "wd10", "ubcstaffjobs"),
]
WORKDAY_MAX = 160          # postings per university per refresh
WORKDAY_PAGE = 20


def _workday_date(text: str) -> str:
    """'Posted 11 Days Ago' / 'Posted Yesterday' -> ISO date."""
    t = (text or "").lower()
    days = None
    if "today" in t:
        days = 0
    elif "yesterday" in t:
        days = 1
    else:
        m = re.search(r"(\d+)\+?\s*day", t)
        if m:
            days = int(m.group(1))
        else:
            m = re.search(r"(\d+)\+?\s*month", t)
            if m:
                days = int(m.group(1)) * 30
    if days is None:
        return ""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def workday(label: str, tenant: str, wd: str, site: str, offset: int):
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        _throttle(urlparse(url).netloc)
        r = _SESSION.post(url, timeout=TIMEOUT,
                          headers={"Accept": "application/json",
                                   "Content-Type": "application/json"},
                          json={"appliedFacets": {}, "limit": WORKDAY_PAGE,
                                "offset": offset, "searchText": ""})
        if r.status_code != 200:
            return
        postings = r.json().get("jobPostings") or []
    except Exception:
        return

    for p in postings:
        path = p.get("externalPath") or ""
        yield {
            "title": _clean(p.get("title", "")),
            "org": label,
            "location": _clean(p.get("locationsText", "")),
            "url": f"https://{tenant}.{wd}.myworkdayjobs.com/en-US/{site}{path}",
            "posted": _workday_date(p.get("postedOn", "")),
            "summary": " ".join([label] + [_clean(b) for b in (p.get("bulletFields") or [])]),
            "salary": "",
            "source": "University portal (Canada)",
        }


# --------------------------------------------------------------------------
# 8. CANADIAN GOVERNMENT  --  SuccessFactors career sites
#
#    Public-sector employers running SAP SuccessFactors expose a standard
#    RSS endpoint at /services/rss/job/. It honours a keyword filter and
#    returns up to 20 items, so it is queried once per search term exactly
#    like the academic boards.
#
#    Federal departments that recruit through GC Jobs (AAFC, CFIA, NRCan,
#    ECCC and most others) are NOT here: jobs.gc.ca is a JavaScript
#    application with no feed, no form and no public API, so it cannot be
#    scraped dependably. Use its own Job Alert instead -- see the README
#    section "Canadian government jobs".
# --------------------------------------------------------------------------
GOV_SF_SITES = [
    ("NRC (federal)", "recruitment-recrutement.nrc-cnrc.gc.ca", "en_US"),
    ("Nova Scotia (provincial)", "jobs.novascotia.ca", "en_US"),
]

# These feeds are bilingual -- every federal posting appears twice, once per
# official language. Keep the English copy.
_FR_STRONG = ("ingénieur", "chercheur", "conseillère", "conseiller ou",
              "informaticien", "gestionnaire", "adjointe", "technicienne",
              "principal(e)", "chargé", "responsable de", "ou agente",
              "spécialiste", "recherche et développement", "agente")
_FR_WEAK = (" ou ", " et ", " de la ", " des ", " du ", " aux ", " pour ")
_ACCENTS = "éèêëàâçùûôîï"


def _looks_french(title: str) -> bool:
    t = " " + title.lower() + " "
    if any(m in t for m in _FR_STRONG):
        return True
    weak = sum(1 for m in _FR_WEAK if m in t)
    return weak >= 2 or (weak >= 1 and any(c in t for c in _ACCENTS))


# SuccessFactors emits a placeholder item when a keyword matches nothing.
_EMPTY_MARKERS = ("no jobs currently available", "aucun emploi",
                  "check out our", "consultez")


def _sf_location(title: str):
    """'Job Name (WATERVILLE, NS, CA, B0P 1V0)' -> (clean title, location)."""
    m = re.search(r"\(([^()]{3,90})\)\s*$", title)
    if not m:
        return title, ""
    inner = m.group(1).strip()
    if not re.search(r",\s*[A-Z]{2}\b", inner):
        return title, ""                       # e.g. "(Relief Roster)"
    inner = re.sub(r",\s*[A-Z]\d[A-Z]\s*\d[A-Z]\d\s*$", "", inner)   # postal code
    return title[: m.start()].strip(), inner.strip()


def successfactors_site(label: str, host: str, locale: str):
    """
    Pull one public-sector site across every GOV_QUERIES term and merge.

    The RSS summary on these feeds is employment-equity boilerplate, so it
    carries no evidence of what the job is actually about. What DOES carry
    evidence is which of our search terms the site's own full-text search
    matched the posting on -- so those terms are recorded on the record and
    the agriculture gate judges the posting on them.
    """
    merged: dict[str, dict] = {}

    for keyword in GOV_QUERIES:
        url = f"https://{host}/services/rss/job/?locale={locale}"
        if keyword:
            url += f"&keywords=({_quote(keyword)})"
        body = _get(url)
        if not body:
            continue
        for e in feedparser.parse(body).entries:
            raw = _clean(e.get("title", ""))
            link = e.get("link", "")
            if not raw or not link:
                continue
            low = raw.lower()
            if any(m in low for m in _EMPTY_MARKERS):
                continue
            if _looks_french(raw):
                continue

            title, location = _sf_location(raw)
            rec = merged.get(link)
            if rec is None:
                rec = merged[link] = {
                    "title": title,
                    "org": label.split(" (")[0],
                    "location": location or "Canada",
                    "url": link,
                    "posted": _iso(e),
                    "summary": _clean(e.get("summary", ""))[:400],
                    "salary": "",
                    "source": label,
                    "_terms": set(),
                }
            if keyword:
                rec["_terms"].add(keyword)

    for rec in merged.values():
        terms = sorted(rec.pop("_terms"))
        if terms:
            rec["summary"] = (f"Matched the {rec['source']} job search for: "
                              f"{', '.join(terms)}. " + rec["summary"])
        yield rec


# --------------------------------------------------------------------------
# TASK LIST  --  every unit of work the scraper will run in parallel
# --------------------------------------------------------------------------
def build_tasks():
    """Returns [(label, callable), ...]"""
    tasks = []

    for board, base in MADGEX_BOARDS:
        for q in SEARCH_QUERIES:
            for page in range(1, MADGEX_PAGES + 1):
                tasks.append((f"{board}: {q} (p{page})",
                              lambda b=board, u=base, q=q, p=page: list(madgex(b, u, q, p))))

    for cid, cname in HEJ_CATEGORIES.items():
        tasks.append((f"HigherEdJobs: {cname}",
                      lambda c=cid, n=cname: list(higheredjobs(c, n))))

    # these two search a literal phrase -- give them the broad query set
    for q in BROAD_QUERIES:
        tasks.append((f"jobs.ac.uk: {q}", lambda q=q: list(jobs_ac_uk(q))))

    for q in BROAD_QUERIES:
        for page in range(0, EURAXESS_PAGES):
            tasks.append((f"EURAXESS: {q} (p{page + 1})",
                          lambda q=q, p=page: list(euraxess(q, p))))

    for q in SEARCH_QUERIES:
        tasks.append((f"jobRxiv: {q}", lambda q=q: list(jobrxiv(q))))

    for page in range(1, CAUT_PAGES + 1):
        tasks.append((f"CAUT Canada: page {page}", lambda p=page: list(caut(p))))

    for label, tenant, wd, site in WORKDAY_SITES:
        for off in range(0, WORKDAY_MAX, WORKDAY_PAGE):
            tasks.append((f"{label}: offset {off}",
                          lambda l=label, t=tenant, w=wd, s=site, o=off:
                          list(workday(l, t, w, s, o))))

    # one task per site -- it walks every GOV_QUERIES term itself so the
    # matched terms can be merged onto a single record per posting
    for label, host, locale in GOV_SF_SITES:
        tasks.append((f"{label}: all queries",
                      lambda l=label, h=host, lo=locale:
                      list(successfactors_site(l, h, lo))))

    return tasks


SOURCE_NAMES = ["CAUT (Canada)", "University portal (Canada)",
                "NRC (federal)", "Nova Scotia (provincial)",
                "Nature Careers", "Times Higher Education",
                "Chronicle of Higher Ed", "Inside Higher Ed", "HigherEdJobs",
                "jobs.ac.uk", "EURAXESS", "jobRxiv"]

# Sources that are Canadian public-sector employers
GOVERNMENT_SOURCES = {label for label, _, _ in GOV_SF_SITES}
