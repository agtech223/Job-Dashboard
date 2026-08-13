# -*- coding: utf-8 -*-
"""
CV MATCHING ENGINE
==================
Turns a raw posting into a scored, classified, de-duplicated record.

score = 100 * (0.50 * domain + 0.30 * role_fit + 0.20 * breadth)

  domain   saturating sum of weighted keyword hits (title hits count 2.6x)
  role_fit how much that kind of position is worth (profile.ROLE_FIT)
  breadth  how many distinct CV areas the posting touches

The matched keywords are kept on the record so the dashboard can SHOW why
a job scored what it did.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone

from profile import (ACADEMIC_SIGNALS, AG_GROUPS, AG_MIN_BODY_TERMS,
                     CANADIAN_UNIVERSITY_SOURCES, CORE_DISCIPLINES,
                     CORE_DISCIPLINE_AG_CREDIT, GOVERNMENT_SOURCES,
                     AG_SATURATION, BREADTH_TARGET, FACULTY_ROLES,
                     KEYWORD_GROUPS, NEGATIVE_BODY, NEGATIVE_TITLE,
                     PRIORITY_COUNTRIES, REQUIRE_AGRICULTURE, ROLE_FIT,
                     ROLE_PATTERNS, SYNERGY_BONUS, TECH_GROUPS,
                     TECH_SATURATION, TITLE_MULTIPLIER, WEIGHTS)

# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
ISO = {
    "US": "United States", "CA": "Canada", "GB": "United Kingdom", "UK": "United Kingdom",
    "AU": "Australia", "NZ": "New Zealand", "IE": "Ireland", "DE": "Germany",
    "FR": "France", "NL": "Netherlands", "BE": "Belgium", "CH": "Switzerland",
    "AT": "Austria", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
    "ES": "Spain", "IT": "Italy", "PT": "Portugal", "PL": "Poland", "CZ": "Czechia",
    "GR": "Greece", "HU": "Hungary", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia",
    "HR": "Croatia", "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania", "IS": "Iceland",
    "LU": "Luxembourg", "CY": "Cyprus", "MT": "Malta", "BG": "Bulgaria", "RS": "Serbia",
    "CN": "China", "JP": "Japan", "KR": "South Korea", "SG": "Singapore", "HK": "Hong Kong",
    "IN": "India", "MY": "Malaysia", "TH": "Thailand", "TW": "Taiwan", "VN": "Vietnam",
    "ID": "Indonesia", "PH": "Philippines", "PK": "Pakistan", "BD": "Bangladesh",
    "AE": "United Arab Emirates", "SA": "Saudi Arabia", "QA": "Qatar", "KW": "Kuwait",
    "OM": "Oman", "BH": "Bahrain", "IL": "Israel", "TR": "Turkey", "JO": "Jordan",
    "LB": "Lebanon", "EG": "Egypt", "MA": "Morocco", "ZA": "South Africa",
    "KE": "Kenya", "NG": "Nigeria", "GH": "Ghana", "ET": "Ethiopia", "TZ": "Tanzania",
    "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "PE": "Peru", "UY": "Uruguay", "CR": "Costa Rica",
}
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR",
}
US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "west virginia", "wisconsin", "wyoming",
}

# Canadian provinces: full names, plus the postal codes which are ONLY ever
# matched as upper-case tokens after a comma. Matching "ON"/"NB"/"PE" as bare
# lower-case substrings turns "London" into Ontario, "Edinburgh" into New
# Brunswick and "Imperial" into Prince Edward Island -- do not do it.
CA_PROVINCE_NAMES = {
    "ontario", "quebec", "québec", "british columbia", "alberta", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick", "newfoundland and labrador",
    "newfoundland", "prince edward island", "yukon", "nunavut",
    "northwest territories",
}
CA_PROVINCE_CODES = {"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE",
                     "YT", "NT", "NU"}

# ---------------------------------------------------------------------------
# City gazetteer. Location fields from these boards are usually a bare city
# name, so this carries most of the weight.
# ---------------------------------------------------------------------------
CITIES = {
    "Canada": {
        "toronto", "montreal", "montréal", "vancouver", "ottawa", "calgary",
        "edmonton", "winnipeg", "halifax", "saskatoon", "regina", "guelph",
        "kitchener", "burnaby", "mississauga", "brampton", "oshawa", "sudbury",
        "thunder bay", "charlottetown", "fredericton", "moncton", "sherbrooke",
        "trois-rivières", "trois-rivieres", "gatineau", "kelowna", "kamloops",
        "nanaimo", "prince george", "lethbridge", "red deer", "brandon",
        "antigonish", "wolfville", "sackville", "corner brook", "peterborough",
        "barrie", "whitehorse", "yellowknife", "iqaluit", "st. john's",
        "st johns", "quebec city", "québec city", "chicoutimi", "rimouski",
        "abbotsford", "chilliwack", "vernon", "penticton", "courtenay",
        "st. catharines", "st catharines", "sault ste. marie", "north bay",
        "timmins", "kingsville", "leamington", "truro, ns", "wilfrid laurier",
    },
    "United Kingdom": {
        "edinburgh", "glasgow", "manchester", "birmingham", "leeds", "bristol",
        "oxford", "nottingham", "sheffield", "liverpool", "cardiff", "belfast",
        "aberdeen", "dundee", "exeter", "norwich", "reading", "southampton",
        "newcastle", "coventry", "leicester", "bath", "lancaster", "guildford",
        "brighton", "colchester", "loughborough", "swansea", "aberystwyth",
        "st andrews", "stirling", "hatfield", "milton keynes", "egham",
        "uxbridge", "cranfield", "falmer", "keele", "preston", "plymouth",
        "portsmouth", "salford", "bradford", "hull", "middlesbrough",
        "sunderland", "wolverhampton", "chester", "bedford", "luton",
        "chelmsford", "ipswich", "northampton", "worcester", "gloucester",
        "cheltenham", "winchester", "bournemouth", "poole", "carlisle",
        "huddersfield", "wakefield", "doncaster", "harpenden", "bracknell",
        "scotland", "wales", "england", "northern ireland", "great britain",
        "hertfordshire", "oxfordshire", "cambridgeshire", "yorkshire",
        "midlands", "tyne and wear", "berkshire", "hampshire",
    },
    "Ireland": {"dublin", "cork", "galway", "limerick", "maynooth", "belfield"},
    "Australia": {"sydney", "melbourne", "brisbane", "perth", "adelaide",
                  "canberra", "hobart", "darwin", "wollongong", "newcastle nsw",
                  "townsville", "toowoomba", "armidale", "bendigo", "geelong",
                  "gold coast", "nsw", "queensland", "victoria, australia"},
    "New Zealand": {"auckland", "wellington", "christchurch", "dunedin",
                    "palmerston north", "hamilton nz", "lincoln nz"},
    "China": {"beijing", "shanghai", "shenzhen", "guangzhou", "hangzhou",
              "nanjing", "wuhan", "chengdu", "xi'an", "xian", "suzhou",
              "tianjin", "qingdao", "hainan", "harbin", "chongqing", "macao",
              "macau", "zhejiang", "jiangsu", "shandong", "guangdong"},
    "Hong Kong": {"hong kong", "kowloon", "sha tin", "clear water bay"},
    "Singapore": {"singapore", "nanyang", "jurong"},
    "Japan": {"tokyo", "kyoto", "osaka", "sendai", "tsukuba", "fukuoka",
              "nagoya", "sapporo", "okinawa"},
    "South Korea": {"seoul", "busan", "daejeon", "daegu", "gwangju", "pohang"},
    "Netherlands": {"amsterdam", "wageningen", "utrecht", "delft", "leiden",
                    "rotterdam", "groningen", "eindhoven", "nijmegen",
                    "maastricht", "enschede", "tilburg"},
    "Germany": {"berlin", "munich", "münchen", "hamburg", "cologne", "köln",
                "frankfurt", "stuttgart", "heidelberg", "bonn", "göttingen",
                "goettingen", "leipzig", "dresden", "freiburg", "tübingen",
                "tuebingen", "aachen", "karlsruhe", "hohenheim", "potsdam",
                "jena", "kiel", "bremen", "hannover", "münster", "muenster"},
    "France": {"paris", "lyon", "toulouse", "montpellier", "grenoble",
               "marseille", "bordeaux", "nantes", "rennes", "strasbourg",
               "lille", "nice", "dijon", "clermont-ferrand", "avignon",
               "haute-garonne", "versailles", "orsay", "palaiseau"},
    "Switzerland": {"zurich", "zürich", "geneva", "genève", "lausanne", "basel",
                    "bern", "lugano", "st. gallen", "eth"},
    "Belgium": {"leuven", "ghent", "gent", "brussels", "antwerp", "liège",
                "liege", "louvain-la-neuve"},
    "Denmark": {"copenhagen", "københavn", "aarhus", "odense", "aalborg",
                "lyngby", "roskilde", "foulum"},
    "Sweden": {"stockholm", "uppsala", "lund", "gothenburg", "göteborg",
               "umeå", "umea", "linköping", "linkoping", "alnarp"},
    "Norway": {"oslo", "bergen", "trondheim", "tromsø", "tromso", "ås", "aas"},
    "Finland": {"helsinki", "espoo", "tampere", "turku", "oulu", "jyväskylä",
                "kuopio", "joensuu"},
    "Austria": {"vienna", "wien", "graz", "innsbruck", "salzburg", "linz",
                "klosterneuburg", "tulln"},
    "Spain": {"madrid", "barcelona", "valencia", "seville", "sevilla",
              "zaragoza", "granada", "córdoba", "cordoba", "pamplona",
              "santiago de compostela", "bilbao", "murcia", "lleida"},
    "Italy": {"rome", "roma", "milan", "milano", "bologna", "turin", "torino",
              "padua", "padova", "florence", "firenze", "naples", "napoli",
              "pisa", "trento", "udine", "bari", "catania", "piacenza"},
    "Portugal": {"lisbon", "lisboa", "porto", "coimbra", "braga", "aveiro",
                 "évora", "evora"},
    "Poland": {"warsaw", "warszawa", "krakow", "kraków", "poznan", "poznań",
               "wroclaw", "wrocław", "gdansk", "gdańsk", "lublin"},
    "Czechia": {"prague", "praha", "brno", "olomouc", "ceske budejovice"},
    "Israel": {"jerusalem", "tel aviv", "haifa", "rehovot", "beer sheva",
               "be'er sheva"},
    "United Arab Emirates": {"abu dhabi", "dubai", "sharjah", "al ain",
                             "masdar", "ras al khaimah"},
    "Saudi Arabia": {"riyadh", "jeddah", "thuwal", "dhahran", "kaust"},
    "Qatar": {"doha", "education city"},
    "Morocco": {"benguerir", "rabat", "casablanca", "marrakech", "ifrane"},
    "South Africa": {"cape town", "johannesburg", "pretoria", "stellenbosch",
                     "durban", "bloemfontein", "potchefstroom"},
    "India": {"new delhi", "mumbai", "bangalore", "bengaluru", "chennai",
              "kanpur", "kharagpur", "hyderabad", "pune", "guwahati", "roorkee"},
    "Brazil": {"sao paulo", "são paulo", "rio de janeiro", "campinas",
               "piracicaba", "vicosa", "viçosa", "porto alegre", "brasilia"},
}

# Cities that exist in more than one country. They only resolve when a
# co-signal is present; otherwise they fall through to the next rule rather
# than guessing.
AMBIGUOUS_CITIES = {
    "london":     [("Canada", ("ontario", " on", "western university", "uwo",
                               "fanshawe")), ("United Kingdom", ())],
    "cambridge":  [("United States", ("massachusetts", " ma", "mit", "harvard")),
                   ("Canada", ("ontario",)), ("United Kingdom", ())],
    "waterloo":   [("Canada", ("ontario", "laurier")), ("Belgium", ("belgium",)),
                   ("Canada", ())],
    "hamilton":   [("Canada", ("ontario", "mcmaster")),
                   ("New Zealand", ("waikato", "new zealand")), ("Canada", ())],
    "kingston":   [("Canada", ("ontario", "queen's", "queens university")),
                   ("Jamaica", ("jamaica",)), ("Canada", ())],
    "windsor":    [("Canada", ("ontario",)), ("United Kingdom", ("berkshire",)),
                   ("Canada", ())],
    "victoria":   [("Canada", ("british columbia", "uvic")),
                   ("Australia", ("australia", "melbourne")), ("Canada", ())],
    "surrey":     [("Canada", ("british columbia", "kwantlen")),
                   ("United Kingdom", ())],
    "truro":      [("Canada", ("nova scotia", "dalhousie")),
                   ("United Kingdom", ("cornwall",)), ("United Kingdom", ())],
    "york":       [("Canada", ("ontario", "toronto")), ("United Kingdom", ())],
    "durham":     [("United States", ("north carolina", "duke")),
                   ("United Kingdom", ())],
    "lincoln":    [("New Zealand", ("new zealand",)),
                   ("United States", ("nebraska",)), ("United Kingdom", ())],
    "sydney":     [("Canada", ("nova scotia", "cape breton")),
                   ("Australia", ())],
    "perth":      [("United Kingdom", ("scotland",)), ("Australia", ())],
    "birmingham": [("United States", ("alabama", "uab")), ("United Kingdom", ())],
    "newcastle":  [("Australia", ("australia", "nsw")), ("United Kingdom", ())],
    "laval":      [("Canada", ()), ],
}

# Institution names that pin a country on their own. Canadian ones are listed
# exhaustively because Canada is the priority market for this search.
CA_INSTITUTIONS = (
    "university of toronto", "mcgill", "university of british columbia",
    "university of alberta", "mcmaster", "université de montréal",
    "universite de montreal", "university of montreal", "university of waterloo",
    "western university", "university of ottawa", "université d'ottawa",
    "queen's university at kingston", "university of calgary", "dalhousie",
    "simon fraser", "university of victoria", "university of saskatchewan",
    "university of manitoba", "university of guelph", "carleton university",
    "york university", "concordia university", "université laval",
    "universite laval", "memorial university", "university of new brunswick",
    "university of prince edward island", "acadia university",
    "saint mary's university", "mount allison", "brock university", "lakehead",
    "laurentian university", "university of windsor", "wilfrid laurier",
    "ontario tech", "university of regina", "university of lethbridge",
    "thompson rivers", "macewan", "mount royal university", "nipissing",
    "cape breton university", "bishop's university", "université de sherbrooke",
    "universite de sherbrooke", "polytechnique montréal", "polytechnique montreal",
    "hec montréal", "hec montreal", "royal military college", "ocad university",
    "emily carr", "vancouver island university", "olds college",
    "holland college", "fanshawe", "conestoga", "seneca polytechnic",
    "george brown college", "sheridan college", "algonquin college",
    "agriculture and agri-food canada", "national research council canada",
    "toronto metropolitan", "trent university", "athabasca", "capilano",
    "kwantlen", "langara", "camosun", "okanagan college", "red river",
    "assiniboine", "nscc", "nbcc", "university canada west", "quest university",
    "st. francis xavier", "mount saint vincent", "université du québec",
    "universite du quebec", "uqam", "uqtr", "inrs", "canadian light source",
)

REGIONS = {
    "North America": {"United States", "Canada", "Mexico"},
    "Europe": {"United Kingdom", "Ireland", "Germany", "France", "Netherlands", "Belgium",
               "Switzerland", "Austria", "Sweden", "Norway", "Denmark", "Finland", "Spain",
               "Italy", "Portugal", "Poland", "Czechia", "Greece", "Hungary", "Romania",
               "Slovakia", "Slovenia", "Croatia", "Estonia", "Latvia", "Lithuania",
               "Iceland", "Luxembourg", "Cyprus", "Malta", "Bulgaria", "Serbia"},
    "Asia-Pacific": {"China", "Japan", "South Korea", "Singapore", "Hong Kong", "India",
                     "Malaysia", "Thailand", "Taiwan", "Vietnam", "Indonesia",
                     "Philippines", "Pakistan", "Bangladesh", "Australia", "New Zealand"},
    "Middle East": {"United Arab Emirates", "Saudi Arabia", "Qatar", "Kuwait", "Oman",
                    "Bahrain", "Israel", "Turkey", "Jordan", "Lebanon"},
    "Africa": {"Egypt", "Morocco", "South Africa", "Kenya", "Nigeria", "Ghana",
               "Ethiopia", "Tanzania"},
    "Latin America": {"Brazil", "Argentina", "Chile", "Colombia", "Peru", "Uruguay",
                      "Costa Rica", "Jamaica"},
}

# ---------------------------------------------------------------------------
# Pre-compiled matchers. Every one of these is word-boundary anchored -- a
# two-letter code is never matched as a bare lower-case substring.
# ---------------------------------------------------------------------------
_PAREN_CODE = re.compile(r"\(([A-Za-z]{2})\)")
_COMMA_CODE = re.compile(r",\s*([A-Z]{2})\b")
_COUNTRY_RE = [(name, re.compile(r"\b" + re.escape(name.lower()) + r"\b"))
               for name in sorted(set(ISO.values()), key=len, reverse=True)]
_CA_PROV_RE = [re.compile(r"\b" + re.escape(p) + r"\b") for p in CA_PROVINCE_NAMES]
_US_STATE_RE = [re.compile(r"\b" + re.escape(s) + r"\b") for s in US_STATE_NAMES]
_CITY_RE = [(country, re.compile(r"\b" + re.escape(city) + r"\b"))
            for country, cities in CITIES.items() for city in cities]
_AMBIG_RE = {city: re.compile(r"\b" + re.escape(city) + r"\b")
             for city in AMBIGUOUS_CITIES}
_CA_INST_RE = [re.compile(r"\b" + re.escape(i) + r"\b") for i in CA_INSTITUTIONS]


def _codes_in(field: str, trailing_only: bool = False) -> str | None:
    """
    ISO country code or US/CA state code written explicitly: '(US)', ', NC'.

    `trailing_only` restricts parenthesised codes to the very end of the field.
    Job boards put the location last ("... Bridgewater, Virginia (US)"), while a
    bracket in the middle of a description is usually something else entirely --
    "Agriculture Business Instructor, Full-time Tenure Track (BC)" is Bakersfield
    College, not British Columbia.
    """
    tail_pos = len(field.rstrip())
    for m in _PAREN_CODE.finditer(field):
        if trailing_only and m.end() < tail_pos:
            continue
        code = m.group(1).upper()
        if code in ISO:
            return ISO[code]
        if code in CA_PROVINCE_CODES:
            return "Canada"
        if code in US_STATES:
            return "United States"
    for m in _COMMA_CODE.finditer(field):          # upper-case only, after a comma
        code = m.group(1)
        if code in CA_PROVINCE_CODES and code not in US_STATES:
            return "Canada"
        if code in US_STATES:
            return "United States"
        if code in ISO:
            return ISO[code]
    return None


def infer_country(location: str, org: str = "", source: str = "",
                  extra: str = "") -> str:
    """
    Resolve a posting to a country.

    Rules are applied in descending order of reliability and each one is
    word-boundary anchored. The fields are consulted in order of trust:
    the structured location first, then the employer name, then the tail of
    the description (where the Madgex boards park the location).
    """
    loc = (location or "").strip()
    org = (org or "").strip()
    tail = (extra or "")[-200:]
    fields = [f for f in (loc, org, tail) if f]
    if not fields:
        return "Canada" if source == "CAUT (Canada)" else "Unspecified"
    lows = [f.lower() for f in fields]

    # 1. an explicit code -- "(US)", "(CA)", ", NC", ", ON".
    #    Trusted anywhere in the structured location field, but only at the very
    #    end of the employer name or the description tail.
    for f, strict in ((loc, False), (org, True), (tail, True)):
        if not f:
            continue
        hit = _codes_in(f, trailing_only=strict)
        if hit:
            return hit

    # 2. a country written out in full
    for low in lows:
        for name, rx in _COUNTRY_RE:
            if rx.search(low):
                return name

    # 3. province / state written out in full
    for low in lows:
        if any(rx.search(low) for rx in _CA_PROV_RE):
            return "Canada"
    for low in lows:
        if any(rx.search(low) for rx in _US_STATE_RE):
            return "United States"

    # 4. unambiguous city
    for low in lows:
        for country, rx in _CITY_RE:
            if rx.search(low):
                return country

    # 5. ambiguous city -- resolved only by a co-signal
    whole = " ".join(lows)
    for city, rx in _AMBIG_RE.items():
        if any(rx.search(low) for low in lows):
            for country, signals in AMBIGUOUS_CITIES[city]:
                if not signals or any(s in whole for s in signals):
                    return country

    # 6. an institution that can only be in one country
    for low in lows:
        if any(rx.search(low) for rx in _CA_INST_RE):
            return "Canada"

    # 7. fall back on what the board itself implies. Only reached when the
    #    posting carries no geographic signal at all -- international listings
    #    on these boards nearly always state their country, and are caught above.
    return SOURCE_HOME_COUNTRY.get(source, "Unspecified")


SOURCE_HOME_COUNTRY = {
    "CAUT (Canada)": "Canada",
    # Scraped straight off a Canadian university's own careers portal, so the
    # country is certain even when the posting names no place.
    **{name: "Canada" for name in CANADIAN_UNIVERSITY_SOURCES},
    "NRC (federal)": "Canada",
    "Nova Scotia (provincial)": "Canada",
    "jobs.ac.uk": "United Kingdom",
    "Chronicle of Higher Ed": "United States",
    "Inside Higher Ed": "United States",
    "HigherEdJobs": "United States",
    # Nature Careers, Times Higher Education, EURAXESS and jobRxiv are genuinely
    # international -- no default is defensible, so they stay Unspecified.
}


def region_of(country: str) -> str:
    for reg, members in REGIONS.items():
        if country in members:
            return reg
    return "Other"


# ---------------------------------------------------------------------------
# Role classification
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    """Fold punctuation to spaces so slash- and hyphen-joined titles match.

    'Assistant/Associate/Full-Professor' and 'Assistant Professor' have to look
    the same to the pattern list, or a real tenure-track line gets filed as
    'Other Academic'.
    """
    return " " + re.sub(r"[^a-z0-9]+", " ", s.lower()).strip() + " "


# patterns normalised once, the same way the text will be
_ROLE_PATTERNS = [(role, [_norm(p).strip() for p in pats])
                  for role, pats in ROLE_PATTERNS]


def classify_role(title: str, summary: str = "") -> str:
    t = _norm(title)
    for role, patterns in _ROLE_PATTERNS:
        if any(p in t for p in patterns):
            return role

    # Slash-stacked ranks -- "Assistant/Associate/Full-Professor",
    # "Open Rank Professor" -- which no single literal covers.
    if "professor" in t:
        if "assistant" in t or "tenure" in t or "open rank" in t:
            return "Tenure-Track Faculty"
        return "Professor / Senior Faculty"

    s = _norm(summary)
    for role, patterns in _ROLE_PATTERNS:
        if any(p in s for p in patterns):
            return role
    if "professor" in s:
        return "Professor / Senior Faculty"

    if any(_norm(sig).strip() in t or _norm(sig).strip() in s for sig in ACADEMIC_SIGNALS):
        return "Other Academic"
    return "Non-Academic"


# ---------------------------------------------------------------------------
# Domain scoring
# ---------------------------------------------------------------------------
# Keyword stems and acronyms are great for matching and terrible to read, so
# anything shown in the dashboard gets a human label first.
TERM_LABELS = {
    "agricultur": "Agriculture", "agronom": "Agronomy", "hydrolog": "Hydrology",
    "horticultur": "Horticulture", "entomolog": "Entomology",
    "agroecolog": "Agroecology", "sensing technolog": "Sensing technology",
    "plant produc": "Plant production", "crop protection": "Crop protection",
    "farm": "Farming", "crop": "Crops", "sensor": "Sensors", "robotic": "Robotics",
    "convolutional": "CNNs", "generative": "Generative models",
    "ai": "AI", "gis": "GIS", "cea": "Controlled-environment ag", "iot": "IoT",
    "uav": "UAV", "ndvi": "NDVI", "rtk": "RTK", "gnss": "GNSS",
    "ai-driven": "AI-driven", "ai-enabled": "AI-enabled", "ml models": "ML models",
    "variable rate": "Variable-rate", "variable-rate": "Variable-rate",
    "site specific": "Site-specific", "site-specific": "Site-specific",
    "climate smart": "Climate-smart", "climate-smart": "Climate-smart",
    "agtech": "AgTech", "ag-tech": "AgTech", "agri-food": "Agri-food",
    "agrifood": "Agri-food", "unmanned aerial": "Unmanned aerial vehicles",
    "rural": "Rural", "livestock": "Livestock",
    "plant patholog": "Plant pathology", "viticultur": "Viticulture",
    "silvicultur": "Silviculture", "irrigat": "Irrigation",
    "seed technolog": "Seed technology", "seed produc": "Seed production",
    "geostatistic": "Geostatistics", "rural development": "Rural development",
    "climate smart agricultur": "Climate-smart agriculture",
    "climate-smart agricultur": "Climate-smart agriculture",
    "regenerative agricultur": "Regenerative agriculture",
    "tree crop": "Tree crops", "plantation management": "Plantation management",
}

# Safety net so a stem added to profile.py later cannot leak into the UI as
# "Plant patholog". Longest suffix wins.
_STEM_ENDINGS = [
    ("patholog", "pathology"), ("entomolog", "entomology"), ("technolog", "technology"),
    ("agroecolog", "agroecology"), ("hydrolog", "hydrology"), ("ecolog", "ecology"),
    ("olog", "ology"), ("ultur", "ulture"), ("produc", "production"),
    ("geostatistic", "geostatistics"), ("istic", "istics"), ("irrigat", "irrigation"),
    ("mechaniz", "mechanization"), ("mechanis", "mechanisation"),
]


def display_term(term: str) -> str:
    key = term.strip().lower()
    if key in TERM_LABELS:
        return TERM_LABELS[key]
    for stem, full in _STEM_ENDINGS:
        if key.endswith(stem):
            key = key[: -len(stem)] + full
            break
    return key[:1].upper() + key[1:]


def _compile(term: str):
    """
    Word-boundary matcher for a keyword.

    Short tokens are anchored at BOTH ends -- without this, "ai" matches inside
    "ch(ai)r" and "gis" inside "re(gis)trar", which silently poisons the score.
    Longer entries are treated as stems ("agricultur" -> agriculture /
    agricultural), so only the leading boundary is anchored.
    """
    probe = re.sub(r"[^a-z0-9]+", " ", term.lower()).strip()
    if not probe:
        return None
    pattern = r"\b" + r"\s+".join(re.escape(p) for p in probe.split())
    if len(probe) <= 3:            # ai, gis, iot, uav, rtk, cea -- exact only
        pattern += r"\b"
    return re.compile(pattern)     # 4+ chars are stems: crop -> crops/cropping


# built once at import -- {group: (axis, weight, [(term, regex), ...])}
_GROUPS = {
    group: (cfg["axis"], cfg["weight"],
            [(t.strip(), rx) for t in cfg["terms"] if (rx := _compile(t))])
    for group, cfg in KEYWORD_GROUPS.items()
}


# Compiled once. Word-boundary anchored at the front so "hydrolog" catches
# hydrology and hydrological, while "uav" cannot fire inside another word.
_CORE_RE = [re.compile(r"\b" + re.escape(term) + (r"\b" if len(term) <= 4 else ""))
            for term in CORE_DISCIPLINES]


def core_discipline_in_title(title: str) -> bool:
    """Does the title name one of the CV's own land/earth disciplines?"""
    t = " " + re.sub(r"[^a-z0-9 ]+", " ", title.lower()) + " "
    return any(rx.search(t) for rx in _CORE_RE)


