from __future__ import annotations

import platform
import subprocess
import sys
import tempfile
from pathlib import Path

WAVESHARE_REPOSITORY = "https://github.com/waveshareteam/e-Paper.git"
WAVESHARE_REVISION = "a794fbc39656b0f93938d1ffb3fdc77eaed9e9fc"
WAVESHARE_SUBDIRECTORY = "RaspberryPi_JetsonNano/python"
SERVICE_UNIT = "gway-epaper.service"
SYSTEMD_UNIT_DIRECTORY = Path("/etc/systemd/system")
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


def _restart_managed_service() -> None:
    """Restart an already-installed Gway service after its environment refreshes."""

    if platform.system() != "Linux":
        return
    unit = SYSTEMD_UNIT_DIRECTORY / SERVICE_UNIT
    if not unit.is_file():
        return
    _run(["systemctl", "try-restart", SERVICE_UNIT])


def install(*_arguments: str) -> None:
    """Install hardware support; Gway owns optional service unit installation."""

    _install_waveshare_driver()


def upgrade(*_arguments: str) -> None:
    """Refresh hardware support and restart an existing Gway-managed service."""

    _install_waveshare_driver()
    _restart_managed_service()
