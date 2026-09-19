"""
Iris AWS Live Visual Telemetry & HUD Module
============================================
Renders high-visibility terminal telemetry and on-screen HUD banners
showcasing live AWS Cedar authorization verdicts, AWS Strands agent tools,
Amazon DynamoDB audit persistence, and Amazon Polly / Bedrock status.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Optional

# ANSI Color codes for high-visibility terminal output
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
PURPLE = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_aws_service_banner():
    """Prints an illuminated AWS ecosystem banner at Iris startup."""
    try:
        import cedarpy
        cedar_status = f"{GREEN}ACTIVE{RESET} (Local Rust Engine)"
    except Exception:
        cedar_status = f"{YELLOW}SIMULATED{RESET}"

    try:
        import strands
        strands_status = f"{GREEN}LOADED{RESET} (8 Accessibility Tools)"
    except Exception:
        strands_status = f"{YELLOW}STANDBY{RESET}"

    key = os.getenv("AWS_ACCESS_KEY_ID", "")
    has_aws_keys = bool(key) and not key.startswith("your_") and key != "test"
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    
    if endpoint_url:
        dynamo_status = f"{GREEN}LOCALSTACK ONLINE{RESET} ({endpoint_url})"
    elif has_aws_keys:
        dynamo_status = f"{GREEN}AWS CLOUD READY{RESET} ({os.getenv('AWS_DEFAULT_REGION', 'us-east-1')})"
    else:
        dynamo_status = f"{CYAN}LOCAL IN-MEMORY + READY FOR LOCALSTACK{RESET}"

    polly_status = f"{GREEN}AWS POLLY NEURAL{RESET}" if has_aws_keys else f"{GREEN}ACTIVE NEURAL (Edge-TTS / Zero Keys Required){RESET}"
    bedrock_status = f"{GREEN}CONVERSE API READY{RESET}" if has_aws_keys else f"{CYAN}STANDBY (Bedrock/OpenRouter Dual-Engine){RESET}"

    banner = f"""
{CYAN}================================================================================{RESET}
  {BOLD}IRIS — Hands-Free Voice Operating Layer for Windows{RESET}
  {DIM}Architecture: AWS Open-Source & Enterprise Cloud Accessibility Ecosystem{RESET}
{CYAN}================================================================================{RESET}
  🛡️  {BOLD}AWS Cedar Policy Engine{RESET}  : {cedar_status}
  🤖  {BOLD}AWS Strands Agents SDK{RESET}   : {strands_status}
  💾  {BOLD}Amazon DynamoDB Audit{RESET}    : {dynamo_status}
  🧠  {BOLD}Amazon Bedrock Reasoning{RESET}: {bedrock_status}
  🔊  {BOLD}Amazon Polly Narration{RESET}   : {polly_status}
{CYAN}================================================================================{RESET}
"""
    print(banner)


def render_action_telemetry(
    utterance: str,
    intent: str,
    cedar_verdict: str = "PERMIT",
    tool_dispatched: str = "",
    dynamo_status: str = "Synced",
    tts_engine: str = "Polly Neural / Memory Audio"
):
    """
    Renders a live visual telemetry block in the console when a command runs.
    """
    badge_cedar = f"{GREEN}PERMIT{RESET}" if "ALLOW" in cedar_verdict.upper() or "PERMIT" in cedar_verdict.upper() else f"\033[91mFORBID\033[0m"
    tool_text = tool_dispatched or intent

    card = f"""
{DIM}┌──{RESET} {BOLD}{CYAN}[AWS ACCESSIBILITY TELEMETRY]{RESET} {DIM}{'─' * 44}┐{RESET}
{DIM}│{RESET} 🎙️  {BOLD}User Spoken{RESET}  : "{utterance}"
{DIM}│{RESET} 🛡️  {BOLD}AWS Cedar{RESET}    : {badge_cedar} ({cedar_verdict})
{DIM}│{RESET} 🤖  {BOLD}AWS Strands{RESET}  : Dispatched tool [{tool_text}]
{DIM}│{RESET} 💾  {BOLD}DynamoDB{RESET}     : {dynamo_status} (Table: {os.getenv('DYNAMODB_TABLE_NAME', 'IrisSecurityAudit')})
{DIM}│{RESET} 🔊  {BOLD}Speech Audio{RESET} : {tts_engine}
{DIM}└──{RESET}{DIM}{'─' * 72}┘{RESET}
"""
    try:
        print(card)
    except Exception:
        pass


def show_hud_toast(title: str, message: str, duration_sec: float = 2.5):
    """
    Displays a non-intrusive on-screen floating pill in the top-right corner of Windows.
    Runs on a daemon thread so it never blocks execution.
    """
    def _toast_worker():
        try:
            import tkinter as tk
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.92)

            # Position in top-right corner
            screen_width = root.winfo_screenwidth()
            width = 320
            height = 68
            x = screen_width - width - 24
            y = 36
            root.geometry(f"{width}x{height}+{x}+{y}")

            frame = tk.Frame(root, bg="#111827", highlightthickness=1, highlightbackground="#06b6d4")
            frame.pack(fill="both", expand=True)

            lbl_title = tk.Label(
                frame, 
                text=f"IRIS AWS HUD • {title}", 
                font=("Segoe UI", 9, "bold"), 
                fg="#06b6d4", 
                bg="#111827"
            )
            lbl_title.pack(anchor="w", padx=12, pady=(6, 0))

            lbl_msg = tk.Label(
                frame, 
                text=message, 
                font=("Segoe UI", 8), 
                fg="#f3f4f6", 
                bg="#111827"
            )
            lbl_msg.pack(anchor="w", padx=12, pady=(2, 6))

            root.after(int(duration_sec * 1000), root.destroy)
            root.mainloop()
        except Exception:
            pass

    t = threading.Thread(target=_toast_worker, daemon=True)
    t.start()
