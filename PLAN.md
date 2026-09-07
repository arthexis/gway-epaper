# gway-epaper implementation plan

## Intent

Build a small Gway-managed service that aggregates multiple ordered text/event
sources and renders them as a continuous ePaper printout. New material is
appended at the bottom, older material scrolls upward, and source adapters remain
independent from display drivers.

The first external integration target is the Arthexis Redis Stream proposed in
`arthexis/arthexis#102`, especially `ocpp.authorization` events including stale
buffered replays from chargers that were offline for long periods.

## Architectural boundaries

The project has four layers:

1. **Configuration** — TOML parsing and validation.
2. **Sources** — adapters yielding normalized `FeedItem` objects.
3. **Printer** — one ordered aggregate line buffer with bottom append / upward
   scroll semantics.
4. **Display** — backend that renders a snapshot of the printer buffer.

Sources must not know anything about ePaper hardware. Display drivers must not
know anything about Redis, OCPP, or file offsets.

`gway_epaper.commands` is the only Gway command namespace. Internal modules must
not be added below that package unless their public functions are intentionally
commands.

## Event model

Every source produces:

```python
FeedItem(
    source="auth-events",
    text="AUTH gway-001 04A1B2C3 Accepted",
    observed_at=...,
    source_id="1740000000000-0",
)
```

`observed_at` is when gway-epaper observes the item. A source may retain another
timestamp inside metadata later, but aggregation order must not assume charger
timestamps are monotonic.

For Redis Streams, the Redis stream ID is the stable ingestion/order cursor.

## Replay-heavy Redis requirements

Arthexis authorization streams can receive a reconnect burst containing stale
buffered authorizations from chargers that were offline for a long period.
Normal live traffic assumptions are therefore invalid.

The Redis implementation must:

- use `XREAD`/consumer cursor semantics rather than Pub/Sub;
- process large bursts incrementally instead of loading an entire backlog into
  memory;
- preserve stream ordering;
- never deduplicate merely because `id_tag`, charger, or status repeats;
- treat each Redis stream entry as independently printable;
- persist the last successfully accepted stream ID locally;
- resume after restart without skipping entries;
- make initial cursor policy configurable:
  - `$` = only events arriving after startup,
  - `0-0` = consume retained history,
  - explicit stream ID = resume from a known point;
- use bounded read batches and configurable pacing/backpressure;
- tolerate the stream being trimmed before the saved cursor;
- avoid advancing durable cursor state before an item has entered the printer
  pipeline.

A future consumer-group implementation is optional. For a single local display,
plain `XREAD` plus a durable cursor file is simpler and preserves every event.
Consumer groups become useful only if delivery ownership or multiple cooperating
processes are introduced.

## Printout semantics

The default presentation is a terminal-roll metaphor:

```text
older line
older line
source-a | message
source-b | message
source-a | newest message
```

New lines are appended at the bottom. If the display has `N` text rows, the
printer keeps the newest `N` rendered rows. Wrapped messages count as multiple
rows.

Ordering is by arrival into the aggregate queue, not by timestamps embedded in
source payloads. This is important during OCPP replay bursts.

Future configuration may allow source prefixes, timestamp prefixes, priorities,
filters, and formatter functions, but the default remains simple arrival order.

## ePaper constraints

Physical ePaper updates are much slower and more wear-sensitive than terminal
drawing. The display implementation must therefore decouple ingestion rate from
physical refresh rate.

Required behavior:

- sources may ingest continuously while the display refreshes on a slower cadence;
- multiple incoming lines between physical refreshes are coalesced into one
  rendered frame;
- the logical printer buffer must not lose lines merely because the panel cannot
  refresh at source rate;
- drivers can advertise partial-refresh support;
- full-refresh cadence must be configurable to limit ghosting;
- hardware errors must not terminate source ingestion;
- a text/null driver remains available for development and CI.

## TOML schema

Initial schema:

```toml
[display]
driver = "text"
width = 40
lines = 12
refresh_seconds = 2.0

[printer]
prefix_source = true
timestamp = false

[[sources]]
name = "system"
type = "file"
path = "/var/log/syslog"
start = "end"
poll_seconds = 0.5

[[sources]]
name = "auth"
type = "redis"
url = "redis://localhost:6379/0"
stream = "arthexis:events"
event_types = ["ocpp.authorization"]
start = "$"
batch_size = 100
block_ms = 1000
cursor_file = "/var/lib/gway-epaper/auth.cursor"
```

Unknown source/display types should fail validation rather than silently
degrading.

## Phase 0 — repository foundation (this scaffold)

Scope:

