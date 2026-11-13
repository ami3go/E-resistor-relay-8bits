"""V5 ONE-PIECE slide-in rack, 5 resistor PCBs + 5 relay PCBs.

Exact empty PCB face gaps: R(top)->L(bottom) = 5 mm;
L(top)->R_next(bottom) = 20 mm. All PCBs 1.6 mm thick.
A single FDM-printable frame holds ten PCB substrates in side-guide pockets.
Boards load from negative Y; no assembly fastening needed for chassis.

WARNING: these are substrate gaps, NOT adequate clearances for assembled
components. Relay PCB (YHQ001) 145 x 56 mm is NOT verified.
"""
from pathlib import Path
import json
import cadquery as cq

OUT=Path(__file__).resolve().parent
R_X,R_Y,PCB_T=145.,55.,1.6 # KiCad verified bottom resistor PCB
L_X,L_Y=145.,56.       # relay board UNVERIFIED placeholder
R_COMPONENT_ASSUMED=14.0
L_COMPONENT_ASSUMED=27.0
PAIR_COUNT=5
GAP_R_TO_L=5.0
GAP_L_TO_NEXT_R=20.0
PAIR_PITCH=2*PCB_T+GAP_R_TO_L+GAP_L_TO_NEXT_R # 28.2
R0_Z=8.0
L0_Z=R0_Z+PCB_T+GAP_R_TO_L  # 14.6
FRAME_X,FRAME_Y,FRAME_H=174.,84.,138.
BOTTOM_T=4.8
SIDE_W=8.0
# Positive sidewall: x in [79,87]; guides join x in [73.6,80].
INNER_FACE=FRAME_X/2-SIDE_W # 79.0
GUIDE_MIN=73.6
SHELF_INNER=71.5
GROOVE_TOP_CLEAR=0.8
GUIDE_Y_CENTERS=(-24.75,24.75)
GUIDE_Y_LENGTH=13.0
BACK_STOP_Y=31.8
FRONT_CABLE_SLOTS=4

def cuboid(x,y,z,dx,dy,dz):
    return cq.Workplane('XY').box(dx,dy,dz,centered=(True,True,False)).val().translate((x,y,z))

def side_piece(sign):
    # Two continuous uprights per side, with a full-height cable/service window
    # from y=-14..+18.  This avoids a roof bridge, reduces print material,
    # and provides access to J9 near one resistor board edge and other cables.
    xc=sign*(FRAME_X/2-SIDE_W/2)
    front=cuboid(xc,-28.0,0,SIDE_W,28.0,FRAME_H)  # y [-42,-14]
    rear=cuboid(xc,30.0,0,SIDE_W,24.0,FRAME_H)   # y [18,42]
    return front.fuse(rear)

def board_levels():
    return [(_type,i,z) for i in range(PAIR_COUNT) for _type,z in (
        ('resistor',R0_Z+i*PAIR_PITCH),('relay',L0_Z+i*PAIR_PITCH))]

def guide_parts(sign,y,z):
    """Guide located only near PCB corners: low-profile 2.1 mm print overhang.

    Continuous fence lies OUTSIDE nominal PCB boundary and connects to sidewall.
    Support lip ends 1 mm below PCB. Cap starts >=0.8 mm above PCB.
    """
    fence_start,fence_end=GUIDE_MIN,INNER_FACE+1.0
    fence=cuboid(sign*(fence_start+fence_end)/2,y,0,
                 fence_end-fence_start,GUIDE_Y_LENGTH,FRAME_H)
    a,b=SHELF_INNER,INNER_FACE+0.7
    low=cuboid(sign*(a+b)/2,y,z-1.35,b-a,GUIDE_Y_LENGTH,1.35)
    high=cuboid(sign*(a+b)/2,y,z+PCB_T+GROOVE_TOP_CLEAR,b-a,GUIDE_Y_LENGTH,1.0)
    return fence,low,high

