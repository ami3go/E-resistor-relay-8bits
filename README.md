# E-Resistor Relay 8bits

8-bit relay-based resistor switch board, part of the [E-Resistor](https://github.com/ami3go/E-resistor) project family.

The board is built around the common **YHQ001 eight-channel Ethernet relay board** (WCH CH9120 Ethernet-to-UART controller), switching 8 relay channels to select resistance values.

## Control software

Control software is not duplicated here — it's included as the [`control/`](control) submodule, pointing at [ch9120-ethernet-relay-toolkit](https://github.com/ami3go/ch9120-ethernet-relay-toolkit), which provides:

- CH9120 discovery over UDP ports 50000/60000.
- Read, back up, modify, write, and verify the CH9120 configuration.
- Tkinter configuration and relay-control GUIs.
- CLI tools for discovery, configuration, TCP-server setup, and relay sequence testing.

### Getting the code

```bash
git clone --recurse-submodules https://github.com/ami3go/E-resistor-relay-8bits.git
```

If already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

See [control/README.md](control/README.md) for full usage instructions.