def score_domain(title: str, body: str):
    """
    -> (per-axis raw scores, {group: [matched terms]}, agriculture evidence)

    The agriculture evidence is tracked separately from the score because it
    decides whether the posting is shown at all, not just how it ranks.
    """
    t = " " + re.sub(r"[^a-z0-9 ]+", " ", title.lower()) + " "
    b = " " + re.sub(r"[^a-z0-9 ]+", " ", body.lower()) + " "
    raw = {"ag": 0.0, "tech": 0.0, "context": 0.0}
    matched: dict[str, list[str]] = {}
    ag_in_title = False
    ag_body_terms: set[str] = set()

    for group, (axis, w, terms) in _GROUPS.items():
        hits, best = [], 0.0
        for term, rx in terms:
            in_title = bool(rx.search(t))
            in_body = in_title or bool(rx.search(b))
            if in_body:
                hits.append(term)
                # each group contributes once at full weight, extra terms taper
                best = max(best, w * (TITLE_MULTIPLIER if in_title else 1.0))
                if axis == "ag":
                    ag_body_terms.add(term)
                    if in_title:
                        ag_in_title = True
        if hits:
            # first hit at full value, additional distinct terms add 15% each
            raw[axis] += best + w * 0.15 * (len(hits) - 1)
            matched[group] = sorted(set(hits))[:6]

    return raw, matched, (ag_in_title, len(ag_body_terms))


