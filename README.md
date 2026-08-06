# Agriculture Jobs

A dashboard that searches academic and government job boards worldwide every
day, keeps only **agriculture** positions, and ranks each one against a
specific CV — with Canada and tenure-track roles first.

**Live site:** https://agtech223.github.io/Job-Dashboard/
*(enable it once — see [Hosting](#hosting-free-on-github-pages) below)*

---

## What it does

- Searches **10 job boards** — ~300 live queries, ~3,500 postings per run
- **Discards anything non-agricultural** — roughly 2,600 postings per run
- Scores the rest 0–100 against the CV and de-duplicates across boards
- Puts **Canada** and **faculty lines** first
- **Emails you** when a new Canadian agriculture position scores 60+
- Refreshes itself **every morning** via GitHub Actions — no server to run

---

## Running it on your own machine

**Double-click `START-DASHBOARD.bat`.** It installs the two dependencies on
first run, does a search, and opens the dashboard with a working
*Refresh from the web* button.

That is the only file at the top level. Everything else lives in `scripts/`:

| File | What it does |
|---|---|
| `START-DASHBOARD.bat` | **Opens the dashboard locally — this is the one you want** |
| `scripts/refresh-now.bat` | Runs a search (and the email alert) without opening the UI |
| `scripts/setup-daily-automation.bat` | Schedules a daily search *on this PC* at 07:30 |
| `scripts/remove-daily-automation.bat` | Removes that schedule |
| `scripts/push-to-github.bat` | Commits and publishes your changes to the live site |

You do not need the local schedule unless you want searches to run on this
machine — the GitHub Action already refreshes the live site every morning
whether the computer is on or not.

The hosted copy and the local copy are the **same page**. Served by
`engine/server.py` it talks to the live engine and can refresh on demand;
served as a static site it reads the daily snapshot and shows *Auto-daily*
instead of a refresh button.

---

## Sources

| Board | Coverage |
|---|---|
| **CAUT / AcademicWork.ca** | **Canada — the Canadian academic job board** |
| **University portals (Workday)** | **Canada — McGill, UBC, direct from the employer** |
| **NRC** | **Canada — National Research Council, federal** |
| **Nova Scotia** | **Canada — provincial public service** |
| jobs.ac.uk | UK + international |
| Nature Careers | Global, high-prestige research posts |
| Times Higher Education (unijobs) | Global |
| Chronicle of Higher Education | United States |
| Inside Higher Ed | United States |
| HigherEdJobs | United States, by discipline |
| EURAXESS | European Commission researcher portal |
| jobRxiv | Global research community board |

**University Affairs (universityaffairs.ca) cannot be included.** It sits behind
Cloudflare and returns HTTP 403 to every automated request — every path, both
domains, even `robots.txt`. CAUT covers the same market and is fully accessible.
Worth checking University Affairs by hand occasionally; the boards do not overlap
completely.

To add another Canadian university, find its careers URL of the shape
`https://<tenant>.<wdN>.myworkdayjobs.com/en-US/<site>` and add a line to
`WORKDAY_SITES` in `engine/sources.py`.

---

## Canadian government jobs

The **Government** view in the dashboard collects public-sector postings.

### What the radar pulls automatically

| Employer | How |
|---|---|
| **NRC** — National Research Council | SuccessFactors RSS |
| **Nova Scotia** — provincial public service | SuccessFactors RSS |

Both are queried across sixteen agriculture and science terms per run. Their
RSS summaries are employment-equity boilerplate with no description in them, so
the radar records **which of its search terms the employer's own full-text
search matched** and judges the posting on those. That is how NRC's *Computer
Specialist – Biostatistics* in **Saskatoon** — their crop-research centre —
surfaces at 60/100 despite a title that never says "agriculture".

### What cannot be automated, and what to do instead

**AAFC, CFIA, Natural Resources Canada, ECCC and most federal departments
recruit through GC Jobs (jobs.gc.ca), which cannot be scraped.** It is a
JavaScript application behind a session — no feed, no search form in the HTML,
no public API. I probed every entry point; none returns job data. Anything that
appeared to work would break silently within weeks, which is worse than not
having it.

**You were right that the account is the reliable route.** GC Jobs has a proper
Job Alert system, and it is the correct tool for federal postings. **I can't
create the account for you** — it needs your identity and credentials, and
creating accounts on your behalf is not something I'll do. It takes about three
minutes:

1. Go to **https://emploisfp-psjobs.cfp-psc.gc.ca** → *Create an account* (GC Key
   or Sign-In Partner).
2. Open **Job Alerts** → *Create a new job alert*.
3. Suggested criteria for your profile:
   - **Keywords:** `agriculture`, `agronomy`, `crop`, `soil`, `precision agriculture`,
     `remote sensing`, `geomatics`, `machine learning`, `research scientist`
   - **Job category:** *Scientific and Professional* (and *Engineering*)
   - **Classification:** `RES` (Research Scientist), `AG` (Agriculture),
     `EG` / `ENG` (Engineering), `PC` (Physical Sciences), `BI` (Biological Sciences)
   - **Location:** all of Canada, or the provinces you would move to
   - **Frequency:** daily
4. Do the same at **CFIA** and **AAFC** if you want department-specific alerts —
   both link out to GC Jobs.

Those alerts land in your inbox directly. The radar covers everything else.

### Provinces that cannot be scraped

**Alberta, Saskatchewan, Ontario, Manitoba, British Columbia, New Brunswick and
Quebec** all render their job lists in JavaScript — the served HTML contains no
postings. Reading them would need a headless browser on every run, which is too
slow and too brittle for a daily job. Nova Scotia is included because it happens
to expose a real feed.

If another province moves to SuccessFactors, adding it is one line in
`GOV_SF_SITES` (`engine/sources.py`) plus its label in `GOVERNMENT_SOURCES`
(`engine/profile.py`). Test the host first:

```
https://<host>/services/rss/job/?locale=en_US
```

If that returns RSS items, it will work.

---

## Agriculture is the requirement, not a preference

**A posting has to be about agriculture to appear at all.** AI, GIS, remote
sensing and robotics are the *tools you bring to* agriculture — they raise a
job's rank, but never qualify one on their own. "Assistant Professor in AI for
Medical Imaging" is a fine job and completely irrelevant here, so it is
**discarded**, not ranked low.

A posting clears the gate when **either** an agricultural term appears in its
**title**, or **two distinct** agricultural terms appear in its body. The
two-term rule matters: one stray "College of Agriculture" in an employer name is
not evidence that the *job* is agricultural.

Keyword clusters sit on one of three axes, set by the `axis` field in
`engine/profile.py`:

| Axis | Clusters | Role |
|---|---|---|
| **`ag`** | Precision Agriculture · Crop & Soil · Ag & Biosystems Engineering · Controlled Environment · Irrigation · Forestry · Food Systems | **the gate — required** |
| `tech` | AI/ML · Sensing & Remote Sensing · Robotics · Data Science | modifiers |
| `context` | Sustainability · Hydrology | minor |

### Scoring

```
score = 46% agriculture fit      <- the dominant term
      + 28% position-type fit
      + 12% technology fit
      + 14% breadth across your areas
      + 10 bonus points for the Ag x Tech intersection
```

Agriculture dominates, so a pure agricultural-engineering faculty line still
scores in the high 70s with no technology keywords at all. The Ag × Tech bonus is
what lifts *"AI for Agriculture"* and *"GIS and Remote Sensing of Cropping
Systems"* past 87.

Each card lists the **Agriculture** terms and the **Tools** terms it matched on
separate rows, so you can always see why it scored what it did.

---

## Priority: Canada and faculty lines

| Tier | What it is |
|---|---|
| 1 | 🍁 Canada · faculty line — first, with a coloured edge |
| 2 | 🍁 Canada · any other role |
| 3 | Faculty line elsewhere |
| 4 | Everything else |

"Faculty line" means **Tenure-Track Faculty** (Assistant Professor),
Professor/Senior Faculty, Lecturer/Teaching Faculty, or Department Head/Chair.
Postdocs, research staff, adjunct pools and studentships are not faculty lines.

Nothing is hidden — everything else stays visible underneath. Priority changes
the **order only**; it never touches the match score.

---

## Email alerts

`engine/notify.py` emails you the first time a posting satisfies every rule in
`engine/profile.py`:

```python
ALERT_COUNTRIES       = ("Canada",)   # () for anywhere
ALERT_MIN_SCORE       = 60
ALERT_REQUIRE_FACULTY = False         # True = professor/lecturer/chair only
```

Agriculture is implied — non-agricultural postings never get that far. Alerted
postings are recorded in `docs/data/alerted.json`, so nothing is emailed twice.

### Setting it up (one time, ~3 minutes)

Credentials never live in the repo. They go in **GitHub → your repo → Settings →
Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `MAIL_USERNAME` | the Gmail address that sends the alert |
| `MAIL_PASSWORD` | a Google **App Password** (16 characters) — *not* your Gmail password |
| `MAIL_TO` | where the alert goes |
| `MAIL_SERVER` | *optional*, defaults to `smtp.gmail.com` |
| `MAIL_PORT` | *optional*, defaults to `465` |

To create the App Password: Google Account → **Security** → turn on
**2-Step Verification** → **App passwords** → generate one for "Mail". Google
does not allow SMTP with a normal account password.

Until those secrets exist the workflow still runs and publishes data — it just
prints "Mail credentials not set" and skips the email.

---

## Hosting (free, on GitHub Pages)

The daily GitHub Action commits a fresh `docs/data/jobs.json`, and GitHub Pages
serves `docs/` as a static site. No server, no cost.

### Three one-time steps

**1. Turn on Pages** — repo → **Settings** → **Pages** → *Source:* **Deploy from
a branch** → branch **`main`**, folder **`/docs`** → **Save**. A minute later the
dashboard is live at `https://agtech223.github.io/Job-Dashboard/`.

**2. Add the mail secrets** so the alerts can send — see
[Email alerts](#email-alerts) above.

The daily workflow (`.github/workflows/refresh.yml`) is already installed and
runs on `cron: "30 10 * * *"` — 07:30 Atlantic. You can also run it on demand
from the **Actions** tab → *Refresh job radar* → **Run workflow**.

`scripts/push-to-github.bat` commits and publishes any later changes using the
token in `gh.txt.txt` — that file is git-ignored and never leaves your machine.

---

## Repository layout

```
.
├── .github/workflows/refresh.yml   daily search + email + publish
├── docs/                           the site GitHub Pages serves
│   ├── index.html                  the dashboard (local + hosted)
│   └── data/
│       ├── jobs.json               published snapshot
│       ├── seen.json               first-seen dates, for NEW badges
│       └── alerted.json            what has already been emailed
├── engine/
│   ├── profile.py                  the CV as search rules  <- edit this
│   ├── sources.py                  the ten job-board adapters
│   ├── matcher.py                  scoring, agriculture gate, geography
│   ├── scraper.py                  runs every source in parallel
│   ├── notify.py                   email alerts
│   └── server.py                   local server + live refresh API
├── scripts/                        refresh · schedule · publish helpers
├── START-DASHBOARD.bat             the one you double-click
└── requirements.txt
```

`engine/data/` (local run logs, saved/applied marks) and the CV PDF are
git-ignored. **This repository is public**, and the CV carries a personal phone
number, private email addresses and the contact details of six referees — so it
stays on your machine. `engine/profile.py` already holds everything the matcher
needs from it.

---

## Tuning

Everything worth changing is in **`engine/profile.py`**:

| Setting | Controls |
|---|---|
| `SEARCH_QUERIES` / `BROAD_QUERIES` | what gets asked of the job boards |
| `KEYWORD_GROUPS` | which terms match, their axis and weight |
| `REQUIRE_AGRICULTURE` | the agriculture gate — `False` ranks everything |
| `AG_MIN_BODY_TERMS` | body evidence needed without a title hit |
| `ROLE_FIT` | what each kind of position is worth |
| `PRIORITY_COUNTRIES` | which countries sort to the top |
| `ALERT_*` | when you get an email |
| `SCORE_FLOOR` / `MAX_AGE_DAYS` | what is kept, and for how long |

Save and press **Refresh** — no restart needed.

---

## Notes on reliability

- **Sources fail sometimes.** When one does, its postings are **carried forward
  from the previous run** rather than vanishing, and re-scored from scratch each
  time. Anything not re-seen anywhere for 10 days drops off as closed.
- **HigherEdJobs is behind Imperva.** The engine asks it for only six discipline
  feeds, four seconds apart. If it blocks anyway, carry-over covers it.
- **De-duplication.** The same job is often on three boards. The best-scoring
  copy is kept and the others noted as `+1`, `+2` on the source tag.
- **Country detection is strict by design.** Every rule is word-boundary
  anchored and a two-letter code is never matched as a bare lower-case
  substring — that mistake turns "L**on**don" into Ontario, "Edi**nb**urgh" into
  New Brunswick and "Im**pe**rial" into Prince Edward Island. Bracketed codes are
  only trusted at the end of a field, because "Tenure Track (BC)" means
  Bakersfield College, not British Columbia. Genuinely ambiguous cities (London,
  Cambridge, Waterloo, Hamilton, Kingston, Victoria, Sydney, Truro) need a second
  signal rather than a guess.

Requires Python 3.9+ with `requests` and `feedparser`.
