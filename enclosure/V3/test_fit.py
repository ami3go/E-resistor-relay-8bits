"""Nominal interference and stack interface checks (not physical HIL)."""
import json
from pathlib import Path
from create_v3 import (
    make_frame,pcb,R_X,R_Y,R_HX,R_HY,U_X,U_Y,RES_SUPPORT_Z,
    RELAY_SUPPORT_Z,LOWER_PITCH,UPPER_PITCH,DOCK_HEAD_D,
    DOCK_BORE_D,DOCK_RELIEF_D,DOCK_HEAD_BASE_Z,DOCK_COUNTERBORE_Z,
    DOCK_HEAD_H,OUT_X,OUT_Y,
)
OUT=Path(__file__).resolve().parent
low=make_frame('resistor');up=make_frame('relay')
checks={
 'lower_pcb_vs_resistor_frame':(pcb(R_X,R_Y,RES_SUPPORT_Z,R_HX,R_HY),low),
 'relay_pcb_vs_relay_frame':(pcb(U_X,U_Y,RELAY_SUPPORT_Z),up),
 'lower_frame_vs_upper_frame':(low,up.translate((0,0,LOWER_PITCH))),
 'upper_frame_vs_next_lower':(up,low.translate((0,0,UPPER_PITCH))),
}
results={}
for label,(a,b) in checks.items():
    v=a.intersect(b).Volume()
    results[label]=round(v,6)
    assert v < .0001, f'{label}: interference {v:.3f} mm3'
assert DOCK_HEAD_D < DOCK_RELIEF_D
assert DOCK_HEAD_D > DOCK_BORE_D
assert DOCK_HEAD_BASE_Z > DOCK_COUNTERBORE_Z
assert DOCK_HEAD_BASE_Z+DOCK_HEAD_H < 5.2
assert OUT_X<=220 and OUT_Y<=220
report={
 'zero_nominal_solid_interference_mm3':results,
 'mounting_interface':{
    'shaft_to_bore_diametral_clearance_mm':round(DOCK_BORE_D-4.20,3),
    'head_snap_radial_deflection_each_mm':round((DOCK_HEAD_D-DOCK_BORE_D)/2,3),
    'head_to_relief_diametral_clearance_mm':round(DOCK_RELIEF_D-DOCK_HEAD_D,3),
    'lower_to_upper_pitch_mm':LOWER_PITCH,
    'upper_to_next_lower_pitch_mm':UPPER_PITCH,
 },
 'scope':'Nominal BRep mechanical proxies only; no populated relay PCB dimensions or physical snap force tests.'
}
(OUT/'fit_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
