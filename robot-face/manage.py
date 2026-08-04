#!/usr/bin/env python3
"""
Small admin CLI for the Robot Face service.

Usage:
  python3 manage.py set-password          # prompts, hidden input (recommended)
  python3 manage.py set-password 'secret'  # non-interactive
  python3 manage.py show                    # print current config (hash redacted)
"""
import getpass
import json
import os
import sys

from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, "config.json")


def _load():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def _save(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)
    os.chmod(CONFIG_FILE, 0o600)


def set_password(pw=None):
    if pw is None:
        pw = getpass.getpass("New control-panel password: ")
        again = getpass.getpass("Confirm: ")
        if pw != again:
            print("Passwords did not match.", file=sys.stderr)
            sys.exit(1)
    if not pw:
        print("Empty password not allowed.", file=sys.stderr)
        sys.exit(1)
    cfg = _load()
    cfg["password_hash"] = generate_password_hash(pw)
    _save(cfg)
    print("Password updated. Restart the service to be safe:")
    print("  sudo systemctl restart robot-face")


def show():
    cfg = _load()
    redacted = dict(cfg)
    if "password_hash" in redacted:
        redacted["password_hash"] = "<set>"
    if "secret_key" in redacted:
        redacted["secret_key"] = "<set>"
    print(json.dumps(redacted, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "set-password":
        set_password(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "show":
        show()
    else:
        print(__doc__)
        sys.exit(1)
