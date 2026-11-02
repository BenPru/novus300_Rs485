# Novus 300 bus capture preparation

`tools/novus300_bus_capture.py` is a receive-only capture tool. It opens the
same adapter configuration as the existing bridge (9600 baud, MARK parity),
sets RTS/DTR low, and never invokes `write()`. It records:

- a lossless raw byte stream (`.raw`);
- a JSON Lines file (`.jsonl`) with wall-clock and monotonic timestamps plus
  the hexadecimal representation of every received chunk.

The prepared systemd unit conflicts with
`novus300-serial-bridge.service`. Starting the capture automatically stops the
TCP bridge, so Home Assistant temporarily receives no bus updates but cannot
send or interfere with bus traffic.

## Important limitation

A single RS-485 receiver observes all traffic on the shared two-wire bus but
cannot identify which participant transmitted each frame. This is sufficient
to compare frames immediately before and after a single panel action.

True direction-labelled full-duplex recording requires hardware-level taps on
the panel and controller UART TX/RX lines, or an appropriate logic analyzer.
Do not connect two transmitting adapters to the bus. The prepared capture
records every bus frame safely; add directional hardware only if frame origin
is required after the first comparison.

## Prepared installation

The files are intended for the bridge host:

```text
/home/pi/novus300-bridge/novus300_bus_capture.py
/etc/systemd/system/novus300-bus-capture.service
/home/pi/novus300-captures/
```

The capture service is deliberately not enabled and must not be started until
the recording session is planned.

## Later recording procedure

1. Make sure Home Assistant is stable and record the current panel mode.
2. Start the passive capture:

   ```sh
   sudo systemctl start novus300-bus-capture.service
   ```

3. Wait ten seconds, then perform exactly one panel action, wait another ten
   seconds, and write down the action and time. Suggested separate captures:
   panel level 1, 2, 3, boost, away, standby, filter reset, and bypass.
4. Stop the capture:

   ```sh
   sudo systemctl stop novus300-bus-capture.service
   sudo systemctl start novus300-serial-bridge.service
   ```

5. Copy both files from `/home/pi/novus300-captures/` without editing them.
   The `.raw` file is authoritative; the `.jsonl` file makes temporal
   comparison easier.

Never attempt to replay captured frames. Captures identify candidate requests
but do not establish that a frame is safe to send.
