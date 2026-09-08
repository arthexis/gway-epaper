import tomllib
from pathlib import Path


def test_raspberry_pi_runtime_dependencies_are_declared() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as stream:
        data = tomllib.load(stream)

    dependencies = data["project"]["dependencies"]
    joined = "\n".join(dependencies)

    assert "waveshare-epd @ git+https://github.com/waveshareteam/e-Paper.git" in joined
    assert "spidev>=3.6" in joined
    assert "gpiozero>=2" in joined
    assert "platform_machine == 'aarch64'" in joined
    assert "platform_machine == 'armv7l'" in joined
