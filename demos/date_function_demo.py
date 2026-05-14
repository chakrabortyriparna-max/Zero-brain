"""
Zero Brain — Date & Timezone Demo
Shows how IST (UTC+5:30) handling works without exposing real data.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def now_ist() -> str:
    """Return current timestamp in IST (UTC+5:30)."""
    return datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()


def format_meeting_time(utc_iso: str) -> str:
    """Convert a UTC ISO timestamp to IST display format."""
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    ist = dt.astimezone(ZoneInfo("Asia/Kolkata"))
    return ist.strftime("%Y-%m-%d %H:%M IST")


if __name__ == "__main__":
    print("=== Zero Brain — Date Demo ===")
    print(f"Current IST time   : {now_ist()}")
    print(f"Sample UTC input   : 2026-05-14T09:00:00Z")
    print(f"Converted to IST   : {format_meeting_time('2026-05-14T09:00:00Z')}")
    print("================================")