def frame():
    # Full-height upright segments and single bottom ring avoid long bridges.
    w=cq.Workplane('XY').rect(FRAME_X,FRAME_Y).extrude(BOTTOM_T).edges('|Z').fillet(4.4).val()
    inner=cq.Workplane('XY').rect(FRAME_X-2*SIDE_W, FRAME_Y-2*SIDE_W).extrude(BOTTOM_T+2).val().translate((0,0,-1))
    solids=[w.cut(inner),side_piece(+1),side_piece(-1)]
    for sx in (-1,1):
        for gy in GUIDE_Y_CENTERS:
            a,b=GUIDE_MIN,INNER_FACE+1
            solids.append(cuboid(sx*(a+b)/2,gy,0,b-a,GUIDE_Y_LENGTH,FRAME_H))
    for kind,i,z in board_levels():
        for sx in (-1,1):
            for y in GUIDE_Y_CENTERS:
                _,support,roof=guide_parts(sx,y,z)
                solids.extend((support,roof))
            solids.append(cuboid(sx*72.0,BACK_STOP_Y,z-.25,2.6,2.0,3.2))
    s=solids[0].fuse(*solids[1:]).clean()
    for x in (-63.,63.):
        for y in (-38.0,38.0):
            s=s.cut(cq.Solid.makeCylinder(1.7,BOTTOM_T+.2,cq.Vector(x,y,-.1)))
    return s.clean()

def reference_pcb(kind,z):
    x,y=(R_X,R_Y) if kind=='resistor' else (L_X,L_Y)
    return cuboid(0,1.5,z,x,y,PCB_T)

def assembly(body,exploded=False):
    a=cq.Assembly(name='V5_ONE_PIECE_'+('exploded' if exploded else 'inserted'))
    a.add(body,name='one_piece_10_slot_chassis',color=cq.Color(.23,.30,.39))
    for kind,i,z in board_levels():
        shape=reference_pcb(kind,0)
        y_offset=-99. if exploded else 0.
        col=cq.Color(.11,.50,.28) if kind=='resistor' else cq.Color(.08,.43,.68)
        a.add(shape,name=f'{kind}_pcb_{i+1}_PLACEHOLDER',
              loc=cq.Location(cq.Vector(0,y_offset,z)),color=col)
    return a

def main():
    assert abs(L0_Z-(R0_Z+PCB_T)-GAP_R_TO_L)<1e-7
    assert abs(PAIR_PITCH+R0_Z-(L0_Z+PCB_T)-GAP_L_TO_NEXT_R)<1e-7
    assert FRAME_H>max(z+PCB_T for _,_,z in board_levels())+5
    assert FRAME_X<=220 and FRAME_Y<=220 and FRAME_H<=250
    body=frame()
    assert body.isValid(), 'invalid BRep'
    assert len(body.Solids())==1, f'Expected one printable solid, got {len(body.Solids())}'
    cq.exporters.export(body,str(OUT/'onepiece_frame.step'))
    cq.exporters.export(body,str(OUT/'onepiece_frame.stl'),tolerance=.12,angularTolerance=.18)
    assembly(body).save(str(OUT/'ten_pcbs_assembly.step'),cq.exporters.ExportTypes.STEP)
    assembly(body,True).save(str(OUT/'ten_pcbs_exploded.step'),cq.exporters.ExportTypes.STEP)
    import trimesh
    m=trimesh.load(OUT/'onepiece_frame.stl',force='mesh')
    assert m.is_watertight and len(m.split())==1, 'invalid or disconnected STL'
    report={
        'valid_brep':body.isValid(), 'solid_count':len(body.Solids()),
        'stl_watertight':bool(m.is_watertight),'stl_connected_count':len(m.split()),
        'production_stl_count':1,'print_quantity':1,
        'board_counts':{'resistor':5,'relay':5},
        'print_envelope_mm':[FRAME_X,FRAME_Y,FRAME_H],
        'bottom_board_z_mm':R0_Z,'first_relay_board_z_mm':L0_Z,
        'pair_pitch_mm':PAIR_PITCH,'resistor_to_relay_substrate_gap_mm':GAP_R_TO_L,
        'relay_to_next_resistor_substrate_gap_mm':GAP_L_TO_NEXT_R,
        'last_relay_bottom_mm':L0_Z+(PAIR_COUNT-1)*PAIR_PITCH,
        'last_relay_top_mm':L0_Z+(PAIR_COUNT-1)*PAIR_PITCH+PCB_T,
        'model_volume_mm3':round(body.Volume(),1),
        'upper_relay_board_outline_verified':False,
        'populated_resistor_components_assumed_mm_NOT_ACCOUNTED_FOR':R_COMPONENT_ASSUMED,
        'populated_relay_components_assumed_mm_NOT_ACCOUNTED_FOR':L_COMPONENT_ASSUMED,
        'potential_resistor_overlap_mm':max(0,R_COMPONENT_ASSUMED-GAP_R_TO_L),
        'potential_relay_overlap_mm':max(0,L_COMPONENT_ASSUMED-GAP_L_TO_NEXT_R),
        'qualified_to_print':'prototype-only: component clearance, wiring and practical fit not checked',
        'rails':'four vertical guide spines with shallow rails at ten board levels',
    }
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
