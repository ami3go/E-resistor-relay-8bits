"""V5: compact modular shelf rack for 5 resistor and 5 relay PCBs.

Five identical single-piece, support-friendly shelf units hold one resistor PCB
below one relay PCB, with PCB top-to-underside gaps 5mm then 20mm (alternating).
Boards slide from -Y. Four corner split-snap pegs join units without screws.

Resistor outline 145x55x1.6 from actual KiCad layout. YHQ001 upper relay PCB
145x56mm is an UNVERIFIED mechanical placeholder. Component dimensions may
NOT FIT into these gaps: this is not a physical-fit-qualified design.
"""
from pathlib import Path
import math, json
import cadquery as cq

HERE=Path(__file__).resolve().parent
R_X,R_Y,PCB_T=145.,55.,1.6
U_X,U_Y=145.,56.  # RELAY PLACEHOLDER — VERIFY
R_COMPONENT_ASSUMED=14.0   # not used to set gaps
U_COMPONENT_ASSUMED=27.0   # not used to set gaps
GAP_R_TO_U=5.0             # resistor PCB TOP to relay PCB BOTTOM
GAP_U_TO_NEXT_R=20.0       # relay PCB TOP to next resistor PCB BOTTOM
R_Z=8.0
U_Z=R_Z+PCB_T+GAP_R_TO_U
PITCH=(U_Z+PCB_T+GAP_U_TO_NEXT_R)-R_Z  # 28.2 mm
FRAME_X,FRAME_Y,BASE_T=174.0,84.0,4.8
POST_X,POST_Y,POST_DIAM=80.5,35.0,13.0
POST_H=PITCH
GUIDE_X,GUIDE_Y=75.25,24.75
GUIDE_X_W,GUIDE_Y_LENGTH=4.3,13.0
GROOVE_SHELF_X=73.55
GROOVE_SHELF_W=5.3
SLOT_HEIGHT=2.45
PEG_STEM_D,PEG_BARB_D,SOCKET_ENTRY_D,SOCKET_BARB_D=4.15,5.35,4.75,6.10
PEG_STEM_H,PEG_HEAD_H,PEG_SPLIT_W=2.95,2.15,0.85
SOCKET_STEP_Z,SOCKET_DEPTH=2.6,5.6

def cylinder(x,y,z,diam,h):
    return cq.Solid.makeCylinder(diam/2,h,cq.Vector(x,y,z))

def cuboid(x,y,z,w,l,h):
    return cq.Workplane('XY').box(w,l,h,centered=(True,True,False)).val().translate((x,y,z))

def ring():
    outer=cq.Workplane('XY').rect(FRAME_X,FRAME_Y).extrude(BASE_T).edges('|Z').fillet(4.5).val()
    inner=cq.Workplane('XY').rect(FRAME_X-14,FRAME_Y-14).extrude(BASE_T+1).val().translate((0,0,-.5))
    return outer.cut(inner)

def brace(x1,y1,x2,y2,z,t,w):
    length=math.hypot(x2-x1,y2-y1)
    angle=math.degrees(math.atan2(y2-y1,x2-x1))
    mid=cuboid(0,0,z,length,w,t).rotate((0,0,0),(0,0,1),angle).translate(((x1+x2)/2,(y1+y2)/2,0))
    return mid.fuse(cylinder(x1,y1,z,w,t)).fuse(cylinder(x2,y2,z,w,t)).clean()

def dock_peg(x,y):
    shaft=cylinder(x,y,POST_H,PEG_STEM_D,PEG_STEM_H)
    head=cq.Solid.makeCone(PEG_BARB_D/2,1.62,PEG_HEAD_H,cq.Vector(x,y,POST_H+PEG_STEM_H))
    peg=shaft.fuse(head)
    return peg.cut(cuboid(x,y,POST_H-2.5,PEG_SPLIT_W,6.2,PEG_STEM_H+PEG_HEAD_H+2.6)).clean()

def guide_group(sx,sy,board_z):
    """Short edge channels, PCB guides open from front; no full-length side rail."""
    x=sx*GUIDE_X
    y=sy*GUIDE_Y
    wall=cuboid(x,y,0,GUIDE_X_W,GUIDE_Y_LENGTH,board_z+3.75)
    shelf=cuboid(sx*GROOVE_SHELF_X,y,board_z-1.65,GROOVE_SHELF_W,GUIDE_Y_LENGTH,1.65)
    lip=cuboid(sx*GROOVE_SHELF_X,y,board_z+SLOT_HEIGHT,GROOVE_SHELF_W,GUIDE_Y_LENGTH,1.25)
    stop=cuboid(sx*72.95,31.25,board_z-.02,3.0,1.1,3.7) if sy>0 else None
    return wall.fuse(shelf).fuse(lip).fuse(stop) if stop else wall.fuse(shelf).fuse(lip)

