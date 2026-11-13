# E-Resistor KiCad bit-table footprints

This package provides **padless, board-only KiCad footprints** that draw the 8-relay resistor population table on PCB silkscreen.

## Included

- `E_Resistor_Legends.pretty/E_Resistor_Bit_Table_Compact.kicad_mod` — about 44.5 × 20 mm, columns `BIT / R1||R2 / R3||R4 / REQ`.
- `E_Resistor_Legends.pretty/E_Resistor_Bit_Table_Full.kicad_mod` — about 63 × 25 mm, explicit `R1 / R2 / R3 / R4` columns.
- `generate_bit_table.py` — edit `ROWS` or `BASE_TEXT` and regenerate both footprints.

## Add to KiCad

1. Copy `E_Resistor_Legends.pretty` into your KiCad project directory.
2. Open **Preferences → Manage Footprint Libraries**.
3. Open **Project Specific Libraries**.
4. Choose **Add Existing Library to Table** and select `E_Resistor_Legends.pretty`.
5. In PCB Editor use **Place → Add Footprint**.
6. Search for `E_Resistor_Bit_Table` and place the compact or full footprint.

The footprint has no pads, is marked `board_only`, and is excluded from BOM and position files.

## Regenerate after resistor changes

Edit `ROWS` in `generate_bit_table.py`, then run:

```bash
python generate_bit_table.py
```

Notation: `||` means parallel, `DNP` means do-not-populate, `2k74` = 2.74 kΩ, `301R10` = 301.10 Ω.
