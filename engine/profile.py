# -*- coding: utf-8 -*-
"""
CANDIDATE PROFILE  --  derived from CV_Hassan_Afzaal_2026.pdf
================================================================
This is the ONLY file you need to edit to re-tune the job search.

  * SEARCH_QUERIES   -> what gets asked of each job board
  * KEYWORD_GROUPS   -> what counts as a good match, and how much
  * ROLE_FIT         -> how much each kind of position is worth to you
  * NEGATIVE_*       -> what to push down / throw away
  * SCORE_FLOOR      -> jobs below this score are not stored

Everything else (scraper, matcher, server, dashboard) reads from here.
"""

CANDIDATE = {
    "name": "Hassan Afzaal, PhD",
    "headline": "Agricultural Engineer | AI, Computer Vision & Precision Agriculture",
    "degree": "PhD Sustainable Design Engineering, University of Prince Edward Island (2026)",
    "metrics": {"publications": 26, "citations": "1,200+", "h_index": 14, "i10_index": 16},
    "awards": [
        "Governor General's Gold Medal (Graduate), 2026",
        "NSERC Canada Postdoctoral Research Award (CPRA), 2025",
        "NSERC Canada Graduate Scholarship (CGS), 2023",
    ],
    "email": "hafzaal@uoguelph.ca",
}

# ---------------------------------------------------------------------------
# 1. WHAT WE ASK THE JOB BOARDS FOR
#    Keep these broad -- the matcher below does the precision work.
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    "precision agriculture",
    "digital agriculture",
    "agricultural engineering",
    "biosystems engineering",
    "smart farming",
    "agricultural robotics",
    "machine learning agriculture",
    "computer vision agriculture",
    "artificial intelligence agriculture",
    "remote sensing",
    "plant phenotyping",
    "controlled environment agriculture",
    "irrigation water management",
    "agronomy crop science",
    "soil science",
    "geospatial data science",
    "agricultural technology",
    "food security sustainability",
]

# Boards that search a literal phrase (jobs.ac.uk, EURAXESS) return almost
# nothing for long phrases, so they get a broader, single-concept query set.
BROAD_QUERIES = [
    "agriculture", "agricultural engineering", "crop science", "soil science",
    "precision agriculture", "horticulture", "plant science", "remote sensing",
    "machine learning", "artificial intelligence", "computer vision", "robotics",
    "phenotyping", "irrigation", "geospatial", "sustainable agriculture",
    "food security", "environmental engineering", "agri-food", "digital agriculture",
]

# Canadian government career sites return only ~20 items per query, so they get
# a short, high-signal list aimed at the science and engineering streams that
# match the CV (NRC research officer, provincial agrologist / specialist roles).
GOV_QUERIES = [
    "",                       # everything currently open -- the safety net
    "agriculture",
    "agronomy",
    "crop",
    "soil",
    "plant",
    "food",
    "research scientist",
    "research officer",
    "remote sensing",
    "geomatics",
    "machine learning",
    "engineer",
    "environment",
    "forestry",
    "water",
]

# ---------------------------------------------------------------------------
# 2. WHAT COUNTS AS A MATCH
#
#    Every cluster sits on one of three axes:
#
#      "ag"      the subject matter -- AGRICULTURE. This is a HARD REQUIREMENT:
#                a posting with no agricultural evidence is discarded outright,
#                however good its technology looks. See REQUIRE_AGRICULTURE.
#      "tech"    the tools you bring TO agriculture -- AI, GIS/remote sensing,
#                robotics, data science. These modify the score; they can never
#                qualify a job on their own.
#      "context" supporting themes that add a little, but decide nothing.
#
#    weight = how central the cluster is to the CV.
#    A hit in the JOB TITLE is worth TITLE_MULTIPLIER x a hit in the body.
# ---------------------------------------------------------------------------
TITLE_MULTIPLIER = 2.6

