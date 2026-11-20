"""Selected local V10.3 editorial helpers adapted from supplied Build 6.1.1."""

import re

import json
import html

from datetime import datetime

from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

INSTITUTION_PATTERNS = {
    "ISRO": [
        r"\bisro\b", r"indian space research organi[sz]ation",
        r"\bvssc\b", r"vikram sarabhai space centre", r"\bursc\b",
        r"u\s*r\s*rao satellite centre", r"\bsac\b", r"space applications centre",
        r"\bsdsc\b", r"satish dhawan space centre", r"\blpsc\b",
        r"liquid propulsion systems centre", r"\bistrac\b", r"\bnrsc\b",
        r"national remote sensing centre", r"\bhsfc\b", r"human space flight centre",
        r"\biirs\b", r"indian institute of remote sensing",
    ],
    "IN-SPACe": [
        r"\bin[-‑–—]space\b", r"indian national space promotion and authorization centre",
        r"indian national space promotion and authorisation centre",
    ],
    "NSIL": [r"\bnsil\b", r"newspace india limited"],
    "Department of Space": [
        r"department of space", r"\bdos\b.{0,35}(?:space|isro)",
        r"(?:space|isro).{0,35}\bdos\b",
    ],
}

MISSION_TERMS = [
    "gaganyaan", "chandrayaan", "nisar", "spadex", "pslv", "gslv", "lvm3",
    "sslV", "navic", "nvs-02", "nvs-03", "aditya-l1", "mangalyaan",
    "venus orbiter", "shukrayaan", "bharatiya antariksh station", "bas-01",
    "lupex", "eos-", "oceansat", "project netra", "poem-", "rlv", "trishna",
]

OFFICIAL_DOMAINS = (
    "isro.gov.in", "dos.gov.in", "pib.gov.in", "inspace.gov.in", "inspace.gov.in",
    "nsilindia.co.in", "nsilindia.com",
)

PRIVATE_SPACE_TERMS = [
    "space startup", "space start-up", "space-tech", "space tech", "private space",
    "private-sector space", "private sector space", "commercial space company",
    "skyroot", "agnikul", "pixxel", "bellatrix", "dhruva space", "digantara",
    "galaxeye", "satsure", "pier sight", "piersight", "manastu", "etherealx",
    "orbitaid", "take me 2 space", "takeme2space", "xovian", "astrogate",
]

SPACE_RELEVANCE_TERMS = [
    "space mission", "satellite", "launch vehicle", "rocket", "spacecraft", "earth observation",
    "remote sensing", "navigation satellite", "satcom", "space station", "lunar", "moon mission",
    "planetary mission", "solar mission", "space debris", "space traffic", "space policy",
    "space economy", "space technology", "space science", "astronomy", "orbital",
]

def _first_meta(soup, specs):
    for attrs in specs:
        node = soup.find("meta", attrs=attrs)
        if node and node.get("content"):
            return str(node.get("content")).strip()
    return ""

def _jsonld_objects(soup):
    objects = []
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = node.string or node.get_text("", strip=True)
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        stack = obj if isinstance(obj, list) else [obj]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                objects.append(x)
                if "@graph" in x and isinstance(x["@graph"], list):
                    stack.extend(x["@graph"])
            elif isinstance(x, list):
                stack.extend(x)
    return objects

def _parse_published(raw):
    """Return (date_iso, exact_datetime_ist_or_None)."""
    s = str(raw or "").strip()
    if not s:
        return "", None
    # Date-only is intentionally preserved as time unknown.
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s[:10]) if len(s) == 10 else None
    if m:
        return s, None
    # ISO / RFC-ish formats.
    candidates = [s, s.replace("Z", "+00:00")]
    for value in candidates:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                # Time without reliable timezone is not acceptable as exact IST.
                return dt.date().isoformat(), None
            return dt.astimezone(IST).date().isoformat(), dt.astimezone(IST)
        except Exception:
            pass
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            return dt.date().isoformat(), None
        dt = dt.astimezone(IST)
        return dt.date().isoformat(), dt
    except Exception:
        pass
    # Common human-readable date only.
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat(), None
        except Exception:
            pass
    return "", None