def score_job(job: dict) -> dict:
    title = job.get("title", "") or ""
    body = " ".join(str(job.get(k, "") or "") for k in ("summary", "org", "location"))
    blob = f"{title} {body}".lower()

    raw, matched, (ag_in_title, ag_body_terms) = score_domain(title, body)

    # ---- the relevance gate ---------------------------------------------
    # Agriculture is the subject; AI/GIS/robotics are only the tools. A posting
    # that is not about agriculture is dropped, not merely ranked low -- unless
    # its title names one of the CV's own land/earth disciplines, which is the
    # single documented exception (see CORE_DISCIPLINES).
    has_agriculture = ag_in_title or ag_body_terms >= AG_MIN_BODY_TERMS
    via_discipline = not has_agriculture and core_discipline_in_title(title)
    is_agricultural = has_agriculture or via_discipline
    if REQUIRE_AGRICULTURE and not is_agricultural:
        job = dict(job)
        job.update({"score": 0.0, "rejected": "not agricultural",
                    "matched": matched, "match_terms": [], "areas": [],
                    "role": classify_role(title, body), "synergy": False,
                    "is_agricultural": False, "via_discipline": False,
                    "age_days": age_days(job.get("posted", "")),
                    "country": "Unspecified", "region": "Other",
                    "priority": 3, "is_faculty": False, "is_tenure_track": False,
                    "is_priority_country": False,
                    "id": hashlib.sha1((job.get("url") or title).encode(
                        "utf-8", "ignore")).hexdigest()[:16]})
        return job

    ag = 1.0 - math.exp(-raw["ag"] / AG_SATURATION)
    if via_discipline:
        # No agricultural evidence to score, so credit the discipline instead.
        ag = max(ag, CORE_DISCIPLINE_AG_CREDIT)
    tech = 1.0 - math.exp(-raw["tech"] / TECH_SATURATION)

    role = classify_role(title, body)
    role_fit = ROLE_FIT.get(role, 0.3)

    breadth = min(len(matched) / float(BREADTH_TARGET), 1.0)

    groups = set(matched)
    synergy = bool(groups & AG_GROUPS) and bool(groups & TECH_GROUPS)

    score = 100.0 * (WEIGHTS["ag"] * ag +
                     WEIGHTS["role"] * role_fit +
                     WEIGHTS["tech"] * tech +
                     WEIGHTS["breadth"] * breadth)
    if synergy:
        # scaled by role fit -- a PhD studentship in exactly the right niche is
        # still a PhD studentship, and must not outrank a real faculty line.
        score += SYNERGY_BONUS * role_fit

    # ---- penalties -------------------------------------------------------
    tl = f" {title.lower()} "
    if any(n in tl for n in NEGATIVE_TITLE):
        score *= 0.30
    if any(n in blob for n in NEGATIVE_BODY):
        score *= 0.80
    if not any(sig in blob for sig in ACADEMIC_SIGNALS):
        score *= 0.45
    # a posting with zero domain overlap is not a match no matter the title
    if not matched:
        score *= 0.25

    job = dict(job)
    job["score"] = round(min(score, 100.0), 1)
    job["role"] = role
    job["synergy"] = synergy
    # "cleared the relevance gate" -- via agriculture, or via the discipline
    # exception, which via_discipline distinguishes for the dashboard badge.
    job["is_agricultural"] = True
    job["via_discipline"] = via_discipline
    job["ag_strength"] = round(ag, 3)
    job["tech_strength"] = round(tech, 3)
    job["ag_areas"] = [g for g in matched if g in AG_GROUPS]
    job["tech_areas"] = [g for g in matched if g in TECH_GROUPS]
    # store human labels, not the matching stems -- "agricultur" is how we find
    # it, "Agriculture" is what the dashboard shows
    job["matched"] = {g: sorted({display_term(t) for t in terms})
                      for g, terms in matched.items()}
    job["match_terms"] = sorted({display_term(t)
                                 for terms in matched.values() for t in terms})[:10]
    job["areas"] = list(matched.keys())
    job["country"] = infer_country(job.get("location", ""), job.get("org", ""),
                                   job.get("source", ""), job.get("summary", ""))
    job["region"] = region_of(job["country"])

    # ---- priority: what the dashboard shows first ------------------------
    # Independent of the match score, which stays a pure measure of CV fit.
    job["is_faculty"] = role in FACULTY_ROLES
    job["is_tenure_track"] = role == "Tenure-Track Faculty"
    job["is_priority_country"] = job["country"] in PRIORITY_COUNTRIES
    job["is_government"] = job.get("source", "") in GOVERNMENT_SOURCES
    job["priority"] = (0 if job["is_priority_country"] and job["is_faculty"] else
                       1 if job["is_priority_country"] else
                       2 if job["is_faculty"] else 3)
    job["id"] = hashlib.sha1(
        (job.get("url", "") or (title + job.get("org", ""))).encode("utf-8", "ignore")
    ).hexdigest()[:16]
    job["age_days"] = age_days(job.get("posted", ""))
    return job