KEYWORD_GROUPS = {
    # ---------------- AGRICULTURE (the gate) ------------------------------
    "Precision Agriculture": {
        "axis": "ag",
        "weight": 11,
        "terms": [
            "precision agriculture", "precision farming", "digital agriculture",
            "smart farming", "smart agriculture", "variable rate", "variable-rate",
            "site specific", "site-specific", "precision livestock", "agtech",
            "ag-tech", "agricultural technology", "digital farming", "crop scouting",
            "precision crop", "precision horticulture", "controlled traffic",
        ],
    },
    "Agriculture, Crop & Soil Science": {
        "axis": "ag",
        "weight": 9,
        "terms": [
            # generic domain anchors -- these are what make a posting agricultural
            "agricultur", "farming", "farm ", "agrifood", "agri-food", "agroecolog",
            "agronom", "crop", "horticultur", "livestock", "rural development",
            "soil", "plant science", "plant produc", "plant patholog",
            "plant breeding", "plant stress", "cropping system", "agrarian",
            # specifics from the CV
            "crop science", "crop production", "crop protection", "soil health",
            "potato", "weed science", "entomolog", "yield prediction",
            "grain", "forage", "pasture", "rangeland", "orchard", "vineyard",
            "viticultur", "turfgrass", "tillage", "fertilizer", "fertiliser",
            "pesticide", "herbicide", "dairy", "poultry", "aquaculture",
            # animal science is a core agriculture discipline -- every ag
            # faculty has it. Bare "animal" is deliberately NOT here: it would
            # pull in lab-animal and shelter roles that are not agricultural.
            "animal science", "animal bioscience", "animal physiolog",
            "animal nutrition", "animal breeding", "animal welfare",
            "animal product",
            "post-harvest", "postharvest", "seed technolog", "seed produc",
        ],
    },
    "Agricultural / Biosystems Engineering": {
        "axis": "ag",
        "weight": 11,
        "terms": [
            "agricultural engineering", "biosystems engineering",
            "biological engineering", "bioresource engineering",
            "agricultural and biological", "biosystems", "agricultural machinery",
            "farm machinery", "mechanization", "mechanisation",
            "agricultural automation", "sustainable design engineering",
            "food engineering", "postharvest engineering",
        ],
    },
    "Controlled Environment": {
        "axis": "ag",
        "weight": 9,
        "terms": [
            "controlled environment", "greenhouse", "growth chamber",
            "vertical farming", "plant factory", "indoor farming", "hydroponic",
            "aquaponic", "protected cultivation", "cea ", "glasshouse",
            "nursery production",
        ],
    },
    "Irrigation & Agricultural Water": {
        "axis": "ag",
        "weight": 8,
        "terms": [
            "irrigat", "evapotranspiration", "soil moisture", "water management",
            "agricultural water", "drainage", "water productivity",
            "water budgeting", "fertigation", "drip system",
        ],
    },
    "Forestry & Agroforestry": {
        "axis": "ag",
        "weight": 6,
        "terms": [
            "agroforestry", "forestry", "silvicultur", "tree crop",
            "plantation management",
        ],
    },
    "Food Systems & Security": {
        "axis": "ag",
        "weight": 7,
        "terms": [
            "food security", "food system", "food production", "food science",
            "sustainable agriculture", "climate smart agricultur",
            "climate-smart agricultur", "regenerative agricultur",
        ],
    },

    # ---------------- TECHNOLOGY (the modifiers) --------------------------
    "AI / Machine Learning": {
        "axis": "tech",
        "weight": 9,
        "terms": [
            "machine learning", "deep learning", "artificial intelligence",
            "computer vision", "machine vision", "neural network", "convolutional",
            "vision transformer", "image analysis", "image processing",
            "semantic segmentation", "object detection", "data-driven modeling",
            "generative", "foundation model", "predictive model", "ai", "ai-driven",
            "ai-enabled", "ml models",
        ],
    },
    "Sensing & Remote Sensing": {
        "axis": "tech",
        "weight": 9,
        "terms": [
            "remote sensing", "uav", "drone", "unmanned aerial", "hyperspectral",
            "multispectral", "ndvi", "lidar", "photogrammetry", "geospatial",
            "gis", "satellite imagery", "earth observation", "proximal sensing",
            "sensor", "sensing technolog", "imaging", "phenotyping", "phenomics",
            "rtk", "gnss", "geomatics", "spatial analysis",
        ],
    },
    "Robotics & Automation": {
        "axis": "tech",
        "weight": 7,
        "terms": [
            "robotic", "robotics", "autonomous system", "automation", "mechatronic",
            "internet of things", "iot", "embedded system", "edge computing",
            "control system", "actuator", "cyber-physical",
        ],
    },
    "Data Science & Modelling": {
        "axis": "tech",
        "weight": 6,
        "terms": [
            "data science", "data analytics", "big data", "statistical modeling",
            "statistical modelling", "time series", "simulation model",
            "decision support", "digital twin", "modeling framework",
            "geostatistic",
        ],
    },

    # ---------------- CONTEXT (adds a little, decides nothing) ------------
    "Sustainability & Climate": {
        "axis": "context",
        "weight": 4,
        "terms": [
            "climate smart", "climate-smart", "climate change", "carbon",
            "greenhouse gas", "environmental sustainability", "circular economy",
            "sustainability", "life cycle assessment", "bioeconomy",
        ],
    },
    "Hydrology & Environment": {
        "axis": "context",
        "weight": 4,
        "terms": [
            "hydrolog", "watershed", "water resources", "groundwater",
            "environmental modeling", "environmental modelling", "ecosystem service",
        ],
    },
}

