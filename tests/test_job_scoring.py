
import pytest

from app.services.job_scoring import (
    assess_job,
    classify_eligibility,
    score_job,
)


@pytest.mark.parametrize(
    "title,description",
    [
        (
            "Junior Frontend Developer",
            "Build interfaces using React, TypeScript, HTML and CSS.",
        ),
        (
            "Full Stack Engineer",
            "Develop web applications using React, Node.js and PostgreSQL.",
        ),
        (
            "Frontend Engineering Intern",
            "Work with JavaScript, React and responsive web design.",
        ),
    ],
)
def test_relevant_web_development_jobs_score_above_zero(
    title: str, description: str
) -> None:
    score, reasons = score_job(title, description)

    assert 0 < score <= 100
    assert reasons


def test_react_typescript_frontend_job_scores_highly() -> None:
    score, _ = score_job(
        "Frontend Developer",
        "Build applications with React and TypeScript.",
    )

    assert score >= 50


@pytest.mark.parametrize(
    "description,matched_skill",
    [
        ("WCAG 2.2 AA compliance", "wcag"),
        ("Accessibility and inclusive design", "accessibility"),
        ("a11y testing", "accessibility"),
        ("ARIA labels and roles", "aria"),
        ("Semantic HTML", "semantic html"),
        ("Responsive web design", "responsive design"),
        ("Tailwind CSS", "tailwind css"),
        ("SCSS stylesheets", "sass"),
        ("React Native applications", "react native"),
        ("TanStack Query", "tanstack query"),
        ("Redux Toolkit (RTK)", "redux toolkit"),
        ("React Testing Library", "react testing library"),
        ("Jest and Vitest", "jest"),
        ("Jest and Vitest", "vitest"),
        ("Vite build tooling", "vite"),
        ("UI/UX wireframing", "ui ux"),
        ("CI/CD pipelines", "ci cd"),
        ("Continuous integration and delivery", "ci cd"),
        ("Claude Code", "claude"),
        ("Node.js services", "nodejs"),
        ("Express.js backend", "express"),
        ("React Context API", "context api"),
        ("Zustand state management", "zustand"),
        ("Git version control", "git"),
        ("GraphQL APIs", "graphql"),
        ("Sass (SCSS) stylesheets", "sass"),
    ],
)
def test_frontend_and_accessibility_skills_are_matched(
    description: str,
    matched_skill: str,
) -> None:
    score, reasons = score_job("Frontend Engineer", description)

    assert score > 0
    matching_reason = next(
        reason
        for reason in reasons
        if reason.startswith("Matching technologies:")
    )
    assert matched_skill in matching_reason


def test_unrelated_job_scores_low() -> None:
    score, _ = score_job(
        "Registered Nurse",
        "Provide patient care in a hospital.",
    )

    assert score <= 10


def test_senior_title_receives_penalty() -> None:
    junior_score, _ = score_job(
        "Frontend Developer",
        "Build web applications using React.",
    )
    senior_score, reasons = score_job(
        "Senior Frontend Developer",
        "Build web applications using React.",
    )

    assert senior_score < junior_score
    assert any("senior" in reason.lower() for reason in reasons)


def test_score_never_exceeds_100() -> None:
    score, _ = score_job(
        "Junior Full Stack Frontend Software Engineer",
        "React TypeScript JavaScript HTML CSS Next.js Node.js "
        "Python FastAPI Vue Angular SQL PostgreSQL REST APIs.",
    )

    assert 0 <= score <= 100


def test_explicit_worldwide_eligibility() -> None:
    eligibility, reason = classify_eligibility(
        title="Frontend Developer",
        description="We welcome applicants from worldwide locations.",
    )

    assert eligibility == "worldwide"
    assert reason


def test_explicit_emea_eligibility() -> None:
    eligibility, _ = classify_eligibility(
        title="Full Stack Developer",
        description="This remote role is open to candidates across EMEA.",
    )

    assert eligibility == "emea"


def test_remote_alone_does_not_prove_eligibility() -> None:
    eligibility, _ = classify_eligibility(
        title="Remote Frontend Developer",
        description="Work remotely with our engineering team.",
    )

    assert eligibility == "unknown"


def test_explicit_nigeria_exclusion() -> None:
    eligibility, reason = classify_eligibility(
        title="Remote Developer",
        description="We are not hiring applicants from Nigeria.",
    )

    assert eligibility == "country_restricted"
    assert reason


def test_ambiguous_eligibility_remains_unknown() -> None:
    eligibility, _ = classify_eligibility(
        title="Software Engineer",
        description="Remote position. Some geographic restrictions may apply.",
    )

    assert eligibility == "unknown"


def test_assess_job_returns_both_assessments() -> None:
    result = assess_job(
        title="Junior Frontend Developer",
        description="React and TypeScript. Applicants worldwide are welcome.",
    )

    assert result.relevance_score > 0
    assert result.eligibility == "worldwide"
    assert result.relevance_reasons
    assert result.eligibility_reason
