"""Fail if an automated change touches anything except params and reports.

Usage: check_auto_diff.py <base-ref> [--staged]
Guarantees the self-improvement loop can never change code, risk limits,
broker selection or live-trading mode.
"""
import subprocess
import sys

ALLOWED_PREFIXES = ("config/params.yaml", "reports/")

base = sys.argv[1]
cmd = ["git", "diff", "--name-only"]
cmd += ["--cached", base] if "--staged" in sys.argv else [f"{base}...HEAD"]
files = [f for f in subprocess.check_output(cmd, text=True).split() if f]
bad = [f for f in files if not f.startswith(ALLOWED_PREFIXES)]
if bad:
    print("automated change touches forbidden files:", *bad, sep="\n  ")
    sys.exit(1)
print(f"ok: {len(files)} file(s) changed, all within {ALLOWED_PREFIXES}")
