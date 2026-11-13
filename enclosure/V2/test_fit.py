"""Offline V2 nominal mechanical fit checks; real populated boards are NOT modeled."""
import json
from pathlib import Path
import cadquery as cq
from create_v2 import R_X,R_Y,R_HX,R_HY,U_X,U_Y,LOW_BOSS_TOP,UP_PCB_BOTTOM,TOWER_TOP,refpcb
HERE=Path(__file__).resolve().parent
body=cq.importers.importStep(str(HERE/'chassis_v2.step')).val()
assert body.isValid() and len(body.Solids())==1
proxies={
    'resistor_pcb':refpcb(R_X,R_Y,LOW_BOSS_TOP,R_HX,R_HY),
    'relay_pcb_nominal':refpcb(U_X,U_Y,UP_PCB_BOTTOM),
    'next_chassis':body.translate((0,0,TOWER_TOP)),
}
results={}
for name,shape in proxies.items():
    volume=body.intersect(shape).Volume()
    results[name]=volume
    assert volume<1e-4,f'{name} collides with chassis by {volume:.3f} mm^3'
(HERE/'fit_check.json').write_text(json.dumps({'nominal_intersection_volume_mm3':results,'note':'proxies only, not actual populated boards'},indent=2)+'\n')
print('No nominal chassis/PCB/second-chassis collisions:',results)
