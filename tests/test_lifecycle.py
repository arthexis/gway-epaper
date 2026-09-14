from pathlib import Path

from gway_epaper import lifecycle


def test_waveshare_install_uses_sparse_checkout(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(lifecycle.platform, "system", lambda: "Linux")
    monkeypatch.setattr(lifecycle.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(lifecycle, "_run", lambda command: commands.append(command))

    lifecycle.install()

    joined = [" ".join(command) for command in commands]
    assert any("sparse-checkout set RaspberryPi_JetsonNano/python" in command for command in joined)
    assert any("fetch --depth=1 --filter=blob:none --no-tags origin" in command for command in joined)
    assert any("checkout --detach FETCH_HEAD" in command for command in joined)
    assert any("pip install" in command and "--no-deps" in command for command in joined)
    assert not any(command[:2] == ["git", "clone"] for command in commands)


def test_waveshare_install_is_skipped_off_raspberry_pi(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(lifecycle.platform, "system", lambda: "Linux")
    monkeypatch.setattr(lifecycle.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(lifecycle, "_run", lambda command: commands.append(command))

    lifecycle.install()

    assert commands == []
