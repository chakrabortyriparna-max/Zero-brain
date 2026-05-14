"""Gmail integration — read + draft only (Advisor level, never send)."""

import argparse
import base64
import os
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    subject: str
    from_addr: str
    to_addr: str
    date: str
    snippet: str
    body_text: str
    labels: List[str]


_CREDENTIALS_PATH = Path("credentials.json")
_TOKEN_PATH = Path(".claude/data/token.json")


def _get_service():
    """Lazy-load authenticated Gmail service."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    creds = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _CREDENTIALS_PATH.exists():
                print(
                    f"Gmail credentials not found: {_CREDENTIALS_PATH}", file=sys.stderr
                )
                print(
                    "Download credentials.json from Google Cloud Console and place it in the project root.",
                    file=sys.stderr,
                )
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        _TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def list_unread(max_results: int = 20) -> List[GmailMessage]:
    service = _get_service()
    if service is None:
        return []
    try:
        results = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread", maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])
        out: List[GmailMessage] = []
        for m in messages:
            msg = get_message(m["id"])
            if msg:
                out.append(msg)
        return out
    except Exception as e:
        print(f"Gmail list_unread error: {e}", file=sys.stderr)
        return []


def get_message(msg_id: str) -> Optional[GmailMessage]:
    service = _get_service()
    if service is None:
        return None
    try:
        raw = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = raw.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        body_text = ""
        parts = payload.get("parts", [payload])
        for part in parts:
            if part.get("mimeType") == "text/plain" and "body" in part:
                data = part["body"].get("data", "")
                if data:
                    body_text += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        return GmailMessage(
            id=raw["id"],
            thread_id=raw["threadId"],
            subject=headers.get("subject", ""),
            from_addr=headers.get("from", ""),
            to_addr=headers.get("to", ""),
            date=headers.get("date", ""),
            snippet=raw.get("snippet", ""),
            body_text=body_text,
            labels=raw.get("labelIds", []),
        )
    except Exception as e:
        print(f"Gmail get_message error: {e}", file=sys.stderr)
        return None


def create_draft(to: str, subject: str, body: str) -> Optional[str]:
    """Create a Gmail draft. Advisor level: draft only, never send."""
    service = _get_service()
    if service is None:
        return None
    try:
        draft_msg = EmailMessage()
        draft_msg["To"] = to
        draft_msg["Subject"] = subject
        draft_msg.set_content(body)
        raw = base64.urlsafe_b64encode(draft_msg.as_bytes()).decode()
        draft = {"message": {"raw": raw}}
        result = service.users().drafts().create(userId="me", body=draft).execute()
        return result.get("id")
    except Exception as e:
        print(f"Gmail create_draft error: {e}", file=sys.stderr)
        return None


def format_messages(messages: List[GmailMessage]) -> str:
    if not messages:
        return "_No unread messages._"
    lines = []
    for m in messages:
        lines.append(
            f"**From:** {m.from_addr}\n"
            f"**Subject:** {m.subject}\n"
            f"**Date:** {m.date}\n"
            f"**Snippet:** {m.snippet}\n"
            f"**Body:** {m.body_text[:500]}{'...' if len(m.body_text) > 500 else ''}\n"
        )
    return "\n---\n".join(lines)


def add_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("gmail", help="Gmail integration commands")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("unread", help="List unread messages")

    p_get = sub.add_parser("get", help="Get a specific message by ID")
    p_get.add_argument("msg_id", help="Gmail message ID")

    p_draft = sub.add_parser("draft", help="Create a draft (Advisor: never sends)")
    p_draft.add_argument("--to", required=True, help="Recipient email")
    p_draft.add_argument("--subject", required=True, help="Subject line")
    p_draft.add_argument("--body", required=True, help="Draft body text")


def handle_cli(args: argparse.Namespace) -> None:
    if args.command == "unread":
        msgs = list_unread()
        print(format_messages(msgs))
    elif args.command == "get":
        msg = get_message(args.msg_id)
        if msg:
            print(format_messages([msg]))
        else:
            print("Message not found or error occurred.")
    elif args.command == "draft":
        draft_id = create_draft(args.to, args.subject, args.body)
        if draft_id:
            print(f"Draft created: {draft_id}")
        else:
            print("Failed to create draft.", file=sys.stderr)
            sys.exit(1)
    else:
        print("Unknown command. Use: unread, get <msg_id>, draft")
