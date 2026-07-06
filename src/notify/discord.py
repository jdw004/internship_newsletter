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


def build_body(
    jobs: list[Job],
    *,
    max_jobs: int = DEFAULT_MAX_JOBS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
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
        remaining_after_item = len(jobs) - shown - 1
        footer = f"\n...and {remaining_after_item} more." if remaining_after_item else ""
        candidate = "\n".join(lines + item)
        if len(candidate) + len(footer) > max_chars:
            break
        lines.extend(item)
        shown += 1

    remaining = len(jobs) - shown
    if remaining:
        footer = f"...and {remaining} more."
        if len("\n".join(lines + [footer])) <= max_chars:
            lines.append(footer)

    return "\n".join(lines)[:DISCORD_CONTENT_LIMIT]


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
    body = build_body(jobs, max_jobs=max_jobs)
    payload: dict[str, Any] = {
        "content": body,
        "allowed_mentions": {"parse": []},
    }
    username = discord_cfg.get("username")
    if username:
        payload["username"] = str(username)

    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        log.error("discord send failed: %s", exc)
        return False

    if 200 <= response.status_code < 300:
        log.info("discord sent (%d jobs)", len(jobs))
        return True

    log.error("discord send failed: HTTP %s %s", response.status_code, response.text[:300])
    return False
