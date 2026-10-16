
import re
from dataclasses import dataclass
from typing import Literal


Eligibility = Literal[
    "worldwide",
    "emea",
    "country_restricted",
    "unknown",
]


@dataclass(frozen=True)
class JobAssessment:
    relevance_score: int
    eligibility: Eligibility
    relevance_reasons: tuple[str, ...]
    eligibility_reason: str


# Higher weights are given to the role itself rather than isolated keywords.
ROLE_WEIGHTS = {
    "frontend": 35,
    "full_stack": 35,
    "backend": 25,
    "web_developer": 30,
    "software_engineer": 20,
    "internship": 10,
    "junior": 10,
    "contract": 5,
}

SKILL_WEIGHTS = {
    "react": 10,
    "typescript": 10,
    "javascript": 8,
    "html": 5,
    "css": 5,
    "nextjs": 7,
    "nodejs": 7,
    "python": 5,
    "fastapi": 5,
    "vue": 5,
    "angular": 5,
    "tailwind_css": 6,
    "sass": 4,
    "react_native": 5,
    "tanstack_query": 4,
    "redux_toolkit": 4,
    "vite": 5,
    "pwa": 7,
    "component_architecture": 5,
    "state_management": 4,
    "api_integration": 5,
    "react_testing_library": 3,
    "jest": 3,
    "vitest": 3,
    "vite": 3,
    "responsive_design": 5,
    "accessibility": 5,
    "wcag": 5,
    "aria": 3,
    "semantic_html": 3,
    "ui_ux": 3,
    "wireframing": 2,
    "ci_cd": 3,
    "claude": 2,
    "express": 5,
    "context_api": 4,
    "zustand": 4,
    "git": 2,
    "graphql": 5,
    "sql": 3,
    "postgresql": 3,
    "rest_api": 3,
    "docker": 2,
    "kubernetes": 2,
}

UNRELATED_ROLE_PATTERNS = [
    r"\b(?:registered nurse|nursing|surgeon|physician)\b",
    r"\b(?:accountant|bookkeeper|tax analyst)\b",
    r"\b(?:sales representative|real estate agent)\b",
    r"\b(?:truck driver|delivery driver)\b",
]

SENIOR_ROLE_PATTERN = re.compile(
    r"\b(?:staff|principal|distinguished|director|vp|vice president)\b"
    r"|\b(?:senior|sr\.?)\b"
    r"|\b(?:lead|head of)\s+(?:engineering|frontend|front-end|"
    r"backend|back-end|software|development)\b",
    re.IGNORECASE,
)


def _has_term(text: str, term: str) -> bool:
    """Match a keyword as a whole term, including common technology aliases."""
    aliases = {
        "full_stack": r"\bfull[\s-]?stack\b",
        "web_developer": r"\bweb\s+developer\b",
        "software_engineer": r"\bsoftware\s+engineer\b",
        "nextjs": r"\bnext\.?js\b",
        "nodejs": r"\bnode\.?js\b",
        "rest_api": r"\brest(?:ful)?\s+apis?\b",
        "tailwind_css": r"\btailwind(?:\s+css)?\b",
        "sass": r"\b(?:sass|scss)\b",
        "react_native": r"\breact\s+native\b",
        "tanstack_query": r"\btanstack\s+query\b",
        "redux_toolkit": r"\bredux\s+toolkit\b|\brtk\b",
        "react_testing_library": (
            r"\breact\s+testing\s+library\b|\btesting-library/react\b"
        ),
        "jest": r"\bjest\b",
        "vitest": r"\bvitest\b",
        "vite": r"\bvite\b",
        "responsive_design": (
            r"\bresponsive\s+(?:web\s+)?(?:design|layouts?)\b"
        ),
        "accessibility": r"\baccessibility\b|\ba11y\b",
        "wcag": r"\bwcag(?:\s+\d(?:\.\d+)?)?(?:\s+aa|aaa)?\b",
        "aria": r"\baria\b",
        "semantic_html": r"\bsemantic\s+html\b",
        "ui_ux": r"\bui\s*/\s*ux\b|\buser[- ]centered\s+(?:design|interfaces?)\b",
        "wireframing": r"\bwirefram(?:e|es|ing)\b",
        "ci_cd": (
            r"\bci\s*[/&+]\s*cd\b|\bci\s+cd\b"
            r"|\bcontinuous\s+(?:integration|delivery|deployment)\b"
        ),
        "claude": r"\bclaude(?:\s+code)?\b",
        "express": r"\bexpress(?:\.js)?\b",
        "context_api": r"\b(?:react\s+)?context\s+api\b",
        "zustand": r"\bzustand\b",
        "git": r"\bgit\b",
        "graphql": r"\bgraphql\b|\bgraph\s+ql\b",
    }

    pattern = aliases.get(term, rf"\b{re.escape(term)}\b")
    return re.search(pattern, text, re.IGNORECASE) is not None


