"""
Single-command launcher for the Support Ticket AI system.

Starts:
  1. FastAPI backend on http://127.0.0.1:8080
  2. Streamlit UI on http://localhost:8501

Usage:
    python start.py
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
API_HOST = "127.0.0.1"
API_PORT = 8080
UI_PORT = 8501


def start_api() -> subprocess.Popen:
    print(f"[start] Launching FastAPI on http://{API_HOST}:{API_PORT}")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", API_HOST, "--port", str(API_PORT)],
        cwd=ROOT,
    )


def start_ui() -> subprocess.Popen:
    print(f"[start] Launching Streamlit on http://localhost:{UI_PORT}")
    return subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
            "--server.port", str(UI_PORT),
            "--server.headless", "true",
        ],
        cwd=ROOT,
    )


def main() -> None:
    print("=" * 60)
    print(" Support Ticket AI — starting up")
    print("=" * 60)

    api = start_api()
    time.sleep(3)  # let FastAPI bind the port before Streamlit calls it

    ui = start_ui()
    time.sleep(2)

    print("\n✅ Backend:  http://127.0.0.1:8080/docs")
    print(f"✅ UI:       http://localhost:{UI_PORT}")
    print("\nPress Ctrl+C to stop both services.\n")

    # Optional: auto-open the UI in the default browser
    try:
        webbrowser.open(f"http://localhost:{UI_PORT}")
    except Exception:
        pass

    try:
        api.wait()
        ui.wait()
    except KeyboardInterrupt:
        print("\n[start] Shutting down…")
        api.terminate()
        ui.terminate()
        try:
            api.wait(timeout=5)
            ui.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api.kill()
            ui.kill()
        print("[start] Done.")


if __name__ == "__main__":
    main()