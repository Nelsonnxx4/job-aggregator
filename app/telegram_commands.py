import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import SessionLocal
from app.models import IngestionRun, Job
from app.services.notifications import _send_message

logger = logging.getLogger("job_aggregator.telegram_commands")

FETCH_COMMAND = "fetch"
HELP_COMMAND = "help"
START_COMMAND = "start"
VERIFY_COMMAND = "verify"


def _clean_text(value: str | None, limit: int = 120) -> str:
    return " ".join((value or "").split())[:limit]


def _parse_command(text: str) -> tuple[str, str]:
    command_text, _, argument = text.strip().partition(" ")
    command = command_text.split("@", 1)[0].lstrip("/").casefold()
    return command, argument.strip()


def _verify_job(db: Session, argument: str, settings: Settings) -> str:
    if not argument:
        return "Usage: /verify <job ID or exact listing URL>"

    if argument.isdecimal() and len(argument) <= 18:
        job = db.get(Job, int(argument))
    elif len(argument) <= 2048:
        job = db.scalar(select(Job).where(Job.url == argument))
    else:
        job = None

    if job is None:
        return (
            "I couldn't find that listing in the aggregator's database. "
            "Use /fetch first, or check the employer's official careers site. "
            "Never pay fees or share passwords to apply."
        )

    source_name = (
        _clean_text(job.source.name, 100) if job.source is not None else "unknown"
    )
    parsed_url = urlparse(job.url)
    fields_complete = bool(
        _clean_text(job.title)
        and _clean_text(job.company)
        and parsed_url.hostname
        and parsed_url.scheme in {"http", "https"}
        and not parsed_url.username
        and not parsed_url.password
    )
    secure_link = parsed_url.scheme == "https" and bool(parsed_url.hostname)
    fresh = False
    if job.posted_at is not None:
        posted_at = job.posted_at
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        fresh = posted_at >= (
            datetime.now(timezone.utc)
            - timedelta(days=settings.ingestion_freshness_days)
        )

    checks = [
        f"Imported source: {source_name}",
        f"Required listing fields: {'present' if fields_complete else 'incomplete'}",
        f"Application link: {'HTTPS' if secure_link else 'not HTTPS'}",
        f"Posted date: {'within configured freshness window' if fresh else 'missing or old'}",
        (
            "Duplicate: yes"
            if job.duplicate_of_id is not None
            else "Duplicate: no known match"
        ),
    ]
    assessment = (
        "No obvious data/link warning found."
        if fields_complete and secure_link and fresh and job.duplicate_of_id is None
        else "One or more checks need manual review."
    )
    return (
        f"Listing #{job.id}: {_clean_text(job.title)} — "
        f"{_clean_text(job.company)}\n"
        f"{assessment}\n"
        + "\n".join(checks)
        + "\nThis is not proof the employer or vacancy is genuine. "
        "Confirm the role on the employer's official careers site before "
        "sharing personal information."
    )


def handle_command(
    db: Session,
    text: str,
    settings: Settings,
    *,
    fetch_jobs: Callable[[], str],
) -> str:
    command, argument = _parse_command(text)
    if command in {HELP_COMMAND, START_COMMAND}:
        return (
            "Available commands:\n"
            "/fetch — fetch listings now and show newly added jobs\n"
            "/verify <job ID or exact listing URL> — check a saved listing\n"
            "/help — show this message"
        )
    if command == FETCH_COMMAND:
        return fetch_jobs()
    if command == VERIFY_COMMAND:
        return _verify_job(db, argument, settings)
    return "Unknown command. Send /help to see available commands."


def _fetch_jobs(settings: Settings) -> str:
    from app.worker import run_cycle

    with SessionLocal() as db:
        previous_job_id = db.scalar(select(func.max(Job.id)) )
        previous_run_id = db.scalar(select(func.max(IngestionRun.id)))

    run_cycle(dispatch_notifications=False)

    with SessionLocal() as db:
        statement = select(Job)
        if previous_job_id is not None:
            statement = statement.where(Job.id > previous_job_id)
        new_jobs = list(
            db.scalars(statement.order_by(Job.id.desc()).limit(4)).all()
        )
        total_new = db.scalar(select(func.count()).select_from(Job))
        if previous_job_id is not None:
            total_new = db.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.id > previous_job_id)
            )
        failed_runs = db.scalars(
            select(IngestionRun).where(
                IngestionRun.id > (previous_run_id or 0),
                IngestionRun.status == "failed",
            )
        ).all()

        if not new_jobs:
            message = "Fetch finished. No new jobs were added."
        else:
            message = f"Fetch finished. {total_new} new job(s) added:"
            for job in new_jobs:
                source_name = (
                    _clean_text(job.source.name, 60)
                    if job.source is not None
                    else "unknown source"
                )
                safe_url = _clean_text(job.url, 500)
                message += (
                    f"\n\n#{job.id} {_clean_text(job.title)} — "
                    f"{_clean_text(job.company)} ({source_name})"
                    f"\n/verify {job.id}\n{safe_url}"
                )
            if total_new is not None and total_new > len(new_jobs):
                message += f"\n\nShowing {len(new_jobs)} of {total_new} new jobs."

        if failed_runs:
            failed_sources = ", ".join(
                _clean_text(run.source_name, 60) for run in failed_runs[:4]
            )
            message += (
                f"\n\nSome sources failed during this fetch: {failed_sources}. "
                "Check the worker log for details."
            )
        return message


def _send_reply(
    client: httpx.Client,
    settings: Settings,
    chat_id: str,
    text: str,
) -> None:
    sent, _, error, _ = _send_message(
        client,
        token=settings.telegram_bot_token or "",
        chat_id=chat_id,
        text=text[:4000],
        max_attempts=settings.telegram_retry_attempts,
        backoff_seconds=settings.telegram_retry_backoff_seconds,
    )
    if not sent:
        logger.warning("Telegram command reply failed (%s)", error)


def run_telegram_command_listener(
    settings: Settings,
    stop_event: threading.Event,
) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram commands disabled: bot token or chat ID is missing")
        return

    endpoint = (
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
    )
    offset: int | None = None
    logger.info("Telegram command listener started")

    with httpx.Client(timeout=35.0) as client:
        while not stop_event.is_set():
            params: dict[str, int] = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset
            try:
                response = client.get(endpoint, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("ok") is not True:
                    logger.warning("Telegram returned an invalid updates response")
                    stop_event.wait(5)
                    continue
                updates = payload.get("result")
                if not isinstance(updates, list):
                    logger.warning("Telegram updates response had no result list")
                    stop_event.wait(5)
                    continue
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    "Telegram command polling failed (%s)", type(exc).__name__
                )
                stop_event.wait(5)
                continue

            for update in updates:
                if not isinstance(update, dict):
                    continue
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1

                message = update.get("message")
                if not isinstance(message, dict):
                    continue
                chat = message.get("chat")
                if (
                    not isinstance(chat, dict)
                    or str(chat.get("id")) != settings.telegram_chat_id
                ):
                    continue
                text = message.get("text")
                if not isinstance(text, str) or not text.startswith("/"):
                    continue

                try:
                    with SessionLocal() as db:
                        reply = handle_command(
                            db,
                            text,
                            settings,
                            fetch_jobs=lambda: _fetch_jobs(settings),
                        )
                except Exception:
                    logger.exception("Telegram command handler failed")
                    reply = "That command failed. Check the worker log for details."
                _send_reply(
                    client,
                    settings,
                    settings.telegram_chat_id,
                    reply,
                )

    logger.info("Telegram command listener stopped")
