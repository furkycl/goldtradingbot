"""Every sub-command registered in the parser must have a handler (regression:
telegram-login/health/doctor once silently fell through to nothing)."""
import re
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "goldbot" / "cli.py"


def test_every_parser_command_has_a_branch():
    src = CLI.read_text()
    declared = set(re.findall(r'add_parser\("([a-z-]+)"', src))
    handled = set(re.findall(r'args\.cmd == "([a-z-]+)"', src))
    assert declared - handled == set(), f"commands without handler: {declared - handled}"


def test_doctor_and_health_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = subprocess.run([sys.executable, "-m", "goldbot", "doctor"], capture_output=True, text=True,
                         cwd=CLI.parent.parent, timeout=180)
    assert out.returncode == 0 and "config loaded" in out.stdout and "need YOUR input" in out.stdout or \
        "nothing missing" in out.stdout
    h = subprocess.run([sys.executable, "-m", "goldbot", "health"], capture_output=True, text=True,
                       cwd=CLI.parent.parent, timeout=60)
    assert h.returncode in (0, 1)