def age_days(iso: str) -> int | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - d).days)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# De-duplication -- the same job is often on 3 boards at once
# ---------------------------------------------------------------------------
_STOP = {"the", "of", "for", "and", "in", "a", "an", "at", "to", "on", "position",
         "job", "opening", "vacancy", "full", "time", "faculty"}


def _fingerprint(job: dict) -> str:
    title = re.sub(r"[^a-z0-9 ]+", " ", (job.get("title") or "").lower())
    words = sorted(w for w in title.split() if w not in _STOP and len(w) > 2)
    org = re.sub(r"[^a-z0-9]+", "", (job.get("org") or "").lower())[:22]
    return hashlib.sha1((" ".join(words[:9]) + "|" + org).encode()).hexdigest()[:16]


def deduplicate(jobs: list[dict]) -> list[dict]:
    """Keep the best-scoring copy; remember which other boards carried it."""
    best: dict[str, dict] = {}
    for j in jobs:
        fp = _fingerprint(j)
        if fp not in best:
            j["also_on"] = []
            best[fp] = j
        else:
            keep = best[fp]
            other = j
            if other["score"] > keep["score"]:
                other["also_on"] = sorted(set(keep.get("also_on", []) + [keep["source"]]))
                best[fp] = other
            elif other["source"] != keep["source"]:
                keep["also_on"] = sorted(set(keep.get("also_on", []) + [other["source"]]))
    return list(best.values())
