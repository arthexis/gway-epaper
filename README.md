# gway-epaper

`gway-epaper` turns multiple local data sources into a continuous, paper-like
feed for an ePaper display on a Gway device.

The project uses the Gway 1.x Python-function adapter. It intentionally does not
ship its own CLI. Public functions under `gway_epaper.commands` are discovered by
Gway and exposed as managed commands.

The display model is append-oriented: newly ingested lines appear at the bottom,
existing lines move upward, and lines that no longer fit disappear from the top.
This makes the display behave like a small continuous printout aggregating all
configured sources.

## Planned sources

- ordinary log/text files
- Redis Streams, beginning with Arthexis `arthexis:events`
- later source adapters can be added without changing the printer or display
  contracts

## Initial commands

Once registered with Gway:

```text
gway epaper validate
gway epaper preview
gway epaper status
gway epaper run
```

The Python facade mirrors the same namespace:

```python
from gway import gway as gw

gw.epaper.validate()
gw.epaper.preview()
gw.epaper.status()
gw.epaper.run()
```

`run` currently exercises the source/aggregation loop with the text backend.
Hardware ePaper drivers and Redis consumption are intentionally staged in
`PLAN.md`.

## Bootstrap service control without Gway

The repository also includes thin bootstrap wrappers for cases where Gway is not
installed or is itself unavailable:

```text
./epaper.sh start
epaper.bat start
```

Both wrappers support `start`, `stop`, `restart`, `status`, and `run`. They call
the same `gway_epaper.runtime.run_forever()` implementation used by the managed
Gway command path; they are service-control fallbacks, not a second application
CLI.

By default they use `epaper.toml` in the repository root and write transient PID
and log files below `.run/`. Set `EPAPER_CONFIG` to use another configuration
file and `PYTHON` to select a different Python executable.

On Linux, production service supervision is still expected to move to systemd in
a later phase; `epaper.sh` remains useful as an emergency/bootstrap path.

## Configuration

Copy `epaper.example.toml` to `epaper.toml`.

```toml
[display]
driver = "text"
width = 40
lines = 12
refresh_seconds = 2.0

[[sources]]
name = "arthexis-log"
type = "file"
path = "/var/log/arthexis/charger.gway-001.log"
start = "end"

[[sources]]
name = "auth-events"
type = "redis"
url = "redis://localhost:6379/0"
stream = "arthexis:events"
event_types = ["ocpp.authorization"]
start = "$"
```

See `PLAN.md` for replay semantics, Redis consumer-state requirements, ePaper
refresh policy, and future implementation phases.