def shelf_unit():
    body=ring()
    for sx in (-1,1):
        for sy in (-1,1):
            x,y=sx*POST_X,sy*POST_Y
            body=body.fuse(cylinder(x,y,0,POST_DIAM,POST_H))
            body=body.fuse(brace(x,y,sx*GUIDE_X,sy*GUIDE_Y,0,BASE_T,7.3))
            body=body.fuse(guide_group(sx,sy,R_Z))
            body=body.fuse(guide_group(sx,sy,U_Z))
            body=body.fuse(dock_peg(x,y))
    for sx in (-1,1):
        for sy in (-1,1):
            x,y=sx*POST_X,sy*POST_Y
            body=body.cut(cylinder(x,y,-.10,SOCKET_ENTRY_D,SOCKET_DEPTH+.2))
            body=body.cut(cylinder(x,y,SOCKET_STEP_Z,SOCKET_BARB_D,SOCKET_DEPTH-SOCKET_STEP_Z+.10))
            body=body.cut(cq.Solid.makeCylinder(1.2,14,cq.Vector(x-7,y,3.95),cq.Vector(1,0,0)))
    for x in (-40.,40.):
        for y in (-38.,38.):
            body=body.cut(cuboid(x,y,-.2,11.,2.4,BASE_T+.4))
    return body.clean()

def pcb_proxy(x,y,z):
    return cuboid(0,1.5,z,x,y,PCB_T)

def make_assy(body,levels=5,exploded=False):
    assembly=cq.Assembly(name='V5_shelf_10boards_'+('exploded' if exploded else 'assembled'))
    for i in range(levels):
        base_z=i*PITCH+(i*25 if exploded else 0)
        assembly.add(body,name=f'shelf_unit_{i+1}',loc=cq.Location(cq.Vector(0,0,base_z)),color=cq.Color(.22,.27,.34))
        for kind,dim,z,col in (
            ('resistor',(R_X,R_Y),R_Z,cq.Color(.10,.48,.25)),
            ('relay',(U_X,U_Y),U_Z,cq.Color(.06,.41,.37))):
            delta=(16 if kind=='resistor' else 30) if exploded else 0
            assembly.add(pcb_proxy(*dim,z),name=f'{kind}_pcb_{i+1}_reference',
                loc=cq.Location(cq.Vector(0,0,base_z+delta)),color=col)
    return assembly

def main():
    assert abs((U_Z-(R_Z+PCB_T))-GAP_R_TO_U)<1e-6
    assert abs((PITCH+R_Z-(U_Z+PCB_T))-GAP_U_TO_NEXT_R)<1e-6
    assert FRAME_X<=220 and FRAME_Y<=220 and POST_H+PEG_STEM_H+PEG_HEAD_H<=250
    solid=shelf_unit()
    assert solid.isValid() and len(solid.Solids())==1,'One printable connected solid required'
    cq.exporters.export(solid,str(HERE/'shelf_unit.stl'),tolerance=.085,angularTolerance=.14)
    cq.exporters.export(solid,str(HERE/'shelf_unit.step'))
    make_assy(solid,1).save(str(HERE/'one_pair_reference.step'),cq.exporters.ExportTypes.STEP)
    make_assy(solid,5).save(str(HERE/'five_pair_rack.step'),cq.exporters.ExportTypes.STEP)
    make_assy(solid,2,True).save(str(HERE/'exploded_pair_reference.step'),cq.exporters.ExportTypes.STEP)
    import trimesh
    mesh=trimesh.load(HERE/'shelf_unit.stl',force='mesh')
    assert mesh.is_watertight and len(mesh.split())==1
    report={
        'STL_watertight':bool(mesh.is_watertight),'STL_connected_parts':len(mesh.split()),
        'BRep_valid':bool(solid.isValid()),'BRep_solids':len(solid.Solids()),
        'distinct_printed_models':1,'print_quantity':5,'resistor_board_quantity':5,'relay_board_quantity':5,
        'per_unit_footprint_mm':[FRAME_X,FRAME_Y],
        'per_unit_print_height_mm':round(POST_H+PEG_STEM_H+PEG_HEAD_H,2),
        'assembled_five_unit_height_mm':round(4*PITCH+POST_H+PEG_STEM_H+PEG_HEAD_H,2),
        'resistor_pcb_under_z_mm':R_Z,'relay_pcb_under_z_mm':U_Z,
        'air_gap_R_PCB_top_to_U_PCB_bottom_mm':GAP_R_TO_U,
        'air_gap_U_PCB_top_to_next_R_PCB_bottom_mm':GAP_U_TO_NEXT_R,
        'assumed_resistor_component_height_mm_NOT_USED_IN_SPACING':R_COMPONENT_ASSUMED,
        'assumed_relay_component_height_mm_NOT_USED_IN_SPACING':U_COMPONENT_ASSUMED,
        'provisional_resistor_components_intrude_gap_by_mm':max(0,R_COMPONENT_ASSUMED-GAP_R_TO_U),
        'provisional_relay_components_intrude_gap_by_mm':max(0,U_COMPONENT_ASSUMED-GAP_U_TO_NEXT_R),
        'mechanical_fit_of_populated_boards':'NOT VERIFIED: likely clearance clash at both shelf intervals',
        'relay_pcb_footprint_unverified':True,
        'board_rails':'four short edge guide pockets each PCB, slide toward +Y',
        'stack_lock':'4 split snap pegs into relief-bore sockets per interface',
        'volume_mm3':round(solid.Volume(),1)
    }
    (HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
