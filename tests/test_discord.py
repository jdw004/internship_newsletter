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
    assert "Acme - SWE Intern [New York, NY] [Link](https://example.com/Acme)" in body
    assert "Beta - SWE Intern [Link](https://example.com/Beta)" in body


def test_build_body_caps_job_count():
    jobs = [_job(f"Company{i}") for i in range(5)]
    body = D.build_body(jobs, max_jobs=2)
    assert body.count("https://example.com/") == 2
    assert "...and" not in body


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
    assert "https://example.com/jobs/" in body


def test_build_bodies_splits_oversized_digest():
    jobs = [
        _job(
            f"Company{i}",
            title="Software Engineering Internship " * 10,
            url=f"https://example.com/jobs/{i}",
        )
        for i in range(8)
    ]
    bodies = D.build_bodies(jobs, max_jobs=8, max_chars=350)
    assert len(bodies) > 1
    assert all(len(body) <= D.DISCORD_CONTENT_LIMIT for body in bodies)
    assert sum(body.count("https://example.com/jobs/") for body in bodies) == 8


def test_send_discord_skips_without_webhook():
    assert not D.send_discord([_job("Acme")], {}, {})


def test_send_discord_uses_configured_username(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout

        class Response:
            status_code = 204
            text = ""

        return Response()

    monkeypatch.setattr(D.requests, "post", fake_post)

    assert D.send_discord(
        [_job("Acme")],
        {"DISCORD_WEBHOOK_URL": "https://example.com/webhook"},
        {"username": "internship bot"},
    )
    assert captured["json"]["username"] == "internship bot"
    assert captured["json"]["flags"] == D.SUPPRESS_EMBEDS_FLAG


def test_send_discord_posts_multiple_chunks(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))

        class Response:
            status_code = 204
            text = ""

        return Response()

    monkeypatch.setattr(D.requests, "post", fake_post)
    monkeypatch.setattr(D, "build_bodies", lambda jobs, **kw: ["chunk-1", "chunk-2", "chunk-3"])

    assert D.send_discord(
        [_job("Acme")],
        {"DISCORD_WEBHOOK_URL": "https://example.com/webhook"},
        {"username": "internship bot", "timeout_seconds": 7},
    )
    assert len(calls) == 3
    assert all(call[0] == "https://example.com/webhook" for call in calls)
    assert [call[1]["content"] for call in calls] == ["chunk-1", "chunk-2", "chunk-3"]
    assert all(call[1]["username"] == "internship bot" for call in calls)
    assert all(call[1]["flags"] == D.SUPPRESS_EMBEDS_FLAG for call in calls)
    assert all(call[2] == 7 for call in calls)
