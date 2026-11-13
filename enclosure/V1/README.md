# Enclosure V1 — Open, Stackable E-Resistor / Relay Assembly

Status: **V1 mechanical prototype — NOT hardware-fit-qualified**.

This folder contains editable models for a 3D-printable open frame holding a resistor PCB on the bottom and the eight-relay controller PCB above it. Four removable posts allow complete assemblies to stack vertically.

## Verified lower PCB geometry

From [the KiCad PCB](../../Resistors-board/Resistors-board.kicad_pcb) (reviewed 2026-11-13):

| Parameter | Value |
| --- | --- |
| Lower resistor PCB outline | 145 × 55 mm |
| PCB thickness | 1.6 mm |
| Four mounting holes | 3.2 mm diameter |
| Mounting-hole centres | 138 × 48 mm |
| Hole offset from corresponding corners | 3.5 mm |

**Not verified:** the real YHQ001/CH9120 eight-relay PCB mounting pattern, component envelopes, wiring/terminal access, insertion tolerances, cooling and physical fit. The relay board in visualizations is a *placeholder* only.

## V1 dimensions

| Item | Nominal value |
| --- | ---: |
| Open-frame body footprint | 178 × 86 mm |
| Overall XY envelope incl. local protrusions | approximately 178 × 90 mm |
| Lower base frame thickness | 4.5 mm |
| Resistor support boss height | 6.4 mm above base |
| Lower tray support post length | 21 mm |
| Upper tray thickness | 5.2 mm |
| Upper board adapter-arm thickness | 3.6 mm |
| Resistor PCB to relay PCB board-plane separation | 21.8 mm |
| Assumed maximum resistor-side component height | 14 mm above lower PCB |
| Resulting *free air* above assumed lower components | 7.8 mm |
| Stackable upper pillar length | 45 mm |
| Base-to-base repeat pitch | 75.7 mm |
| Adjustable relay mount arm slot | 8–28 mm from pivot |

The requested **5–10 mm gap means clear space above the tallest fitted resistor-board component**, not bare-PCB separation. Actual clearance is:

`gap [mm] = 21.8 - fitted lower component height above PCB [mm]`

Adjust `LOWER_POST_H` in `create_step.py` or `lower_post_h` in `e_resistor_stack.scad` after measuring the assembled resistor board. Upper module-to-module headroom must also be checked against the real relay, RJ45 and wiring heights.

## File contents

- [`create_step.py`](create_step.py) — CadQuery/OpenCascade parametric geometry source; generates five printable STEP/STL parts and positioned STEP assemblies.
- [`e_resistor_stack.scad`](e_resistor_stack.scad) — OpenSCAD source with individual printable parts, assembled, exploded and two-module stacked preview modes.
- Generated outputs (regenerate from `create_step.py`): `base.stl`, `tray.stl`, `arm.stl`, `lower_post.stl`, `stack_post.stl`, corresponding `.step` files, `frame_assembly.step`, and `frame_with_reference_pcbs.step`.
- A single module uses **1 base, 1 tray, 4 adapter arms, 4 lower posts, and up to 4 stacking posts**.

### Generate CAD files

Install a compatible Python/CadQuery environment and run:

```bash
python -m pip install cadquery
python enclosure/V1/create_step.py
```

For an editable 3D preview, open `e_resistor_stack.scad` in OpenSCAD and set `part` to `assembled`, `exploded`, `stacked`, or an individual part name.

The generated STEP files can be opened in FreeCAD.

## Fasteners, construction and stacking

Nominal fasteners are M3 machine screws, washers, and manufacturer-verified brass heat-set inserts. Both sets of corner support posts use inserts at *both ends*. The pivoting relay mounting arms provide adjustment until the real relay PCB's mounting points have been measured.

1. Print and inspect the open lower frame, upper tray, four adapter arms and support posts.
2. Fit M3 inserts in the base mounting bosses, upper-tray pivots, and ends of posts, according to actual insert geometry.
3. Secure the short lower posts to the frame from below.
4. Screw down the resistor PCB at its four verified locations.
5. Pre-wire the lower PCB before mounting the upper tray, preserving access to connector screws.
6. Install the upper tray and orient the adjustable arms to the real relay PCB mounting holes.
7. Secure the relay board, checking component and solder-pad clearance.
8. Attach four upper stack posts, then secure the next module's base to those posts.

**Do not assume** the demonstration PCB hole coordinates and components in the exploded rendering match the real relay controller. Where fitted connector hardware conflicts with the upper tray, resize or relocate the tray before printing.

## Printing guidance

PETG is preferred, with an initial profile of 0.2 mm layers, 4 perimeters and 30–40% infill. Lay the base, upper tray and adapter arms flat on the bed. Print cylindrical posts upright. Supports should not generally be required. Test the specific heat-set insert bore and intermodule fastening before a complete multi-level build.

## Qualification checklist

- [x] Lower resistor PCB outline, hole pitch, and thickness taken from the actual KiCad layout.
- [x] Editable parametric CadQuery/OpenSCAD models prepared.
- [x] CAD-generation solid checks and STL watertightness checks passed in the initial local export.
- [ ] Real upper relay-board footprint and holes measured.
- [ ] Lower and upper populated-component heights measured.
- [ ] Terminal-block and RJ45 access checked.
- [ ] End-to-end hardware test print and physical fit verified.
- [ ] Stack stiffness, fasteners, creepage/clearance and cooling tested.

**V1 is a mechanical fit prototype, not a production-qualified enclosure.**