# ---------------------------------------------------------------------------
# 3. HOW MUCH EACH KIND OF ROLE IS WORTH  (0.0 - 1.0)
#    Primary target = permanent faculty. Postdocs still surface (CPRA holder)
#    but rank below a tenure-track line.
# ---------------------------------------------------------------------------
ROLE_FIT = {
    "Tenure-Track Faculty": 1.00,
    "Professor / Senior Faculty": 0.96,
    "Lecturer / Teaching Faculty": 0.86,
    "Research Scientist": 0.74,
    "Postdoctoral": 0.70,
    "Research Fellow": 0.72,
    "Department Head / Chair": 0.80,
    "Adjunct / Faculty Pool": 0.26,
    "PhD Studentship": 0.10,
    "Other Academic": 0.34,
    "Non-Academic": 0.12,
}

# Patterns are checked IN ORDER -- first match wins.
ROLE_PATTERNS = [
    ("PhD Studentship", ["phd student", "phd position", "doctoral student",
                         "phd studentship", "phd scholarship", "graduate assistantship",
                         "phd researcher", "doctoral candidate", "phd fellow"]),
    # checked before the faculty patterns -- an "adjunct pool" posting is not a line
    ("Adjunct / Faculty Pool", ["adjunct", "faculty pool", "applicant pool",
                                "instructor pool", "lecturer pool",
                                "part-time faculty", "part time faculty",
                                "part-time instructor", "part time instructor",
                                "temporary faculty", "casual academic",
                                "sessional", "per course"]),
    ("Tenure-Track Faculty", ["tenure track", "tenure-track", "assistant professor",
                              "tenure system", "tenured or tenure",
                              "open rank", "open-rank"]),
    ("Department Head / Chair", ["department head", "head of department", "department chair",
                                 "dean of", "chair of the department", "professor and head",
                                 "director of the school"]),
    # NB: keep every entry here at least two words. Punctuation is folded to
    # spaces before matching, so a one-word entry like "professor," would
    # collapse to "professor" and swallow every rank above.
    ("Professor / Senior Faculty", ["associate professor", "full professor", "professorship",
                                    "professor of", "professor in", "chair in", "w2 professor",
                                    "w3 professor", "reader in"]),
    ("Lecturer / Teaching Faculty", ["lecturer", "senior lecturer", "teaching fellow",
                                     "instructor", "teaching professor", "faculty position",
                                     "faculty member", "adjunct"]),
    ("Postdoctoral", ["postdoctoral", "post-doctoral", "postdoc", "post doc"]),
    ("Research Fellow", ["research fellow", "research associate", "senior researcher",
                         "research officer"]),
    ("Research Scientist", ["research scientist", "scientist", "staff scientist",
                            "research engineer", "principal investigator"]),
]

