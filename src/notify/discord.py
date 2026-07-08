"""Discord webhook digest."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

from ..models import Job

log = logging.getLogger(__name__)

DISCORD_CONTENT_LIMIT = 2000
DEFAULT_MAX_CHARS = 1900
DEFAULT_MAX_JOBS = 15


def _one_line(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _build_body_for_jobs(
    jobs: list[Job],
    *,
    max_jobs: int = DEFAULT_MAX_JOBS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[str, int]:
    max_jobs = max(1, max_jobs)
    max_chars = min(max_chars, DISCORD_CONTENT_LIMIT)
    lines = [f"**{len(jobs)} new internship posting(s)**", ""]
    shown = 0

    for job in sorted(jobs, key=lambda x: (x.company.lower(), x.title.lower())):
        if shown >= max_jobs:
            break
        company = _one_line(job.company, 80)
        title = _one_line(job.title, 140)
        location = _one_line(job.location_str, 120)
        location_text = f" [{location}]" if location else ""
        item = [
            f"- {company} - {title}{location_text}",
            f"  <{job.url}>",
        ]
        candidate = "\n".join(lines + item)
        if len(candidate) > max_chars:
            break
        lines.extend(item)
        shown += 1

    return "\n".join(lines)[:DISCORD_CONTENT_LIMIT], shown


def build_body(
    jobs: list[Job],
    *,
    max_jobs: int = DEFAULT_MAX_JOBS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """Compatibility wrapper that returns the first digest chunk."""
    bodies = build_bodies(jobs, max_jobs=max_jobs, max_chars=max_chars)
    return bodies[0] if bodies else ""


def build_bodies(
    jobs: list[Job],
    *,
    max_jobs: int = DEFAULT_MAX_JOBS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[str]:
    """Split a digest into multiple Discord-sized messages."""
    sorted_jobs = sorted(jobs, key=lambda x: (x.company.lower(), x.title.lower()))
    bodies: list[str] = []
    remaining = list(sorted_jobs)
    while remaining:
        body, consumed = _build_body_for_jobs(
            remaining, max_jobs=max_jobs, max_chars=max_chars
        )
        if consumed <= 0:
            body, consumed = _build_body_for_jobs(
                remaining[:1], max_jobs=max_jobs, max_chars=max_chars
            )
            consumed = 1
        bodies.append(body)
        remaining = remaining[consumed:]
    return bodies


def _int_cfg(cfg: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def send_discord(jobs: list[Job], secrets: dict[str, str], discord_cfg: dict[str, Any]) -> bool:
    """Send the digest to a Discord channel webhook."""
    webhook_url = secrets.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log.warning("discord skipped: DISCORD_WEBHOOK_URL not set")
        return False
    if not jobs:
        log.info("discord skipped: no jobs to send")
        return False

    max_jobs = _int_cfg(discord_cfg, "max_jobs", DEFAULT_MAX_JOBS)
    timeout = max(1, _int_cfg(discord_cfg, "timeout_seconds", 10))
    bodies = build_bodies(jobs, max_jobs=max_jobs)
    username = discord_cfg.get("username")
    sent_any = False

    for idx, body in enumerate(bodies, 1):
        payload: dict[str, Any] = {
            "content": body,
            "allowed_mentions": {"parse": []},
        }
        if username:
            payload["username"] = str(username)

        try:
            response = requests.post(webhook_url, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            log.error("discord send failed on chunk %d/%d: %s", idx, len(bodies), exc)
            return False

        if 200 <= response.status_code < 300:
            sent_any = True
            continue

        log.error(
            "discord send failed on chunk %d/%d: HTTP %s %s",
            idx,
            len(bodies),
            response.status_code,
            response.text[:300],
        )
        return False

    if sent_any:
        log.info("discord sent (%d jobs in %d chunk(s))", len(jobs), len(bodies))
    return sent_any
