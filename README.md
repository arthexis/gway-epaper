# gway-epaper

`gway-epaper` turns multiple local data sources into a continuous, paper-like
feed for an ePaper display on a Gway device.

The project uses the Gway 1.x Python-function adapter. It intentionally does not
ship its own CLI. Public functions under `gway_epaper.commands` are discovered by
Gway and exposed as managed commands.

The display model is append-oriented: newly ingested lines appear at the bottom,
existing lines move upward, and lines that no longer fit disappear from the top.

## Supported hardware

The first hardware backend is the **Waveshare 2.13-inch e-Paper HAT V4**, the
250x122 monochrome Raspberry Pi HAT identified on the board as `2.13inch e-Paper
HAT` with the `V4` revision marker.

The backend uses Waveshare's `waveshare_epd.epd2in13_V4` driver and Pillow for
text rendering. Hardware imports are lazy and cached, so development and CI do
not require GPIO/SPI libraries or a Raspberry Pi.

```toml
[display]
driver = "waveshare_2in13_v4"
width = 40
lines = 12
refresh_seconds = 2.0
min_refresh_seconds = 5.0
font_size = 12
margin = 4
```

`refresh_seconds` controls the runtime/source polling loop. Physical Waveshare
updates are independently guarded by `min_refresh_seconds`: unchanged frames are
not sent to the panel, and multiple changed frames arriving inside the guard
window are coalesced so only the newest frame is rendered when the next refresh
is due. Set `min_refresh_seconds = 0` only when explicitly testing unrestricted
refreshes.

The HAT uses the Raspberry Pi SPI/GPIO interface. SPI must be enabled on the Pi.
The Waveshare driver itself is intentionally not vendored into this repository.
The current backend uses full refreshes; partial-refresh policy remains deferred
until the real V4 panel has been validated for orientation, ghosting, and cadence.

## Sources

File sources and Redis Streams are supported. The first Redis integration is the
Arthexis `arthexis:events` stream:

```toml
[[sources]]
name = "auth-events"
type = "redis"
url = "redis://localhost:6379/0"
stream = "arthexis:events"
event_types = ["ocpp.authorization"]
start = "$"
batch_size = 100
block_ms = 1000
cursor_file = "/var/lib/gway-epaper/auth.cursor"
```

Install Redis support with:

```text
python -m pip install -e '.[redis]'
```

`start = "$"` begins at the current stream tail, `0-0` consumes retained
history, and an explicit Redis Stream ID resumes from a known point. `$` is
resolved once to a concrete ID so entries cannot fall into gaps between polls.
When `cursor_file` is configured, the last ingested stream ID is written
atomically and reused after restart.

Authorization events retain the full `id_tag`, `original`, and `raw` fields in
the `FeedItem` metadata. Repeated-looking authorization events are deliberately
not deduplicated because chargers may replay buffered requests after long
offline periods.

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

## Bootstrap service control without Gway

The repository includes thin bootstrap wrappers for cases where Gway is not
installed or is itself unavailable:

```text
./epaper.sh start
epaper.bat start
```

Both wrappers support `start`, `stop`, `restart`, `status`, and `run`. They call
the same `gway_epaper.runtime.run_forever()` implementation used by the managed
Gway command path.

By default they use `epaper.toml` in the repository root and write transient PID
and log files below `.run/`. Set `EPAPER_CONFIG` to use another configuration
file and `PYTHON` to select a different Python executable.

## Configuration

Copy `epaper.example.toml` to `epaper.toml`. See `PLAN.md` for replay semantics,
refresh/backpressure policy, and future implementation phases.