# A "faculty line" -- a real academic appointment, as opposed to a postdoc,
# a research-staff post, an adjunct pool or a studentship. Assistant Professor
# (tenure-track) is the primary target and sits at the top of this set.
FACULTY_ROLES = {"Tenure-Track Faculty", "Professor / Senior Faculty",
                 "Lecturer / Teaching Faculty", "Department Head / Chair"}

# ---------------------------------------------------------------------------
# PRIORITY -- what the dashboard puts first by default
# ---------------------------------------------------------------------------
# Canada is the target market; a tenure-track faculty line is the target role.
# These do NOT change a job's match score (that stays an honest measure of CV
# fit) -- they set the default ORDER, so priority jobs sit at the top and
# everything else remains visible underneath.
PRIORITY_COUNTRIES = ("Canada",)

PRIORITY_TIERS = [
    (0, "Canada · faculty line"),
    (1, "Canada · other role"),
    (2, "Elsewhere · faculty line"),
    (3, "Elsewhere · other role"),
]

# ---------------------------------------------------------------------------
# EMAIL ALERTS  (engine/notify.py)
# ---------------------------------------------------------------------------
# A posting triggers one email the first time it satisfies ALL of these.
# Agriculture is implied -- non-agricultural postings never get this far.
GOVERNMENT_SOURCES = ("NRC (federal)", "Nova Scotia (provincial)")

# Canadian universities scraped directly from their own careers portal.
# Everything posted here is by definition a Canadian position.
CANADIAN_UNIVERSITY_SOURCES = (
    "University of Guelph",
    "University of Toronto",
    "University of Ottawa",
    "McGill University",
    "University of British Columbia",
    "Dalhousie University",
)

ALERT_COUNTRIES = ("Canada",)      # () for anywhere in the world
ALERT_MIN_SCORE = 60               # match score out of 100
ALERT_REQUIRE_FACULTY = False      # True = only professor/lecturer/chair lines
                                   # (leave False to also hear about postdocs
                                   #  and research scientist posts in Canada)

# ---------------------------------------------------------------------------
# 4. NOISE CONTROL
# ---------------------------------------------------------------------------
# In the TITLE -> heavy penalty (these are almost never relevant)
NEGATIVE_TITLE = [
    "nursing", "nurse", "athletic", "coach", "basketball", "football", "soccer",
    "admissions counselor", "development officer", "custodian", "groundskeeper",
    "dining", "cafeteria", "police officer", "security officer", "bus driver",
    "accountant", "accounting", "payroll", "human resources", "hr generalist",
    "theology", "divinity", "chaplain", "dental", "dentistry", "pharmacy",
    "veterinary technician", "social work", "counseling", "counselor",
    "music", "dance", "theatre", "theater", "art history", "philosophy",
    "spanish", "french language", "english composition", "creative writing",
    "law school", "paralegal", "criminal justice", "cosmetology", "welding",
    "hvac", "plumbing", "phlebotomy", "radiologic", "sonography", "midwif",
    "marketing manager", "sales", "recruiter", "advancement", "alumni",
    "registrar", "bursar", "financial aid", "student affairs", "residence life",
]

# Anywhere -> mild penalty
NEGATIVE_BODY = [
    "part-time only", "volunteer position", "unpaid",
]

# A job must contain at least ONE of these to be considered academic/research
# (guards against generic corporate listings leaking in from broad feeds).
ACADEMIC_SIGNALS = [
    "professor", "faculty", "lecturer", "postdoc", "post-doc", "research",
    "university", "college", "institute", "academic", "phd", "doctoral",
    "school of", "department of", "laborator", "scientist", "fellow",
    "tenure", "teaching", "campus", "scholar",
]

