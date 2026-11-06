"""
PRAVISION — Production Service Watchdog & Health Supervisor
Manages and monitors:
  1. FastAPI Backend Daemon (127.0.0.1:8000)
  2. Cloudflare Persistent Named Tunnel (pravision-tunnel / 94e94e3b-360e-4a9e-abff-99753d401df8)

Features:
  - Automatic restart recovery on unexpected process termination.
  - Active liveness polling via http://127.0.0.1:8000/api/storage/status.
  - Graceful termination handling for clean process cleanup.
  - Audit logging with timestamps.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
PYTHON_EXE = ROOT_DIR / "venv" / "Scripts" / "python.exe"

import shutil
_system_cloudflared = shutil.which("cloudflared")
_wrangler_cloudflared = Path(os.environ.get("APPDATA", "")) / "xdg.config" / ".wrangler" / "cloudflared" / "2026.10.7" / "cloudflared.exe"
CLOUDFLARED_EXE = Path(_system_cloudflared) if _system_cloudflared else _wrangler_cloudflared
TUNNEL_TOKEN_FILE = ROOT_DIR / "backend" / ".tunnel_token"
LOG_DIR = ROOT_DIR / "backend" / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [WATCHDOG] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "watchdog.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("pravision.watchdog")

CHECK_INTERVAL = 15  # seconds
MAX_CONSECUTIVE_FAILURES = 6  # 90 seconds grace period for remote database startup and migrations

backend_proc = None
tunnel_proc = None
running = True


def start_backend():
    global backend_proc
    # Generate / synchronize deployment build metadata before starting backend
    try:
        sys.path.insert(0, str(ROOT_DIR / "backend"))
        from app.build_identity import generate_build_metadata, resolve_deployment_identity
        meta = generate_build_metadata(output_dir=ROOT_DIR / "backend" / "app")
        ident = resolve_deployment_identity()
        logger.info(f"Build metadata synchronized: commit_sha={ident.commit_sha} status={ident.identity_status} agree={ident.sources_agree}")
    except Exception as e:
        logger.warning(f"Could not pre-generate build metadata: {e}")

    logger.info("Starting FastAPI backend process on 127.0.0.1:8000...")
    cmd = [
        str(PYTHON_EXE),
        "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--app-dir", str(ROOT_DIR / "backend")
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    backend_log = open(LOG_DIR / "backend.log", "a", encoding="utf-8")
    backend_proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=backend_log,
        stderr=backend_log
    )
    logger.info(f"Backend started with PID {backend_proc.pid}.")


def start_tunnel():
    global tunnel_proc
    token = None
    if TUNNEL_TOKEN_FILE.exists():
        token = TUNNEL_TOKEN_FILE.read_text(encoding="utf-8").strip()

    if token and CLOUDFLARED_EXE.exists():
        logger.info("Starting persistent Cloudflare Tunnel (pravision-tunnel: 94e94e3b-360e-4a9e-abff-99753d401df8)...")
        cmd = [
            str(CLOUDFLARED_EXE),
            "tunnel", "run",
            "--token", token
        ]
        tunnel_log = open(LOG_DIR / "tunnel.log", "a", encoding="utf-8")
        tunnel_proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=tunnel_log,
            stderr=tunnel_log
        )
        logger.info(f"Tunnel process started with PID {tunnel_proc.pid}.")
    else:
        logger.warning("Tunnel token file or cloudflared executable not found. Running in local-only mode.")


def check_backend_liveness() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/storage/status", headers={"User-Agent": "PRAVISION-Watchdog/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def stop_all():
    global backend_proc, tunnel_proc
    logger.info("Stopping supervised processes...")
    if backend_proc and backend_proc.poll() is None:
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
    if tunnel_proc and tunnel_proc.poll() is None:
        tunnel_proc.terminate()
        try:
            tunnel_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tunnel_proc.kill()
    logger.info("All supervised processes stopped.")


def sig_handler(sig, frame):
    global running
    logger.info(f"Received signal {sig}. Initiating graceful shutdown...")
    running = False
    stop_all()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    logger.info("=" * 60)
    logger.info("PRAVISION PRODUCTION SERVICE WATCHDOG INITIALIZED")
    logger.info(f"Workspace Directory: {ROOT_DIR}")
    logger.info("=" * 60)

    start_backend()
    time.sleep(3)
    start_tunnel()

    consecutive_failures = 0

    while running:
        time.sleep(CHECK_INTERVAL)

        # Check backend process health
        if backend_proc and backend_proc.poll() is not None:
            logger.warning(f"Backend process terminated unexpectedly (exit code {backend_proc.returncode}). Restarting...")
            start_backend()
            consecutive_failures = 0
            continue

        # Check tunnel process health
        if tunnel_proc and tunnel_proc.poll() is not None:
            logger.warning(f"Tunnel process terminated unexpectedly (exit code {tunnel_proc.returncode}). Restarting...")
            start_tunnel()
            continue

        # Check HTTP liveness
        if not check_backend_liveness():
            consecutive_failures += 1
            logger.warning(f"Backend liveness probe failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}).")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error("Backend unresponsive after max threshold. Restarting backend process...")
                if backend_proc and backend_proc.poll() is None:
                    backend_proc.terminate()
                    try:
                        backend_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        backend_proc.kill()
                start_backend()
                consecutive_failures = 0
        else:
            if consecutive_failures > 0:
                logger.info("Backend liveness restored.")
            consecutive_failures = 0


if __name__ == "__main__":
    main()
