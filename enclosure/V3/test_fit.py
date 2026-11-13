"""Interference tests for V3 universal (one CAD part rotated 0°/180° alternately)."""
import json
from pathlib import Path
import cadquery as cq
from create_v3 import (
    frame, pcb_proxy, LOWER_SIZE, RELAY_PLACEHOLDER, PITCH_SHORT,PITCH_TALL,
    PCB_SUPPORT_Z, POST_OFFSET_X, POST_WIDTH,POST_SLOT_X,
    BASE_T, PCB_LOWER_MAX_H, PCB_RELAY_MAX_H, BOARD_T, BASE_X,BASE_Y,
)
OUT=Path(__file__).resolve().parent
p=frame()
assert p.isValid() and len(p.Solids())==1

def located(s,z,angle=0):
    return s.rotate((0,0,0),(0,0,1),angle).translate((0,0,z))
positions=[(0,0),(PITCH_SHORT,180),(PITCH_SHORT+PITCH_TALL,0),(PITCH_SHORT+PITCH_TALL+PITCH_SHORT,180)]
frames=[located(p,z,a) for z,a in positions]
result={}
# The two pitches must accept the SAME geometry under a 180° rotation.
for i in range(3):
    v=frames[i].intersect(frames[i+1]).Volume()
    result[f'frame_{i}_vs_{i+1}_collision_mm3']=round(v,8)
    assert v < .0001, f'Frame {i}/{i+1} collision {v:.5f} mm3'
# A non-adjacent frame cannot overlap the one two positions below.
for i in range(2):
    v=frames[i].intersect(frames[i+2]).Volume()
    result[f'nonadjacent_frame_{i}_vs_{i+2}_collision_mm3']=round(v,8)
    assert v<.0001
for idx,(z,a) in enumerate(positions):
    w,d,t=(LOWER_SIZE if idx%2==0 else RELAY_PLACEHOLDER)
    pcb=located(pcb_proxy(w,d,0,mounting=idx%2==0),z+PCB_SUPPORT_Z,a)
    v=pcb.intersect(frames[idx]).Volume()
    result[f'pcb_{idx}_vs_own_frame_collision_mm3']=round(v,8)
    assert v < .0001, (idx,v)
    for j,f in enumerate(frames):
        if idx==j:continue
        v=pcb.intersect(f).Volume()
        result[f'pcb_{idx}_vs_frame_{j}_collision_mm3']=round(v,8)
        assert v < .0001, (idx,j,v)
# One edge clip placement must fit either nominal width without specific holes.
assert abs(PITCH_SHORT - BOARD_T - PCB_LOWER_MAX_H - 8.0)<.001
assert PITCH_TALL-BOARD_T-PCB_RELAY_MAX_H>=8
assert POST_WIDTH < POST_SLOT_X*2
assert BASE_X<=220 and BASE_Y<=220
report={
  'universal_frame_variant_count':1,
  'interference':result,
  'zero_intersections':all(v < .0001 for v in result.values()),
  'short_gap_mm':PITCH_SHORT-BOARD_T-PCB_LOWER_MAX_H,
  'tall_gap_mm':PITCH_TALL-BOARD_T-PCB_RELAY_MAX_H,
  'nominal_latch_ledge_engagement_mm':round(POST_OFFSET_X+POST_WIDTH/2+1.30-(POST_OFFSET_X+POST_SLOT_X),2),
  'scope':'CAD proxies and geometric latch positions only. Actual component envelope and snap endurance not verified.',
}
assert report['nominal_latch_ledge_engagement_mm']>=.5
(OUT/'fit_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