def _norm_title(value):
    value = html.unescape(str(value or "")).lower()
    value = re.sub(r"\s+-\s+[^-]{2,80}$", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def _is_private_space_story(title, body):
    text = f"{title} {body[:2600]}".lower()
    private = any(term in text for term in PRIVATE_SPACE_TERMS)
    india = any(x in text for x in [
        "india", "indian", "bengaluru", "bangalore", "hyderabad", "chennai",
        "ahmedabad", "sriharikota", "new delhi", "delhi", "pune"
    ])
    named_indian_company = any(x in text for x in [
        "skyroot", "agnikul", "pixxel", "bellatrix", "dhruva space", "digantara",
        "galaxeye", "satsure", "piersight", "manastu", "etherealx", "orbitaid",
        "takeme2space", "take me 2 space", "xovian", "astrogate"
    ])
    return private and (india or named_indian_company)

def _is_english_article(title, body):
    sample = re.sub(r"\s+", " ", f"{title} {body[:2400]}").strip()
    letters = [c for c in sample if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if ("A" <= c <= "Z") or ("a" <= c <= "z"))
    return latin / max(1, len(letters)) >= 0.72

def classify_tone(title, body="", institutions=None):
    """Classify media tone from the perspective of ISRO/DoS/IN-SPACe/NSIL.

    This is intentionally *not* generic word sentiment.  The label answers:
    "How is the covered development portraying or affecting the standing of the
    four institutions?"

    Negative is reserved for coverage that is derogatory, accusatory,
    disparaging, or materially questions competence, credibility, integrity,
    governance, performance, or decisions of ISRO/DoS/IN-SPACe/NSIL.

    A delay, anomaly, failure, accident, risk, investigation, or other adverse
    event is NOT automatically Negative.  Without a reputational/critical stance
    toward the institution it normally remains Neutral, while operational impact
    is assessed separately by classify_impact().

    Positive covers direct praise/achievement as well as clearly beneficial
    ecosystem developments (for example successful missions, useful partnerships,
    technology transfer, or growth of India's private space ecosystem).
    """
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    body = re.sub(r"\s+", " ", str(body or "")).strip()
    full = (title + ". " + body).strip()
    lower = full.lower()

    # Re-use the same institution vocabulary used by the four-institution gate,
    # so the stance must be tied to ISRO/DoS/IN-SPACe/NSIL or an ISRO centre.
    inst_pattern = "(?:" + "|".join(
        p for patterns in INSTITUTION_PATTERNS.values() for p in patterns
    ) + ")"

    def _sentences(text):
        return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\s*[;|]\s*", text) if x.strip()]

    # Patterns encode *direction of stance*, not just vocabulary.  For example,
    # "ISRO criticised X" does not match the negative passive/object patterns,
    # while "ISRO was criticised" and "criticism of ISRO" do.
    negative_patterns = [
        rf"{inst_pattern}.{{0,55}}\b(?:was|is|has been|had been|were|are)\s+(?:sharply\s+|strongly\s+)?(?:criticis(?:ed|zed)|slammed|accused|blamed|questioned|condemned|mocked|ridiculed)",
        rf"{inst_pattern}.{{0,65}}\b(?:faces?|faced|draws?|drew|attracts?|attracted|came under|is under|remains under)\s+(?:sharp\s+|strong\s+|growing\s+)?(?:criticism|scrutiny|fire|backlash|questions?|accusations?|allegations?)",
        rf"\b(?:criticis(?:ed|zed)|slammed|accused|blamed|questioned|condemned|mocked|ridiculed)\b.{{0,70}}{inst_pattern}",
        rf"\b(?:criticism|accusations?|allegations?|backlash|questions?|charges?)\s+(?:of|against|over|towards?|about)\s+.{{0,45}}{inst_pattern}",
        rf"{inst_pattern}.{{0,70}}\b(?:mismanagement|incompetence|negligence|corruption|opacity|lack of transparency|poor governance|poor handling|mishandling|wastefulness|wasteful spending|unaccountability|serious lapse|major lapse)",
        rf"{inst_pattern}.{{0,50}}\b(?:failed to|failure to)\b.{{0,65}}\b(?:explain|deliver|prevent|address|respond|disclose|manage|meet|protect|maintain)",
        rf"\b(?:audit|report|committee|court|experts?|critics?|opposition|employees?|scientists?)\b.{{0,80}}\b(?:faulted|criticis(?:ed|zed)|blamed|questioned|accused)\b.{{0,55}}{inst_pattern}",
        rf"\b(?:under fire|in the dock|faces backlash)\b.{{0,45}}{inst_pattern}",
    ]

    positive_patterns = [
        rf"{inst_pattern}.{{0,55}}\b(?:was|is|has been|were|are)\s+(?:widely\s+|internationally\s+)?(?:praised|lauded|hailed|commended|applauded|congratulated|recognised|recognized)",
        rf"\b(?:praised|lauded|hailed|commended|applauded|congratulated)\b.{{0,70}}{inst_pattern}",
        rf"{inst_pattern}.{{0,75}}\b(?:successfully|success|achievement|milestone|breakthrough|record|historic|first-of-its-kind|demonstrated|validated|completed|accomplished)\b",
        rf"{inst_pattern}.{{0,60}}\b(?:strengthens?|boosts?|enhances?|expands?|advances?)\b.{{0,70}}\b(?:capability|capacity|mission|technology|cooperation|partnership|ecosystem|self-reliance|leadership)",
    ]

    neg_score = 0
    pos_score = 0

    title_lower = title.lower()
    for pat in negative_patterns:
        if re.search(pat, title_lower, flags=re.I):
            neg_score += 4  # headline stance is especially important
    for pat in positive_patterns:
        if re.search(pat, title_lower, flags=re.I):
            pos_score += 4

    for sentence in _sentences(body[:1600]):
        sl = sentence.lower()
        # Ignore sentences with no institutional anchor for reputational stance.
        if not re.search(inst_pattern, sl, flags=re.I):
            continue
        neg_score += sum(2 for pat in negative_patterns if re.search(pat, sl, flags=re.I))
        pos_score += sum(2 for pat in positive_patterns if re.search(pat, sl, flags=re.I))

    # Clearly beneficial developments can be Positive from ISRO's perspective
    # even when the article is not explicitly praising ISRO.  These are event
    # combinations, not isolated positive words.
    beneficial_event_rules = [
        # Indian private-space ecosystem growth, funding, production or capability.
        (
            ("startup", "start-up", "private space", "private-sector", "private sector", "space-tech", "space tech"),
            ("growth", "expansion", "investment", "funding", "manufacturing", "production", "capacity", "indigenous", "fund raise", "raised"),
        ),
        # Technology transfer / commercialisation of domestic space capability.
        (
            ("technology transfer", "tech transfer", "licensing", "technology licence", "technology license"),
            ("industry", "company", "startup", "commercial", "manufacturing", "production"),
        ),
        # Cooperation or partnership involving one of the institutions.
        (
            ("partnership", "cooperation", "collaboration", "agreement", "memorandum of understanding", "mou"),
            ("joint mission", "technology", "data", "launch", "satellite", "research", "industry", "international"),
        ),
    ]
    institution_present = bool(re.search(inst_pattern, lower, flags=re.I))
    private_ecosystem_story = _is_private_space_story(title, body)
    if institution_present or private_ecosystem_story:
        for left, right in beneficial_event_rules:
            if any(x in lower for x in left) and any(x in lower for x in right):
                pos_score += 2

    # Operationally bad events are deliberately excluded from the negative tone
    # decision unless one of the directed critical/derogatory patterns matched.
    # This keeps "launch delayed by weather" Neutral but "ISRO criticised over
    # repeated delays" Negative.
    if neg_score >= 3 and neg_score > pos_score:
        return "Negative"
    if pos_score >= 2 and pos_score > neg_score:
        return "Positive"
    return "Neutral"

def classify_impact(text, institutions, concern_ids):
    """Assess impact on ISRO/DoS/IN-SPACe/NSIL from likely consequences.

    Impact level is deliberately separate from tone.  A critical article can be
    low operational impact, while a neutral technical event can be high impact.
    No single keyword is allowed to force High.  High requires evidence of a
    direct and material consequence for missions, safety, resources, strategy,
    institutional functioning, or long-duration programme execution.
    """
    lower = re.sub(r"\s+", " ", (text or "").lower()).strip()

    def has(*terms):
        return any(term in lower for term in terms)

    def count_groups(groups):
        return sum(1 for group in groups if any(term in lower for term in group))

    # Direct institutional relevance.  Articles that explicitly name one of the
    # four institutions have more potential impact than general sector stories.
    direct = bool(institutions) or has(
        "isro", "indian space research organisation", "indian space research organization",
        "department of space", "in-space", "in‑space", "in–space", "nsil",
        "newspace india limited",
    )

    # Evidence groups describe consequences, not sentiment words.
    severe_event = has(
        "mission failure", "launch failure", "failed mission", "vehicle failure",
        "serious anomaly", "major anomaly", "crash", "collision", "sabotage",
        "loss of mission", "loss of satellite", "explosion", "fatal", "fatality",
        "crew safety", "human rating failure", "safety breach",
        "programme cancelled", "program cancelled", "mission cancelled",
        "programme suspended", "mission suspended",
    )
    material_delay = has(
        "months delay", "month delay", "six-month", "six month", "year delay",
        "indefinitely postponed", "long delay", "major delay", "schedule slippage",
        "repeated delay", "repeated delays",
    )
    minor_delay = has("delay", "delayed", "postponed", "slipped", "deferred") and not material_delay

    mission_effect = count_groups([
        ("gaganyaan", "chandrayaan", "nisar", "navic", "pslv", "gslv", "lvm3", "sslv", "aditya-l1"),
        ("mission readiness", "launch readiness", "mission schedule", "launch schedule", "critical test", "qualification test"),
        ("launch pad", "spaceport", "ground segment", "tracking network", "propulsion", "flight hardware"),
    ])
    resource_effect = count_groups([
        ("budget cut", "budget reduction", "funding cut", "funding shortfall", "cost overrun", "major allocation", "budget increase"),
        ("staff shortage", "critical vacancy", "mass resignation", "attrition", "workforce shortage"),
        ("major contract", "strategic contract", "large contract", "procurement delay", "supply disruption", "supply chain disruption"),
    ])
    strategic_effect = count_groups([
        ("national security", "strategic capability", "defence", "defense", "military space"),
        ("spectrum allocation", "satcom spectrum", "foreign launcher dependence", "technology denial", "export restriction"),
        ("space policy", "space act", "space legislation", "major regulatory change", "privatisation", "privatization"),
    ])
    institutional_effect = count_groups([
        ("investigation into isro", "investigation into nsil", "investigation into in-space", "official inquiry"),
        ("leadership resignation", "chairman resignation", "governance failure", "institutional crisis"),
        ("operations suspended", "facility shutdown", "centre shutdown", "center shutdown"),
    ])

    # Ecosystem developments are usually meaningful but indirect.  They should
    # normally be Medium, not High, unless paired with a direct severe effect.
    commercial_event = has("contract", "order", "procurement", "tender")

    ecosystem = has(
        "startup", "start-up", "space-tech", "space tech", "private sector",
        "private-sector", "private company", "private companies", "industry participation",
        "commercial space", "technology transfer", "tech transfer", "manufacturing",
        "supplier", "supply base", "partnership", "cooperation", "collaboration",
        "memorandum of understanding", "mou", "funding", "investment",
    )

    # High impact requires either a severe direct event, or multiple material
    # consequence dimensions with direct institutional relevance.  A concern
    # query hit is only supporting evidence; it never forces High by itself.
    consequence_dimensions = (
        (1 if severe_event or material_delay else 0)
        + (1 if mission_effect else 0)
        + (1 if resource_effect else 0)
        + (1 if strategic_effect else 0)
        + (1 if institutional_effect else 0)
    )

    if direct and severe_event:
        level = "High"
    elif direct and material_delay and mission_effect:
        level = "High"
    elif direct and consequence_dimensions >= 2 and (mission_effect or resource_effect or strategic_effect or institutional_effect):
        level = "High"
    elif material_delay or ecosystem or mission_effect or resource_effect or strategic_effect or institutional_effect or concern_ids or (direct and commercial_event):
        level = "Medium"
    else:
        level = "Low"

    # Private-space/start-up ecosystem: describe the concrete ecosystem effect.
    if (has("startup", "start-up", "space-tech", "space tech", "private sector", "private-sector",
            "private company", "private companies", "industry participation", "commercial space")
            and not has("major regulatory change", "space act", "space legislation", "spectrum allocation")):
        if has("funding", "investment", "fund raise", "raises", "venture", "capital"):
            reason = (
                "More funding for Indian space companies can strengthen ISRO's supplier and innovation ecosystem. "
                "It may help private firms take on more technology, manufacturing and service work around ISRO missions."
            )
        elif has("manufacturing", "production", "factory", "supply chain", "supplier"):
            reason = (
                "Greater private manufacturing capacity can broaden ISRO's domestic supply base. "
                "This can support scaling of launch, satellite and mission hardware while ISRO focuses on advanced R&D and missions."
            )
        else:
            reason = (
                "Growth in India's private space sector can strengthen ISRO's innovation and supplier ecosystem. "
                "It may allow industry to take on more commercial and production work while ISRO focuses on advanced missions."
            )

    elif has("technology transfer", "tech transfer", "technology licence", "technology license", "licensing"):
        reason = (
            "This can move ISRO-developed technology into wider industry use and build domestic capability. "
            "It may also reduce ISRO's need to handle routine production itself."
        )

    elif has("contract", "order", "procurement", "tender"):
        reason = (
            "This could affect how ISRO sources hardware or services and how much work industry takes on. "
            "The impact depends on the contract's scale, mission relevance and delivery schedule."
        )

    elif has("partnership", "cooperation", "collaboration", "agreement", "memorandum of understanding", "mou"):
        reason = (
            "The cooperation can give ISRO access to complementary technology, data or mission capability. "
            "It may reduce development burden and support future joint missions."
        )

    elif severe_event or has("failed", "failure", "anomaly", "setback", "crash"):
        reason = (
            "The event may require technical review, additional testing or corrective action before the programme moves ahead. "
            "Its impact depends on whether mission readiness or future schedules are materially affected."
        )
    elif material_delay:
        reason = (
            "The delay could materially affect the programme schedule and dependent activities. "
            "ISRO may need to re-sequence testing, launch slots or follow-on milestones."
        )
    elif minor_delay:
        reason = (
            "The article reports a schedule change that may affect the immediate timeline. Wider significance may remain limited unless dependent milestones are also affected."
        )
    elif has("test", "trial", "demonstration"):
        reason = (
            "The result is relevant to readiness for the next development or mission milestone. "
            "Its impact depends on whether further testing or design changes are required."
        )
    elif has("launch", "mission", "gaganyaan", "chandrayaan", "aditya", "nisar", "navic", "satellite"):
        reason = (
            "This is relevant to ISRO's mission planning or execution. "
            "The impact depends on whether it changes readiness, resources or the timing of follow-on activities."
        )

    elif has("crew safety", "human rating", "safety", "accident"):
        reason = (
            "This could affect ISRO's safety and mission-assurance work. "
            "A material safety issue may require additional reviews, testing or safeguards."
        )

    elif has("policy", "regulation", "regulatory", "spectrum", "approval", "privatisation", "privatization"):
        reason = (
            "The policy or regulatory development may affect the operating environment around ISRO and India's space sector. "
            "Its significance depends on whether it changes approvals, commercial participation or programme planning."
        )

    elif has("budget", "funding", "allocation", "expenditure"):
        reason = (
            "The funding development may influence the pace of missions, infrastructure or technology programmes. "
            "Its impact depends on the size and duration of the change."
        )

    elif has("vacancy", "vacancies", "attrition", "recruitment", "staff", "workforce", "employee"):
        reason = (
            "This may affect ISRO's programme execution capacity if it creates sustained gaps in specialised teams. "
            "A limited or temporary staffing issue would have a smaller impact."
        )

    elif has("national security", "strategic", "defence", "defense", "military"):
        reason = (
            "This may affect the strategic importance or prioritisation of India's space capabilities. "
            "The impact depends on whether ISRO programmes, infrastructure or services need to change in response."
        )

    elif level == "High":
        reason = (
            "The development appears to have a direct and material consequence for ISRO's programmes, resources or strategic priorities. "
            "It may require significant follow-up or changes to execution."
        )
    elif level == "Medium":
        reason = (
            "The article covers a development of potential relevance to programme planning, the space ecosystem or the wider operating environment. No major immediate operational effect is evident from the available report."
        )
    else:
        reason = "The article provides information relevant to the Indian space programme, while no significant operational or strategic consequence is evident from the available report."

    return level, reason
