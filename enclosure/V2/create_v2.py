"""Enclosure V2: single-body screwless open PCB stack.
Run: python create_v2.py. CadQuery >=2.3, trimesh for mesh validation.
Units mm; default upper board size is a DESIGN PLACEHOLDER, not measurement.
"""
from __future__ import annotations
import json
from pathlib import Path
import cadquery as cq

OUT=Path(__file__).resolve().parent
# KiCad-verified resistor board / holes.
R_X,R_Y,R_HX,R_HY,PCB_T=145.,55.,138.,48.,1.6
# YHQ001 dimensions & edge conditions not measured; change before final print.
U_X,U_Y=145.,56.
# Open-frame geometry; 220 x 220 mm printer friendly.
OUT_X,OUT_Y=174.,82.
P_X,P_Y=81.,35.
BASE_T=4.4
LOW_BOSS_TOP=8.0
LOW_PCB_TOP=LOW_BOSS_TOP+PCB_T
UP_PCB_BOTTOM=32.0
UP_PCB_TOP=UP_PCB_BOTTOM+PCB_T
TOWER_TOP=74.0
STACK_PEG_H=4.0
# Assumed lower populated component top above resistor PCB: MUST MEASURE.
LOW_COMPONENT_H=14.0
UP_COMPONENT_H=27.0


def cyl(x,y,z,d,h): return cq.Solid.makeCylinder(d/2,h,cq.Vector(x,y,z))
def box(x,y,z,w,d,h):return cq.Workplane('XY').box(w,d,h,centered=(True,True,False)).val().translate((x,y,z))
def ring(w,d,t,border,r=4.0):
    a=cq.Workplane('XY').rect(w,d).extrude(t).edges('|Z').fillet(r).val()
    b=cq.Workplane('XY').rect(w-2*border,d-2*border).extrude(t+2).val().translate((0,0,-1))
    return a.cut(b)
def brace(x1,y1,x2,y2,z,height,width):
    """Plan-view capsule straight, from base corner to PCB mounting boss."""
    import math
    L=math.hypot(x2-x1,y2-y1); a=math.degrees(math.atan2(y2-y1,x2-x1))
    body=box(0,0,z,L,width,height).rotate((0,0,0),(0,0,1),a).translate(((x1+x2)/2,(y1+y2)/2,0))
    return body.fuse(cyl(x1,y1,z,width,height)).fuse(cyl(x2,y2,z,width,height)).clean()
def angled_gusset(x0,y0,x1,y1,z0,z1):
    """Loft is inward/downward supported; rise >= horizontal reach."""
    assert z1-z0 >= ((x1-x0)**2+(y1-y0)**2)**0.5
    return (cq.Workplane('XY',origin=(0,0,z0)).center(x0,y0).circle(4.6)
            .workplane(offset=z1-z0).center(x1-x0,y1-y0).circle(4.6).loft(combine=True).val())
def lower_snap(x,y):
    # Ø2.6 shaft; head Ø3.55 at 1.9 mm above PCB top, tapered top for insertion.
    # The 0.8-mm split flexes for a Ø3.2 mm hole. Small head overhang printed upright.
    shaft=cyl(x,y,LOW_BOSS_TOP,2.6,2.0)
    lip=cyl(x,y,LOW_BOSS_TOP+2.0,3.50,0.55)
    cone=cq.Solid.makeCone(1.75,1.1,1.70,cq.Vector(x,y,LOW_BOSS_TOP+2.55))
    result=shaft.fuse(lip).fuse(cone)
    return result.cut(box(x,y,LOW_BOSS_TOP+.75,0.8,4.0,3.7)).clean()
def edge_clip(sx,sy):
    """End-edge snap at x +/-73, y +/-20, above upper seating surface.
    Clip toe joins corner tower via a printed steep gusset; no long unsupported bridges.
    """
    x=sx*(U_X/2+1.5); y=sy*(U_Y/2-8.0)
    # vertical flexible beam: 1.4 mm x 6.5 mm section; local fit depends on PCB edge.
    stem=box(x,y,23.1,1.4,6.5,14.4)
    # Lip catches approximately 0.7 mm of the board x edge.
    lip=box(x-sx*1.3,y,UP_PCB_TOP+0.16,1.9,6.5,0.75)
    taper=(cq.Workplane('XY',origin=(0,0,UP_PCB_TOP+0.91))
        .center(x-sx*1.3,y).rect(1.9,6.5)
        .workplane(offset=1.15).center(sx*0.7,0).rect(0.7,6.5)
        .loft(combine=True).val())
    return stem.fuse(lip).fuse(taper).clean()

