"""
scheduler.py
------------
Schedules the YouTube Shorts automation pipeline using Windows Task Scheduler.

Usage:
    python scheduler.py --install
    python scheduler.py --remove
    python scheduler.py --status
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scheduler")

# Default daily schedule times (24-hour format HH:MM)
DEFAULT_TIMES = [
    ("NaviShorts_Morning", "08:00"),    # 8:00 AM
    ("NaviShorts_Afternoon", "14:00"),  # 2:00 PM
    ("NaviShorts_Night", "20:00"),      # 8:00 PM
]

PYTHON_EXE = sys.executable
PROJECT_DIR = Path(__file__).parent.resolve()
MAIN_PY = PROJECT_DIR / "main.py"


def install_tasks(privacy: str = "public") -> None:
    """Create Windows Task Scheduler jobs for 3x daily automatic posting."""
    logger.info("Installing 3x daily automated YouTube Shorts tasks...")

    for task_name, run_time in DEFAULT_TIMES:
        cmd_args = f'"{MAIN_PY}" --auto --privacy {privacy}'
        
        ps_script = (
            f"$action = New-ScheduledTaskAction -Execute '{PYTHON_EXE}' -Argument '{cmd_args}' -WorkingDirectory '{PROJECT_DIR}'; "
            f"$trigger = New-ScheduledTaskTrigger -Daily -At '{run_time}'; "
            f"$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable; "
            f"Register-ScheduledTask -TaskName '{task_name}' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null"
        )

        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, check=True)
            logger.info("✅ Task created: %s at %s", task_name, run_time)
        except subprocess.CalledProcessError as exc:
            logger.error("❌ Failed to create task %s: %s", task_name, exc.stderr.strip())

    logger.info("\n🎉 All 3 daily tasks installed successfully!")
    logger.info("  1. Morning: 08:00 AM")
    logger.info("  2. Afternoon: 02:00 PM")
    logger.info("  3. Night: 08:00 PM")


def remove_tasks() -> None:
    """Delete the scheduled Windows tasks."""
    for task_name, _ in DEFAULT_TIMES:
        schtasks_cmd = ["schtasks", "/Delete", "/TN", task_name, "/F"]
        try:
            subprocess.run(schtasks_cmd, capture_output=True, text=True, check=True)
            logger.info("🗑️ Task removed: %s", task_name)
        except subprocess.CalledProcessError:
            logger.warning("Task not found or already deleted: %s", task_name)


def check_status() -> None:
    """List status of scheduled tasks."""
    logger.info("Checking status of scheduled tasks...")
    for task_name, run_time in DEFAULT_TIMES:
        schtasks_cmd = ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST"]
        res = subprocess.run(schtasks_cmd, capture_output=True, text=True)
        if res.returncode == 0:
            logger.info("✅ %s (%s) is active.", task_name, run_time)
        else:
            logger.info("❌ %s (%s) is NOT installed.", task_name, run_time)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage YouTube Shorts automation scheduler.")
    parser.add_argument("--install", action="store_true", help="Install 3x daily automated tasks.")
    parser.add_argument("--remove", action="store_true", help="Remove all scheduled tasks.")
    parser.add_argument("--status", action="store_true", help="Check status of scheduled tasks.")
    parser.add_argument("--privacy", choices=["public", "unlisted", "private"], default="public", help="Upload privacy mode.")

    args = parser.parse_args()

    if args.install:
        install_tasks(privacy=args.privacy)
    elif args.remove:
        remove_tasks()
    elif args.status:
        check_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
