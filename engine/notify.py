# -*- coding: utf-8 -*-
"""
EMAIL ALERTS
============
Sends one email when a posting appears that meets every alert rule
(see ALERT_* in profile.py) -- by default: agricultural, in Canada, and
scoring 60+ against the CV.

Runs after scraper.py, both locally and in the GitHub Action.

Credentials come from the environment, never from the repo:

    MAIL_SERVER    smtp.gmail.com          (default)
    MAIL_PORT      465                     (default, implicit TLS)
    MAIL_USERNAME  the sending Gmail address
    MAIL_PASSWORD  a Google **App Password**, not the account password
    MAIL_TO        where the alert goes

Already-alerted postings are recorded in docs/data/alerted.json so the same
job is never emailed twice.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from profile import (ALERT_COUNTRIES, ALERT_MIN_SCORE,        # noqa: E402
                     ALERT_REQUIRE_FACULTY, CANDIDATE)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PUBLIC = os.path.join(ROOT, "docs", "data")
JOBS_FILE = os.path.join(PUBLIC, "jobs.json")
ALERTED_FILE = os.path.join(PUBLIC, "alerted.json")


def _read(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def qualifies(job: dict) -> bool:
    if job.get("score", 0) < ALERT_MIN_SCORE:
        return False
    if ALERT_COUNTRIES and job.get("country") not in ALERT_COUNTRIES:
        return False
    if ALERT_REQUIRE_FACULTY and not job.get("is_faculty"):
        return False
    # the agriculture gate already ran in the matcher, but be explicit
    return bool(job.get("is_agricultural", True))


def find_new(payload: dict, alerted: dict) -> list[dict]:
    return [j for j in payload.get("jobs", [])
            if qualifies(j) and j.get("id") not in alerted]


# --------------------------------------------------------------------------
# Email body
# --------------------------------------------------------------------------
def _plain(jobs: list[dict]) -> str:
    lines = [f"{len(jobs)} new position{'s' if len(jobs) != 1 else ''} "
             f"matching your alert rules "
             f"({'/'.join(ALERT_COUNTRIES)}, match {ALERT_MIN_SCORE}+, agriculture).", ""]
    for j in jobs:
        lines += [
            f"  {j['score']:.0f}/100  {j['title']}",
            f"           {j.get('org') or 'Institution not stated'}"
            f" - {j.get('location') or j.get('country')}",
            f"           {j.get('role')}"
            + ("  |  Ag x Tech" if j.get("synergy") else ""),
            f"           {j.get('url')}",
            "",
        ]
    lines.append("-- Academic Job Radar")
    return "\n".join(lines)


def _html(jobs: list[dict]) -> str:
    rows = []
    for j in jobs:
        tags = []
        if j.get("is_tenure_track"):
            tags.append("Tenure-track")
        elif j.get("is_faculty"):
            tags.append("Faculty line")
        if j.get("synergy"):
            tags.append("Ag &times; Tech")
        tagline = " &middot; ".join(tags)
        ag = ", ".join(j.get("ag_areas", [])[:3])
        rows.append(f"""
        <tr><td style="padding:0 0 14px">
          <table width="100%" cellpadding="0" cellspacing="0" style="
              border:1px solid #e1e0d9;border-radius:12px;border-collapse:separate">
            <tr>
              <td width="62" valign="top" style="padding:16px 0 16px 16px">
                <div style="width:46px;height:46px;border-radius:50%;
                    background:#e8f5ef;color:#0e6d4b;font:700 16px system-ui,sans-serif;
                    text-align:center;line-height:46px">{j['score']:.0f}</div>
              </td>
              <td valign="top" style="padding:16px 16px 16px 8px;font-family:system-ui,-apple-system,'Segoe UI',sans-serif">
                <a href="{j.get('url','')}" style="font-size:15px;font-weight:650;
                   color:#0b0b0b;text-decoration:none">{j.get('title','')}</a>
                <div style="font-size:13px;color:#52514e;margin-top:4px">
                  <b>{j.get('org') or 'Institution not stated'}</b> &middot;
                  {j.get('location') or j.get('country')}</div>
                <div style="font-size:12px;color:#7d827a;margin-top:6px">
                  {j.get('role','')}{(' &middot; ' + tagline) if tagline else ''}</div>
                {f'<div style="font-size:12px;color:#0e6d4b;margin-top:6px">{ag}</div>' if ag else ''}
                <a href="{j.get('url','')}" style="display:inline-block;margin-top:11px;
                   padding:8px 15px;background:#2a78d6;color:#fff;border-radius:8px;
                   font-size:12.5px;font-weight:600;text-decoration:none">View &amp; apply</a>
              </td>
            </tr>
          </table>
        </td></tr>""")

    return f"""<html><body style="margin:0;padding:26px 16px;background:#f7f8f6">
  <table align="center" width="100%" style="max-width:620px" cellpadding="0" cellspacing="0">
    <tr><td style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;padding-bottom:18px">
      <div style="font-size:18px;font-weight:680;color:#0b0b0b;letter-spacing:-.02em">
        {len(jobs)} new agriculture position{'s' if len(jobs) != 1 else ''} in
        {' / '.join(ALERT_COUNTRIES)}</div>
      <div style="font-size:13px;color:#52514e;margin-top:5px">
        Matching {ALERT_MIN_SCORE}+ against your CV. Found
        {datetime.now(timezone.utc).strftime('%d %B %Y')}.</div>
    </td></tr>
    {''.join(rows)}
    <tr><td style="font-family:system-ui,sans-serif;font-size:11.5px;color:#898781;
        padding-top:12px;border-top:1px solid #e1e0d9">
      Academic Job Radar &middot; alert rules live in <code>engine/profile.py</code>
    </td></tr>
  </table></body></html>"""


# --------------------------------------------------------------------------
def send(jobs: list[dict]) -> bool:
    server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("MAIL_PORT", "465"))
    user = os.environ.get("MAIL_USERNAME", "")
    password = os.environ.get("MAIL_PASSWORD", "")
    to = os.environ.get("MAIL_TO", "")

    if not (user and password and to):
        print("  Mail credentials not set (MAIL_USERNAME / MAIL_PASSWORD / MAIL_TO)"
              " -- skipping the email, everything else still ran.")
        return False

    n = len(jobs)
    top = max(j["score"] for j in jobs)
    msg = EmailMessage()
    msg["Subject"] = (f"{n} new agriculture position{'s' if n != 1 else ''} in "
                      f"{'/'.join(ALERT_COUNTRIES)} - top match {top:.0f}/100")
    msg["From"] = formataddr(("Academic Job Radar", user))
    msg["To"] = to
    msg.set_content(_plain(jobs))
    msg.add_alternative(_html(jobs), subtype="html")

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(server, port, context=ctx, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(server, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)
    print(f"  Emailed {n} position(s) to {to}")
    return True


def main() -> int:
    payload = _read(JOBS_FILE, None)
    if not payload:
        print("No jobs.json -- run scraper.py first.")
        return 1

    alerted = _read(ALERTED_FILE, {})
    fresh = find_new(payload, alerted)
    rule = (f"{'/'.join(ALERT_COUNTRIES) or 'anywhere'}, match {ALERT_MIN_SCORE}+"
            f"{', faculty only' if ALERT_REQUIRE_FACULTY else ''}")
    print(f"Alert rule: {rule}")
    print(f"  {len(fresh)} posting(s) newly qualify")

    if not fresh:
        return 0

    fresh.sort(key=lambda j: -j["score"])
    for j in fresh:
        print(f"    {j['score']:5.1f}  {j['title'][:60]}  ({j.get('org','')[:30]})")

    sent = send(fresh)
    if sent:
        now = datetime.now(timezone.utc).isoformat()
        for j in fresh:
            alerted[j["id"]] = now
        os.makedirs(PUBLIC, exist_ok=True)
        with open(ALERTED_FILE, "w", encoding="utf-8") as fh:
            json.dump(alerted, fh, indent=1)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