# ---------------------------------------------------------------------------
# 5. SCORING WEIGHTS + CUTOFF
# ---------------------------------------------------------------------------
WEIGHTS = {
    "ag": 0.46,       # how agricultural the posting is  <- the dominant term
    "role": 0.28,     # how well the position type matches the goal
    "tech": 0.12,     # how much of your toolkit it asks for
    "breadth": 0.14,  # how many distinct CV areas it touches
}

# Saturation constants: raw weighted hits -> 0..1 curve.
AG_SATURATION = 18.0
TECH_SATURATION = 16.0

# ---------------------------------------------------------------------------
# THE AGRICULTURE GATE
# ---------------------------------------------------------------------------
# Agriculture is the subject; AI, GIS, remote sensing and robotics are the
# tools. A posting has to be about agriculture to be worth seeing at all --
# "Assistant Professor in AI for Medical Imaging" is a fine job and completely
# irrelevant here, so it is discarded rather than ranked low.
#
# A posting clears the gate when EITHER:
#   * an agricultural term appears in its TITLE, or
#   * at least AG_MIN_BODY_TERMS distinct agricultural terms appear in the body.
#
# The two-term body rule matters: a single stray "College of Agriculture" in an
# employer name is not evidence that the JOB is agricultural.
#
# Set REQUIRE_AGRICULTURE = False to go back to ranking everything.
REQUIRE_AGRICULTURE = True
AG_MIN_BODY_TERMS = 2

# ---------------------------------------------------------------------------
# THE CV-DISCIPLINE PATHWAY  (the one documented exception to the gate)
# ---------------------------------------------------------------------------
# Agriculture stays the rule, but a handful of disciplines ARE the CV and are
# inherently land, earth and environment facing -- close enough to agriculture
# to be worth seeing even when the advert never says the word. "Assistant
# Professor in GeoAI" or "...in Geomatics" is such a job. "Assistant Professor
# in AI for Medical Imaging" is not, because medical imaging appears on neither
# list, and that is exactly the separation this list has to hold.
#
# TITLE ONLY, deliberately. An incidental "remote sensing" buried in a long
# advert is not evidence that the JOB is about remote sensing; naming it in the
# title is. Keep this list short -- every entry widens the gate.
CORE_DISCIPLINES = [
    "geomatics", "geoai", "geo-ai", "geospatial", "geographic information",
    "remote sensing", "earth observation", "photogrammetry", "lidar",
    "spatial data science", "spatial analysis", "spatial statistics",
    "land use", "land cover", "terrain analysis", "digital earth",
    "phenotyping", "phenomics", "evapotranspiration", "hydrolog", "watershed",
    "unmanned aerial", "uav", "agroclimat", "environmental sensing",
]

# A posting admitted this way has no agricultural evidence, so it cannot be
# scored on one. It is credited half an agriculture score instead: enough to
# rank alongside the Canadian faculty cluster, not enough to outrank a genuine
# agricultural match of the same seniority.
CORE_DISCIPLINE_AG_CREDIT = 0.50

# THE SIGNATURE BONUS ---------------------------------------------------------
# Hassan's niche is not "agriculture" and not "AI" -- it is the intersection.
# A posting that lands in BOTH halves is the thing worth applying to, so it
# earns the final 10 points outright. This is what separates
# "Assistant Professor of AI for Agriculture" from a generic embedded-systems
# lectureship that happens to share a keyword.
# Derived from the "axis" field above -- edit the groups, not these.
AG_GROUPS = {g for g, c in KEYWORD_GROUPS.items() if c["axis"] == "ag"}
TECH_GROUPS = {g for g, c in KEYWORD_GROUPS.items() if c["axis"] == "tech"}
CONTEXT_GROUPS = {g for g, c in KEYWORD_GROUPS.items() if c["axis"] == "context"}
SYNERGY_BONUS = 10.0
BREADTH_TARGET = 4          # matching 4 distinct areas = full breadth credit

SCORE_FLOOR = 22          # below this, the job is discarded entirely
STRONG_MATCH = 70         # "strong match" badge in the dashboard
GOOD_MATCH = 50           # "good match" badge

# How many days a posting stays in the dashboard before it is retired
MAX_AGE_DAYS = 120
