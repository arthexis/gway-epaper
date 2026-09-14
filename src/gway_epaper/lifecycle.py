from __future__ import annotations

import platform
import subprocess
import sys
import tempfile
from pathlib import Path

WAVESHARE_REPOSITORY = "https://github.com/waveshareteam/e-Paper.git"
WAVESHARE_REVISION = "a794fbc39656b0f93938d1ffb3fdc77eaed9e9fc"
WAVESHARE_SUBDIRECTORY = "RaspberryPi_JetsonNano/python"
_SUPPORTED_MACHINES = {"aarch64", "armv7l"}


def _is_raspberry_pi_linux() -> bool:
    return platform.system() == "Linux" and platform.machine() in _SUPPORTED_MACHINES


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _install_waveshare_driver() -> None:
    if not _is_raspberry_pi_linux():
        return

    with tempfile.TemporaryDirectory(prefix="gway-epaper-waveshare-") as temporary:
        checkout = Path(temporary) / "e-Paper"
        checkout.mkdir()

        _run(["git", "init", "-q", str(checkout)])
        _run(["git", "-C", str(checkout), "remote", "add", "origin", WAVESHARE_REPOSITORY])
        _run(["git", "-C", str(checkout), "sparse-checkout", "init", "--cone"])
        _run(
            [
                "git",
                "-C",
                str(checkout),
                "sparse-checkout",
                "set",
                WAVESHARE_SUBDIRECTORY,
            ]
        )
        _run(
            [
                "git",
                "-C",
                str(checkout),
                "fetch",
                "--depth=1",
                "--filter=blob:none",
                "--no-tags",
                "origin",
                WAVESHARE_REVISION,
            ]
        )
        _run(["git", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"])

        package = checkout / WAVESHARE_SUBDIRECTORY
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--force-reinstall",
                str(package),
            ]
        )


def install(*_arguments: str) -> None:
    _install_waveshare_driver()


def upgrade(*_arguments: str) -> None:
    _install_waveshare_driver()
