import json
import os
import re
from datetime import datetime
from django.conf import settings


def get_terminal_logs(lines=100):
    """
    Reads the last N lines from the webnexus.log file.
    Returns a list of strings.
    """
    log_path = os.path.join(settings.BASE_DIR, "logs", "webnexus.log")
    if not os.path.exists(log_path):
        return [f"LOG_NOT_FOUND: {log_path}"]

    try:
        with open(log_path, "r") as f:
            # Efficiently read last N lines
            # For simplicity in this env, we'll just read all and slice
            # In high-load prod, we'd use a more efficient tail implementation
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:]]
    except Exception as e:
        return [f"LOG_READ_ERROR: {str(e)}"]


def parse_tactical_telemetry(max_entries=500):
    """
    Parses the JSON-formatted webnexus_full.log to extract operational intel.
    Returns a dict with heatmap data, active agents, and app stats.
    """
    log_path = os.path.join(settings.BASE_DIR, "logs", "webnexus_full.log")
    data = {"heatmap": [], "agents": {}, "app_hits": {}, "errors": []}

    if not os.path.exists(log_path):
        return data

    # TACTICAL_SCRAPER: Patterns to recover coordinates from raw text
    lat_pattern = re.compile(r"(?:lat|Lat)[:=]\s*([-+]?\d*\.\d+|\d+)")
    lon_pattern = re.compile(r"(?:lon|Lon)[:=]\s*([-+]?\d*\.\d+|\d+)")

    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
            # Process newest first
            for line in reversed(lines[-max_entries:]):
                try:
                    entry = json.loads(line)
                    msg = entry.get("message", "")
                    user = entry.get("user", "ANONYMOUS")
                    timestamp = entry.get("timestamp")

                    # 1. Extract GPS for Heatmap
                    # We look for lat/lon in the entry (passed via 'extra' in logger)
                    lat = entry.get("lat")
                    lon = entry.get("lon")

                    # SIGNAL_RECOVERY: If structured keys are missing, scrape the message
                    if not lat or not lon:
                        lat_match = lat_pattern.search(msg)
                        lon_match = lon_pattern.search(msg)
                        if lat_match and lon_match:
                            lat = lat_match.group(1)
                            lon = lon_match.group(1)

                    if lat and lon:
                        try:
                            data["heatmap"].append([float(lat), float(lon)])
                        except (ValueError, TypeError):
                            pass

                    # 2. Track Agent Activity
                    if user != "ANONYMOUS" and user not in data["agents"]:
                        data["agents"][user] = {
                            "last_seen": timestamp,
                            "last_action": msg[:50] + "..." if len(msg) > 50 else msg,
                            "ip": entry.get("ip"),
                        }

                    # 3. App Hits (based on path)
                    path = entry.get("path", "UNKNOWN")
                    app = (
                        path.split("/")[1]
                        if "/" in path and len(path.split("/")) > 1
                        else "root"
                    )
                    data["app_hits"][app] = data["app_hits"].get(app, 0) + 1

                    # 4. Error Tracking
                    if entry.get("level") in ["ERROR", "CRITICAL"]:
                        data["errors"].append(
                            {"timestamp": timestamp, "user": user, "message": msg}
                        )

                except (json.JSONDecodeError, ValueError):
                    continue

    except Exception as e:
        print(f"TELEMETRY_PARSE_CRITICAL: {str(e)}")

    return data