- Gway project manifest using the Python-function adapter;
- Python package with no dedicated CLI;
- TOML configuration models and validation;
- normalized `FeedItem`;
- bounded bottom-append `PrinterBuffer`;
- file source that can read existing lines and follow appended lines;
- text display backend;
- Gway functions: `validate`, `preview`, `status`, `run`;
- tests for configuration and printout behavior;
- example TOML.

Acceptance:

- package imports on Python 3.11+ without Raspberry Pi libraries;
- `gway epaper validate --config ...` can validate configuration once registered;
- unit tests do not need Redis or ePaper hardware;
- appending more than display capacity keeps the newest lines in order.

## Phase 1 — durable file following

Implement:

- inode/rotation detection;
- truncation detection;
- durable per-source offsets;
- configurable `start = "beginning" | "end"`;
- line filtering/formatting;
- non-blocking polling loop across multiple files.

Acceptance:

- restart resumes without duplicating already consumed lines;
- logrotate does not permanently stall a source;
- one noisy file cannot starve other sources.

## Phase 2 — Arthexis Redis Stream source

Implement:

- optional `redis` dependency extra;
- `XREAD` batch reader;
- durable cursor file written atomically;
- `event_types` filtering;
- formatter for `ocpp.authorization`;
- raw/original event fields remain available to formatter;
- reconnect with exponential backoff;
- configurable batch size and block interval;
- explicit handling of replay bursts.

Acceptance:

- a retained sequence of >10,000 events can be drained in bounded memory;
- duplicate-looking authorization entries are all delivered;
- restart resumes from last durable Redis stream ID;
- Redis outage does not erase cursor or crash the long-running service;
- tests use a fake Redis client, not a required daemon.

## Phase 3 — aggregation loop and backpressure

Implement:

- asynchronous or selector-based source scheduler;
- bounded internal queue;
- configurable overflow policy, defaulting to **block/backpressure**, not drop;
- fair source polling;
- metrics/status counters:
  - items read per source,
  - queue depth,
  - last source cursor,
  - refresh count,
  - source errors;
- clean shutdown.

For replay bursts, input may outrun the panel by orders of magnitude. Logical
consumption and physical rendering therefore need separate queues/state.

Acceptance:

- Redis replay traffic does not exhaust memory;
- live log sources continue progressing during Redis backlog drain;
- no silent item dropping under default settings.

## Phase 4 — real ePaper drivers

Implement a display-driver protocol and first concrete Waveshare driver matching
the panel selected for the Gway device.

Keep hardware dependencies optional:

```toml
[project.optional-dependencies]
epaper = [...]
```

Driver responsibilities:

- initialize/sleep panel;
- map logical monochrome frame to panel geometry;
- partial refresh when supported;
- periodic full refresh;
- recover from SPI/GPIO errors;
- report hardware status.

Acceptance:

- text backend remains fully functional on non-RPi hosts;
- importing `gway_epaper` never imports GPIO/SPI libraries eagerly;
- hardware tests are separately marked/optional.

## Phase 5 — service lifecycle

Add Gway functions for installation/service management rather than a dedicated
CLI:

```text
gway epaper install-service
gway epaper service-status
gway epaper uninstall-service
```

The systemd service should invoke Python through Gway-managed project isolation
or a small module runner owned by this package, not a parallel command parser.

Define:

- config location, likely `/etc/gway-epaper.toml`;
- state directory, likely `/var/lib/gway-epaper`;
- least-privilege service user/group consistent with SPI/GPIO access;
- Redis access via localhost by default;
- restart policy and clean shutdown.

## Phase 6 — richer formatters and sources

Potential additions, each in separate PRs:

- journald source;
- subprocess/stdin source;
- additional Redis event types (`ocpp.status`, faults, transaction lifecycle,
  admin messages);
- source-specific formatter modules;
- priority/banner messages;
- fixed header/footer regions;
- QR or icon rendering;
- local health/status lines.

Raw OCPP traffic should not automatically be streamed into the display. Prefer
normalized Arthexis events with explicit formatter support.

## Out of scope for the initial repository

- modifying Arthexis;
- owning the Redis event schema;
- full OCPP parsing;
- Redis Pub/Sub;
- MQTT;
- web UI;
- a project-specific argparse/click CLI;
- bundling Waveshare libraries into the base install;
- assuming that all auth events correspond to fresh scans.

## Verification commands for future PRs

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
python -m compileall -q src
```

With Gway 1.x installed and this project registered:

```text
gway epaper validate --config epaper.example.toml
gway epaper preview --config epaper.example.toml
gway epaper status --config epaper.example.toml
```
