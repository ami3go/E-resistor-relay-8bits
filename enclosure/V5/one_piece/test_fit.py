"""Dimensional and solid-intersection checks for V5 single-print PCB rack.

NOTE: Only EMPTY 1.6 mm PCB silhouettes are available. Checks are not a
substitute for measuring actual populated boards, harnesses and terminals.
"""
import json
from pathlib import Path
import cadquery as cq
from create_onepiece import (
    OUT, R_X,R_Y,L_X,L_Y,PCB_T, R0_Z,L0_Z,PAIR_PITCH,
    GAP_R_TO_L,GAP_L_TO_NEXT_R,GUIDE_MIN,SHELF_INNER,
    board_levels,frame,reference_pcb,R_COMPONENT_ASSUMED,L_COMPONENT_ASSUMED
)

body=cq.importers.importStep(str(OUT/'onepiece_frame.step')).val()
assert body.isValid() and len(body.Solids())==1
assert abs(L0_Z-(R0_Z+PCB_T)-5.0)<1e-6
assert abs(PAIR_PITCH+R0_Z-(L0_Z+PCB_T)-20.0)<1e-6
assert min(R_X,L_X)/2<GUIDE_MIN

results={}
max_overlap=0.
for kind,i,z in board_levels():
    board=reference_pcb(kind,z)
    collision=body.intersect(board).Volume()
    results[f'{kind}_{i+1}']=round(collision,8)
    max_overlap=max(max_overlap,collision)
assert max_overlap <1e-4, f'PCB substrate intersects rack by {max_overlap:.5f}mm3'

# Slide-in path check for every bare PCB, offset toward the open front (-Y).
insertion_positions=(-80.,-40.,-16.,0.)
max_slide_collision=0.
for kind,i,z in board_levels():
    for shift in insertion_positions:
        b=reference_pcb(kind,z).translate((0,shift,0))
        max_slide_collision=max(max_slide_collision,body.intersect(b).Volume())
assert max_slide_collision<1e-4,f'Blocked slide-in trajectory: {max_slide_collision}'

for i in range(5):
    rz=R0_Z+i*PAIR_PITCH
    lz=L0_Z+i*PAIR_PITCH
    assert round(lz-(rz+PCB_T),3)==5.0
    if i<4:
        next_rz=R0_Z+(i+1)*PAIR_PITCH
        assert round(next_rz-(lz+PCB_T),3)==20.0

report={
 'frame_vs_bare_pcb_intersection_mm3':results,
 'max_board_sliding_path_intersection_mm3':round(max_slide_collision,8),
 'tested_insertion_offsets_y_mm':insertion_positions,
 'face_to_face_gaps_mm':{'resistor_to_relay':5.0,'relay_to_next_resistor':20.0},
 'physical_populated_component_fit_verified':False,
 'assumed_resistor_height_mm':R_COMPONENT_ASSUMED,
 'assumed_relay_height_mm':L_COMPONENT_ASSUMED,
 'potential_component_clash_mm':{
     'resistor_into_5mm_gap':max(0,R_COMPONENT_ASSUMED-GAP_R_TO_L),
     'relay_into_20mm_gap':max(0,L_COMPONENT_ASSUMED-GAP_L_TO_NEXT_R),
 },
 'upper_relay_PCB_outline_verified':False,
 'fused_mounted_assemblies_not_tested':'Only empty PCB substrate outlines tested',
}
(OUT/'fit_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
