# Enclosure V3 UNIVERSAL — one printed frame variant

**Status: CAD-validated prototype only; relay PCB mechanical dimensions, snap forces, clip durability and physical fit are NOT verified.**

V3 now uses **one universal PCB frame** for the bottom resistor board and the upper 8-relay board. Print **two identical copies of `universal_frame.stl` per complete electrical module**, not two separate lower/upper frame types. Both use the same **board-edge support and flex clips**; the lower resistor board's mounting-hole spacing is no longer part of the mechanical interface. No separate spacer, screw or locking accessory is required in the nominal assembly.

![Exploded: two copies of the same universal frame](exploded_v3.png)
![One complete assembled electrical module](assembled_v3.png)
![Two complete electrical modules stacked using four identical frames](stacked_v3.png)

## Which dimensions are verified?

The real resistor PCB, read from [Resistors-board.kicad_pcb](../../Resistors-board/Resistors-board.kicad_pcb), is **145 × 55 × 1.6 mm**; it also has four Ø3.2-mm holes at a 138 × 48 mm pitch. The updated universal carrier **does not rely on any hole position**.

The actual **YHQ001 8-relay PCB outline is NOT dimensioned in this repository**. Its modelled **145 × 56 × 1.6 mm outline is only a fit placeholder**. The printed spring clips are provisionally dimensioned to fit the nominal 145-mm PCB length of both board models. This is *universal between these two nominal board envelopes*, **not a fixture for arbitrary PCB sizes**. Verify the relay board's actual dimensions and accessible end edges before printing.

| Feature | V3 universal target |
| --- | --- |
| Number of distinct production STLs | **1** — `universal_frame.stl` |
| Quantity per complete 2-PCB assembly | **2 identical frames** |
| Additional spacer/clip/screw items | **0** nominally |
| Common frame footprint | 174 × 82 mm |
| Maximum part height | 47 mm |
| Lower PCB-to-upper PCB *support-plane* pitch | **23.6 mm** |
| Upper PCB-to-next module support-plane pitch | **40.0 mm** |
| Repeated complete-module pitch | **63.6 mm** |
| Assumed resistor component maximum height | 14 mm above the resistor PCB |
| Nominal free gap above lower components | **8.0 mm** (14-mm assumption) |
| Assumed relay component maximum height | 27 mm above the relay PCB |
| Nominal free gap above relay components | **11.4 mm** (27-mm assumption) |
| PCB retention | Four integral end-edge clips and underside seats |
| Interframe retention | Four integrated snap wedges, two selectable heights |

### How one printed part supports two different stack pitches

**Orientation matters.** For every complete electrical module:

1. Start with **universal frame A** at **0°** orientation; insert the **resistor PCB** onto its four generic support seats and under the spring clips.
2. Fit **universal frame B** — exactly the same printed part — **rotated 180° around the vertical axis**. Its four receiver channels slide around the complementary half-width pillars of frame A. Press down until the four **SHORT** catches engage at **23.6 mm**.
3. Insert the **relay PCB** in frame B's generic edge clips. Confirm that real relay components, RJ45 and terminals do not interfere with the support or lower board.
4. Start the next electrical module by setting its **resistor frame C**, rotated back to **0°**, on the **TALL** catches of frame B at **40.0 mm**.
5. Continue 0°/180°/0°/180° with alternating SHORT (resistor → relay) and TALL (relay → next resistor) connections. **Never force the joint** if the latch engagement feels wrong.

Each corner has one slender half-post, a complementary clearance slot, and two positive tapered shoulders located to engage at the required levels. It is a *geometric snap lock* with nominal **0.65 mm catch engagement**, not a verified structural fastening. The higher catch must be pushed past before the short catch can be reached; the column is intended to flex. Actual insertion/extraction force, cyclic flexural strength and resistance to vibration must be tested on printed PETG parts. The original V3 double-frame variants are superseded; only `universal_frame.stl` is the current production frame.

### Clearance calculations

Both boards sit with their undersides **7.0 mm** above their corresponding frame datum and have nominal thickness **1.6 mm**. Thus:

```
resistor-top-to-relay-underside clearance = 23.6 - 1.6 - actual resistor component height
relay-top-to-next-resistor-underside = 40.0 - 1.6 - actual relay component height
```

The 5–10 mm requested lower component gap is met by the **8 mm nominal assumption** *only if* the lower populated board has a tallest component of 14 mm. The relay-to-next-module gap is **11.4 mm nominal** if relay components are no taller than 27 mm. Both figures must be recomputed from measurements.

## FDM printing and snap durability

- Print the **single model** twice per assembly, flat open frame down on the bed, interleaving posts upright. It fits a nominal 220 × 220 mm print area.
- Begin with **PETG**, 0.4-mm nozzle, 0.2-mm layers, 4–5 perimeters, 30–40% infill. Apply 5–8-mm brim if the slender posts show instability.
- No long horizontal roofs are built in; no supports expected for the main geometry, but **inspect edge-clip lips and 2-level latch ramps carefully in the slicer**. Small overhangs are deliberately retained.
- Test both spring clip types using a **PCB-sized coupon** or scrap circuit board before pushing the real electronics into the mounts. Very small dimensional variation can change flex force or break clips. Clean any strings from the receiver slots.
- Before relying on stack retention, perform pull-out, lateral load, thermal cycling and repeated disassembly checks. External restraint remains recommended for vertical hanging or mobile installations.
- Maintain safe electrical creepage/clearance, wiring strain relief and airflow; the printed open-frame system is not a safety-rated enclosure.

## CAD and qualification files

- [`universal_frame.stl`](universal_frame.stl) — **the only printable production frame variant**; print two copies per complete module.
- [`universal_frame.step`](universal_frame.step) — individual STEP solid, editable in FreeCAD via further geometry operations.
- [`create_v3.py`](create_v3.py) — source for the single-part frame, supports, latches and assembly construction.
- [`module_assembly.step`](module_assembly.step), [`two_modules.step`](two_modules.step), [`exploded_assembly.step`](exploded_assembly.step) — STEP assemblies containing copies of the *same* frame geometry, reference PCBs and placements.
- [`test_fit.py`](test_fit.py), [`fit_check.json`](fit_check.json) — nominal 4-frame 0°/180° interframe and PCB collision checks (static non-interference only; not latch-insertion simulation).
- [`verification.json`](verification.json) — BRep validity, watertight STL and nominal gaps.
- [`render_v3.py`](render_v3.py), [`exploded_v3.png`](exploded_v3.png), [`assembled_v3.png`](assembled_v3.png), [`stacked_v3.png`](stacked_v3.png) — CAD-based visualization; components are *illustrative* placeholders.

Generate and test with:

```bash
python -m pip install cadquery trimesh numpy pillow
python enclosure/V3/create_v3.py
python enclosure/V3/test_fit.py
python enclosure/V3/render_v3.py
```

### Physical qualification remains open

- [x] Actual resistor PCB length, width, thickness verified in KiCad.
- [x] **One universal mechanical frame variant** serves both reference board envelopes.
- [x] Four-frame stack **nominal** BRep collision checks pass at short and tall offsets.
- [x] STEP, one STL, assembled/exploded/multimodule renders export reproducibly.
- [ ] Measure the populated actual relay PCB outline and end-edge accessibility.
- [ ] Measure highest resistor, relay, terminal and connector components and their XY outlines.
- [ ] Print test part; verify spring capture, tool release and four-latch engagement at both heights.
- [ ] Test lock pull strength, repeated assembly cycles and allowable electrical module stack height.

**CAD passing does not imply physical qualification.**