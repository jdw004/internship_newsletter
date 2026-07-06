"""Discord webhook notification formatting."""

from src.models import Job
from src.notify import discord as D


def _job(company, title="SWE Intern", url=None, locations=None):
    return Job(
        company=company,
        title=title,
        url=url or f"https://example.com/{company}",
        locations=locations or [],
        category="swe",
    )


def test_build_body_includes_jobs_and_urls():
    jobs = [_job("Acme", locations=["New York, NY"]), _job("Beta")]
    body = D.build_body(jobs)
    assert "**2 new internship posting(s)**" in body
    assert "Acme - SWE Intern [New York, NY]" in body
    assert "https://example.com/Acme" in body
    assert "Beta - SWE Intern" in body


def test_build_body_caps_job_count():
    jobs = [_job(f"Company{i}") for i in range(5)]
    body = D.build_body(jobs, max_jobs=2)
    assert body.count("https://example.com/") == 2
    assert "...and 3 more." in body


def test_build_body_stays_under_discord_limit():
    jobs = [
        _job(
            f"Company{i}",
            title="Software Engineering Internship " * 20,
            url=f"https://example.com/jobs/{i}",
        )
        for i in range(30)
    ]
    body = D.build_body(jobs, max_jobs=30, max_chars=400)
    assert len(body) <= D.DISCORD_CONTENT_LIMIT
    assert "...and" in body


def test_send_discord_skips_without_webhook():
    assert not D.send_discord([_job("Acme")], {}, {})