def score_job(
    title: str,
    description: str | None = None,
) -> tuple[int, tuple[str, ...]]:
    """
    Return a relevance score from 0 to 100 and the reasons behind it.

    This is a transparent heuristic, not a machine-learning prediction.
    """
    text = f"{title or ''}\n{description or ''}".strip()
    title_text = title or ""
    score = 0
    reasons: list[str] = []

    role_matches = [
        (term, weight)
        for term, weight in ROLE_WEIGHTS.items()
        if _has_term(title_text, term)
    ]

    # Avoid adding several overlapping role weights for the same role.
    role_score = max(
        (weight for term, weight in role_matches
         if term not in {"internship", "junior", "contract"}),
        default=0,
    )

    if role_score:
        score += role_score
        matched_roles = [
            term.replace("_", " ")
            for term, weight in role_matches
            if weight == role_score
        ]
        reasons.append(f"Relevant role: {', '.join(matched_roles)}")

    for term in ("internship", "junior", "contract"):
        if _has_term(title_text, term):
            score += ROLE_WEIGHTS[term]
            reasons.append(f"Target opportunity type: {term}")

    matched_skills = []
    for skill, weight in SKILL_WEIGHTS.items():
        if _has_term(text, skill):
            score += weight
            matched_skills.append(skill.replace("_", " "))

    if matched_skills:
        reasons.append(
            "Matching technologies: " + ", ".join(matched_skills)
        )

    if SENIOR_ROLE_PATTERN.search(title_text):
        score -= 25
        reasons.append("Reduced score for a senior or leadership title")

    if any(
        re.search(pattern, title_text, re.IGNORECASE)
        for pattern in UNRELATED_ROLE_PATTERNS
    ):
        score = min(score, 10)
        reasons.append("Role appears unrelated to web development")

    return max(0, min(100, score)), tuple(reasons)


def classify_eligibility(
    title: str,
    description: str | None = None,
    location: str | None = None,
    applicant_country: str = "Nigeria",
) -> tuple[Eligibility, str]:
    """
    Classify geographic eligibility based on explicit text evidence.

    Explicit exclusion of the applicant's country takes precedence.
    Ambiguous or conflicting evidence remains unknown.
    """
    text = " ".join(
        part for part in (title, description, location) if part
    )
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    country = applicant_country.strip().lower()

    if not normalized or not country:
        return "unknown", "Insufficient information to determine eligibility"

    # Explicitly naming Nigeria as excluded is strong negative evidence.
    exclusion_patterns = [
        rf"\b(?:not eligible|ineligible|cannot|can't|may not|must not)"
        rf"\s+(?:apply|work|be hired)\s+(?:from|in)\s+{re.escape(country)}\b",
        rf"\b(?:excluding|except|excluding applicants from)"
        rf"\s+{re.escape(country)}\b",
        rf"\b(?:only|must be based in|must reside in|residents of)"
        rf"\s+(?:the\s+)?(?:united states|u\.s\.a\.?|usa|us|"
        rf"united kingdom|uk|canada|australia)\b",
    ]

    if any(re.search(pattern, normalized) for pattern in exclusion_patterns):
        # The final pattern only proves exclusion if the listing is explicitly
        # limited to another location, rather than merely mentioning it.
        restriction = any(
            re.search(pattern, normalized)
            for pattern in exclusion_patterns
        )
        if restriction:
            return (
                "country_restricted",
                f"Listing contains geographic restriction evidence; "
                f"verify whether applicants from {applicant_country} are excluded",
            )

    worldwide_patterns = [
        r"\b(?:work|hire|hiring|applicants?)\s+(?:from\s+)?worldwide\b",
        r"\b(?:open|available)\s+to\s+(?:applicants?\s+)?worldwide\b",
        r"\banywhere\s+in\s+the\s+world\b",
        r"\bglobally\s+remote\b",
        r"\b(?:all|any)\s+countries\b",
    ]

    emea_patterns = [
        r"\bemea\b",
        r"\beurope\s*,?\s*(?:middle east\s*,?\s*)?and\s+africa\b",
        r"\bafrica\s*,?\s*europe\s*(?:and|&)\s*(?:the\s+)?middle east\b",
    ]

    nigeria_exclusion_patterns = [
        rf"\b(?:not\s+(?:available|open|hiring)|no\s+hiring|"
        rf"cannot\s+hire|can't\s+hire)\s+(?:(?:to|of)\s+)?"
        rf"(?:applicants?\s+)?(?:in|from)\s+{re.escape(country)}\b",
        rf"\b{re.escape(country)}\s+(?:is\s+)?(?:excluded|not eligible)\b",
    ]

    if any(
        re.search(pattern, normalized)
        for pattern in nigeria_exclusion_patterns
    ):
        return (
            "country_restricted",
            f"The listing explicitly excludes {applicant_country}",
        )

    worldwide = any(
        re.search(pattern, normalized) for pattern in worldwide_patterns
    )
    emea = any(
        re.search(pattern, normalized) for pattern in emea_patterns
    )

    if worldwide and emea:
        return (
            "unknown",
            "Conflicting geographic signals require manual review",
        )

    if worldwide:
        return "worldwide", "Listing explicitly indicates worldwide hiring"

    if emea:
        return "emea", "Listing explicitly indicates EMEA eligibility"

    return (
        "unknown",
        "No clear evidence that applicants from "
        f"{applicant_country} are eligible",
    )


def assess_job(
    title: str,
    description: str | None = None,
    location: str | None = None,
    applicant_country: str = "Nigeria",
) -> JobAssessment:
    score, relevance_reasons = score_job(title, description)
    eligibility, eligibility_reason = classify_eligibility(
        title=title,
        description=description,
        location=location,
        applicant_country=applicant_country,
    )

    return JobAssessment(
        relevance_score=score,
        eligibility=eligibility,
        relevance_reasons=relevance_reasons,
        eligibility_reason=eligibility_reason,
    )
