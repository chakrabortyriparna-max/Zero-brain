"""Slack integration — read channels/messages, post with guardrails."""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional


@dataclass
class SlackChannel:
    id: str
    name: str
    is_private: bool


@dataclass
class SlackMessage:
    ts: str
    user: str
    text: str
    channel: str


def _get_client():
    """Lazy-load authenticated Slack WebClient."""
    from slack_sdk import WebClient

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("SLACK_BOT_TOKEN not set in .env", file=sys.stderr)
        return None
    return WebClient(token=token)


def list_channels() -> List[SlackChannel]:
    client = _get_client()
    if client is None:
        return []
    try:
        resp = client.conversations_list(types="public_channel,private_channel")
    except Exception as e:
        err_str = str(e)
        if "missing_scope" in err_str and "groups:read" in err_str:
            # Fallback: list public channels only
            try:
                resp = client.conversations_list(types="public_channel")
            except Exception as e2:
                print(f"Slack list_channels error: {e2}", file=sys.stderr)
                return []
        else:
            print(f"Slack list_channels error: {e}", file=sys.stderr)
            return []
    out: List[SlackChannel] = []
    for ch in resp.get("channels", []):
        out.append(
            SlackChannel(
                id=ch["id"],
                name=ch["name"],
                is_private=ch.get("is_private", False),
            )
        )
    return out


def get_history(channel_id: str, oldest_ts: Optional[str] = None, limit: int = 100) -> List[SlackMessage]:
    client = _get_client()
    if client is None:
        return []
    try:
        kwargs: dict = {"channel": channel_id, "limit": limit}
        if oldest_ts:
            kwargs["oldest"] = oldest_ts
        resp = client.conversations_history(**kwargs)
        out: List[SlackMessage] = []
        for msg in resp.get("messages", []):
            out.append(
                SlackMessage(
                    ts=msg.get("ts", ""),
                    user=msg.get("user", ""),
                    text=msg.get("text", ""),
                    channel=channel_id,
                )
            )
        return out
    except Exception as e:
        print(f"Slack get_history error: {e}", file=sys.stderr)
        return []


def post_message(channel_id: str, text: str, approved: bool = False) -> Optional[str]:
    """Post a Slack message. Requires explicit approval=True (Advisor guardrail)."""
    if not approved:
        print(
            "Slack post blocked: approval=False. Set approved=True only after explicit user consent.",
            file=sys.stderr,
        )
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat_postMessage(channel=channel_id, text=text)
        return resp.get("ts")
    except Exception as e:
        print(f"Slack post_message error: {e}", file=sys.stderr)
        return None


def resolve_user_name(user_id: str) -> str:
    client = _get_client()
    if client is None:
        return user_id
    try:
        resp = client.users_info(user=user_id)
        return resp.get("user", {}).get("real_name", user_id)
    except Exception:
        return user_id


def format_messages(messages: List[SlackMessage]) -> str:
    if not messages:
        return "_No messages._"
    lines = []
    for m in messages:
        ts_human = ""
        try:
            ts_float = float(m.ts)
            dt = datetime.fromtimestamp(ts_float, tz=timezone(timedelta(hours=5, minutes=30)))
            ts_human = dt.strftime("%Y-%m-%d %H:%M IST")
        except Exception:
            pass
        user_name = resolve_user_name(m.user) if m.user else "bot"
        lines.append(f"**[{ts_human}] {user_name}:** {m.text}")
    return "\n".join(lines)


def format_channels(channels: List[SlackChannel]) -> str:
    if not channels:
        return "_No channels found._"
    lines = [f"- {'#' if not ch.is_private else '🔒'} {ch.name} (`{ch.id}`)" for ch in channels]
    return "\n".join(lines)


def add_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("slack", help="Slack integration commands")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("channels", help="List accessible channels")

    p_unread = sub.add_parser("history", help="Get channel history")
    p_unread.add_argument("channel_id", help="Channel ID (e.g. C123456)")
    p_unread.add_argument(
        "--oldest",
        default=None,
        help="Oldest timestamp to fetch from (Slack ts format)",
    )


def handle_cli(args: argparse.Namespace) -> None:
    if args.command == "channels":
        chs = list_channels()
        print(format_channels(chs))
    elif args.command == "history":
        msgs = get_history(args.channel_id, oldest_ts=args.oldest)
        print(format_messages(msgs))
    else:
        print("Unknown command. Use: channels, history <channel_id>")
