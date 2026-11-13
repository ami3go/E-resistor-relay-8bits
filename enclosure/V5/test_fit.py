"""CAD-only fit checks for 5/20-mm bare-PCB face clearances."""
import json
from pathlib import Path
from create_v5 import (
 shelf_unit,pcb_proxy,R_X,R_Y,U_X,U_Y,R_Z,U_Z,PCB_T,GAP_R_TO_U,
 GAP_U_TO_NEXT_R,PITCH,R_COMPONENT_ASSUMED,U_COMPONENT_ASSUMED,FRAME_X,FRAME_Y
)
HERE=Path(__file__).resolve().parent
frame=shelf_unit()
r=pcb_proxy(R_X,R_Y,R_Z)
u=pcb_proxy(U_X,U_Y,U_Z)
other=frame.translate((0,0,PITCH))
overlaps={
 'resistor_PCB_with_frame':frame.intersect(r).Volume(),
 'relay_PCB_with_frame':frame.intersect(u).Volume(),
 'two_adjacent_shelf_frames':frame.intersect(other).Volume(),
 'resistor_PCB_with_relay_PCB':r.intersect(u).Volume()
}
assert all(v<0.0001 for v in overlaps.values()),overlaps
assert abs(U_Z-(R_Z+PCB_T)-5)<1e-7
assert abs(PITCH+R_Z-(U_Z+PCB_T)-20)<1e-7
assert FRAME_X<=220 and FRAME_Y<=220
report={
 'PCB_face_to_face_gaps_mm':{
    'resistor_to_relay':GAP_R_TO_U,
    'relay_to_next_resistor':GAP_U_TO_NEXT_R
 },
 'repeating_pair_pitch_mm':PITCH,
 'nominal_solid_intersection_volume_mm3':{k:round(v,8) for k,v in overlaps.items()},
 'clearance_warning':{
  'component_clearance_is_not_verified':True,
  'resistor_component_assumption_mm':R_COMPONENT_ASSUMED,
  'relay_component_assumption_mm':U_COMPONENT_ASSUMED,
  'resistor_intrusion_at_assumed_height_mm':max(0,R_COMPONENT_ASSUMED-GAP_R_TO_U),
  'relay_intrusion_at_assumed_height_mm':max(0,U_COMPONENT_ASSUMED-GAP_U_TO_NEXT_R),
  'physical_fit_test_required':True
 }
}
(HERE/'fit_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
