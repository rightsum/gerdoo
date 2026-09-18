"""
pytest config for robot-face.

On macOS, pytest's default tmp root lives under a deeply nested per-user
TMPDIR (/private/var/folders/.../T/pytest-of-<user>/pytest-N/<test-name>N/),
often past 100 characters before a single file name is added. AF_UNIX socket
paths are capped at ~104 bytes on macOS (108 on Linux), so any test that
binds a unix socket under the `tmp_path` fixture fails there with "AF_UNIX
path too long" -- unrelated to the code under test. Give pytest a short tmp
root instead so tests that open real sockets (video.py's mpv IPC client, for
one) have room to build a path.
"""


def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = "/tmp/gerdoo-pytest"
