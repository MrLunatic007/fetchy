#!/usr/bin/env python3
"""
Native messaging host for Firefox extension
Receives download requests from browser and forwards to Fetchy
"""

import sys
import json
import struct
import subprocess
import os
from pathlib import Path


def send_message(message):
    """Send message to browser extension"""
    encoded_content = json.dumps(message).encode("utf-8")
    encoded_length = struct.pack("@I", len(encoded_content))
    sys.stdout.buffer.write(encoded_length)
    sys.stdout.buffer.write(encoded_content)
    sys.stdout.buffer.flush()


def read_message():
    """Read message from browser extension"""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length:
        return None

    message_length = struct.unpack("@I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)


def add_download(url, filename=""):
    """Add download to Fetchy via CLI"""
    try:
        # Build command
        cmd = ["fetchy", "add", url]
        if filename:
            cmd.extend(["-o", filename])

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            return {"success": True, "message": "Download added"}
        else:
            return {"success": False, "error": result.stderr}

    except FileNotFoundError:
        return {"success": False, "error": "Fetchy CLI not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_stats():
    """Get download statistics from Fetchy"""
    try:
        result = subprocess.run(
            ["fetchy", "queue"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            # Parse output to count active downloads
            # This is a simple implementation
            return {"success": True, "active": 0, "queued": 0}
        else:
            return {"success": False, "error": "Could not get stats"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def open_fetchy():
    """Open Fetchy GUI"""
    try:
        subprocess.Popen(
            ["fetchy-gui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    """Main message loop"""
    while True:
        message = read_message()

        if message is None:
            break

        action = message.get("action")

        if action == "download":
            url = message.get("url")
            filename = message.get("filename", "")
            response = add_download(url, filename)
            send_message(response)

        elif action == "stats":
            response = get_stats()
            send_message(response)

        elif action == "open":
            response = open_fetchy()
            send_message(response)

        else:
            send_message({"success": False, "error": "Unknown action"})


if __name__ == "__main__":
    main()