def main_body():
    solid=ring(OUT_X,OUT_Y,BASE_T,6.2)
    # Integrated four tall corner pillars: no threaded inserts or separate posts.
    for sx in (-1,1):
        for sy in (-1,1):
            px,py=sx*P_X,sy*P_Y
            bx,by=sx*(R_HX/2),sy*(R_HY/2)
            solid=solid.fuse(cyl(px,py,0,12.0,TOWER_TOP))
            solid=solid.fuse(brace(px,py,bx,by,0,BASE_T,10.2))
            solid=solid.fuse(cyl(bx,by,BASE_T,8.3,LOW_BOSS_TOP-BASE_T))
            solid=solid.fuse(lower_snap(bx,by))
            ux,uy=sx*(U_X/2-4.5),sy*(U_Y/2-4.5)
            solid=solid.fuse(angled_gusset(px,py,ux,uy,12.0,29.5))
            solid=solid.fuse(cyl(ux,uy,29.5,9.0,UP_PCB_BOTTOM-29.5))
            # Self-aligning four-way intermodule peg, z 74..78.
            solid=solid.fuse(cyl(px,py,TOWER_TOP,5.15,2.15))
            solid=solid.fuse(cq.Solid.makeCone(2.575,1.85,STACK_PEG_H-2.15,cq.Vector(px,py,TOWER_TOP+2.15)))
            y_clip=sy*(U_Y/2-8.0)
            x_clip=sx*(U_X/2+1.5)
            solid=solid.fuse(angled_gusset(px,py,x_clip,y_clip,4.5,23.3))
            solid=solid.fuse(edge_clip(sx,sy))
    # 5.60 mm sockets with 5.15 mm pegs: 0.45 mm diametral clearance.
    # Locating/friction engagement only; NOT a positively locked stack.
    for sx in (-1,1):
        for sy in (-1,1):
            x,y=sx*P_X,sy*P_Y
            solid=solid.cut(cyl(x,y,-.1,5.60,STACK_PEG_H+.35))
    # 4 cable-tie pass-through slots in lower rails, for optional stack restraint.
    for x in (-40.,40.):
        for y in (-36.9,36.9):
            solid=solid.cut(box(x,y,-.1,12.,2.8,BASE_T+.2))
    return solid.clean()

def refpcb(x,y,z,diamx=None,diamy=None):
    s=box(0,0,z,x,y,PCB_T)
    if diamx and diamy:
        for sx in (-1,1):
            for sy in (-1,1):s=s.cut(cyl(sx*diamx/2,sy*diamy/2,z-.1,3.2,PCB_T+.2))
    return s.clean()

def assemble(chassis,stack=1,exploded=False):
    assy=cq.Assembly(name=f'Eresistor_V2_{stack}level'+('_exploded' if exploded else ''))
    colors=(cq.Color(.24,.29,.34),cq.Color(.13,.46,.27),cq.Color(.09,.42,.32))
    for i in range(stack):
        offset=i*TOWER_TOP
        e=0 if not exploded else (i+1)*50
        assy.add(chassis,name=f'chassis_{i+1}',loc=cq.Location(cq.Vector(0,0,offset+e)),color=colors[0])
        r=refpcb(R_X,R_Y,0,R_HX,R_HY)
        u=refpcb(U_X,U_Y,0)
        assy.add(r,name=f'resistor_PCB_{i+1}_ref',loc=cq.Location(cq.Vector(0,0,offset+LOW_BOSS_TOP+e+(20 if exploded else 0))),color=colors[1])
        assy.add(u,name=f'relay_PCB_{i+1}_UNVERIFIED_ref',loc=cq.Location(cq.Vector(0,0,offset+UP_PCB_BOTTOM+e+(60 if exploded else 0))),color=colors[2])
    return assy

def main():
    assert abs((UP_PCB_BOTTOM-LOW_PCB_TOP)-LOW_COMPONENT_H-8.4)<0.001
    assert U_X/2+1.5< P_X
    assert U_Y/2+2.1< P_Y
    body=main_body()
    assert body.isValid(), 'BRep invalid'
    assert len(body.Solids())==1, f'{len(body.Solids())} connected solids not one body'
    cq.exporters.export(body,str(OUT/'chassis_v2.step'))
    cq.exporters.export(body,str(OUT/'chassis_v2.stl'),tolerance=0.08,angularTolerance=0.14)
    assemble(body,1).save(str(OUT/'module_reference.step'),cq.exporters.ExportTypes.STEP)
    assemble(body,2).save(str(OUT/'two_modules_reference.step'),cq.exporters.ExportTypes.STEP)
    assemble(body,1,True).save(str(OUT/'exploded_reference.step'),cq.exporters.ExportTypes.STEP)
    import trimesh
    mesh=trimesh.load(OUT/'chassis_v2.stl',force='mesh')
    assert mesh.is_watertight,'STL not watertight'
    assert len(mesh.split())==1,'STL not one connected mesh'
    data={'STL_watertight':bool(mesh.is_watertight),'STL_connected_parts':len(mesh.split()),'BRep_valid':bool(body.isValid()),'BRep_solids':len(body.Solids()),'footprint_mm':[OUT_X,OUT_Y], 'max_height_mm':TOWER_TOP+STACK_PEG_H,'build_volume_mm':[OUT_X,OUT_Y,TOWER_TOP+STACK_PEG_H], 'bottom_board_verified_mm':[R_X,R_Y], 'lower_board_bottom_z_mm':LOW_BOSS_TOP,'relay_board_bottom_nominal_z_mm':UP_PCB_BOTTOM,'lower_clearance_nominal_mm':round(UP_PCB_BOTTOM-LOW_PCB_TOP-LOW_COMPONENT_H,2),'next_module_pitch_mm':TOWER_TOP,'relay_headroom_nominal_mm':TOWER_TOP-(UP_PCB_TOP+UP_COMPONENT_H),'upper_pcb_placeholder_mm':[U_X,U_Y],'required_printed_parts_per_level':1,'nominal_screws_per_level':0,'volume_mm3':round(body.Volume(),1)}
    (OUT/'verification.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))

if __name__=='__main__':main()
