"""V3 UNIVERSAL: one printable PCB carrier type for both PCBs and all stack levels.

Two copies per complete E-resistor assembly, alternately turned 180 deg about Z.
Shared *interleaving* corner towers permit two clip positions: 23.6 / 40.0 mm.
- short pitch: resistor -> relay, with 8 mm assumed free component clearance.
- tall pitch: relay -> next resistor, leaving 11.4 mm assumed headroom.
No extra spacers / different mounting variants / mounting-hole constraints.

The upper relay board outline is a PLACEHOLDER: neither relay PCB dimensions nor
populated component envelope has been measured on hardware.

Run: python create_v3.py  (CadQuery >=2.3 and trimesh)
"""
from pathlib import Path
import math, json
import cadquery as cq

OUT = Path(__file__).resolve().parent
# Verified KiCad resistor PCB, and illustrative Ethernet relay PCB
LOWER_SIZE=(145., 55., 1.6)
RELAY_PLACEHOLDER=(145., 56., 1.6)
# Universal PCB edge-mount allows 144..146 mm length; 54..57 mm width.
PCB_LENGTH_NOM=145.
PCB_SUPPORT_Z=7.0
BOARD_T=1.6
PCB_LOWER_MAX_H=14.0       # unmeasured; determine before printing
PCB_RELAY_MAX_H=27.0       # unmeasured; determine before printing
BASE_X,BASE_Y=174.,82.
BASE_T=5.0
CORNERS_X,CORNERS_Y=76.,34.5
POST_OFFSET_X=2.85
POST_WIDTH=4.6
POST_DEPTH=9.0
POST_TIP_H=47.0
POST_SLOT_X=2.95
POST_SLOT_Y=5.05
PITCH_SHORT=23.6
PITCH_TALL=40.0
CATCH_Z=(PITCH_SHORT+BASE_T+0.12, PITCH_TALL+BASE_T+0.12)
MAX_BUILD_Z=POST_TIP_H


def box(x,y,z,w,d,h):
    return cq.Workplane('XY').box(w,d,h,centered=(True,True,False)).val().translate((x,y,z))

def cylinder(x,y,z,diam,h):
    return cq.Solid.makeCylinder(diam/2,h,cq.Vector(x,y,z))

def capsule(x1,y1,x2,y2,width,z,height):
    length=math.hypot(x2-x1,y2-y1)
    a=math.degrees(math.atan2(y2-y1,x2-x1))
    core=box(0,0,z,length,width,height).rotate((0,0,0),(0,0,1),a).translate(((x1+x2)/2,(y1+y2)/2,0))
    return core.fuse(cylinder(x1,y1,z,width,height)).fuse(cylinder(x2,y2,z,width,height)).clean()

def snap_ramp(x,y,z):
    """PETG flex wedge on OUTER (+x) post edge; angled entry, square lock shoulder.

    An adjacent 47-mm semi-column deflects ~0.7 mm during assembly. Cantilever
    strength, fatigue, layer adhesion MUST be physically verified with coupons.
    """
    # Post x max = x+post_width/2; protrusion into receiver's catch ledge.
    inner=x+POST_WIDTH/2-0.24
    outer=x+POST_WIDTH/2+1.30
    # XZ workplane extrudes in -Y from 0, translated so centred y at corner.
    return (cq.Workplane('XZ')
        .polyline([(inner,z),(outer,z),(inner,z+1.65)]).close()
        .extrude(4.0).val().translate((0,y+2.0,0)))

def clip_end(sx,sy):
    """Universal short-end snap fits BOTH nominal PCB widths, no holes required.

    145 mm board x length; upper components close to the ends still need inspection.
    """
    x=sx*(PCB_LENGTH_NOM/2+1.40)
    y=sy*19.5
    # Flat flexible vertical beam on end of frame
    stem=box(x,y,BASE_T,1.65,6.5,5.6)
    # Lip bottom just above PCB top; 0.35 mm edge overhang nominal
    lip=box(x-sx*1.24,y,PCB_SUPPORT_Z+BOARD_T+0.16,1.65,6.5,0.62)
    taper=(cq.Workplane('XY',origin=(0,0,PCB_SUPPORT_Z+BOARD_T+.78))
       .center(x-sx*1.24,y).rect(1.65,6.5)
       .workplane(offset=1.25).center(sx*.70,0).rect(.60,6.5)
       .loft(combine=True).val())
    return stem.fuse(lip).fuse(taper).clean()

def frame():
    outer=cq.Workplane('XY').rect(BASE_X,BASE_Y).extrude(BASE_T).edges('|Z').fillet(3.5).val()
    cutout=box(0,0,-1,BASE_X-2*6.2,BASE_Y-2*6.2,BASE_T+2)
    s=outer.cut(cutout)
    # Four cradle arms, support underside (away from corner mounting holes)
    for sx in (-1,1):
        for sy in (-1,1):
            cx,cy=sx*CORNERS_X,sy*CORNERS_Y
            dx,dy=sx*66.7,sy*20.5
            # Thickened corner base + receiver ledge on both sides of the channel
            s=s.fuse(box(cx,cy,0,18.0,12.0,BASE_T))
            s=s.fuse(capsule(cx,cy,dx,dy,9.0,0,BASE_T))
            s=s.fuse(cylinder(dx,dy,0,8.8,PCB_SUPPORT_Z))
            # Strengthening under the PCB edge clip, fully supported from bed
            px=sx*(PCB_LENGTH_NOM/2+1.40);py=sy*19.5
            s=s.fuse(capsule(dx,dy,px,py,6.8,0,BASE_T))
            s=s.fuse(clip_end(sx,sy))
            # One local x+ half-column; when alternating frames rotate 180 deg,
            # the two half-columns complement rather than collide.
            xpost=cx+POST_OFFSET_X
            s=s.fuse(box(xpost,cy,0,POST_WIDTH,POST_DEPTH,POST_TIP_H))
            for z in CATCH_Z:
                s=s.fuse(snap_ramp(xpost,cy,z))
    # Through base, a clearance pocket for the *other* frame's half-column.
    # When the upper copy is rotated 180 deg it nests with the lower tower.
    for sx in (-1,1):
        for sy in (-1,1):
            cx,cy=sx*CORNERS_X,sy*CORNERS_Y
            s=s.cut(box(cx-POST_OFFSET_X,cy,-.15,
                POST_SLOT_X*2,POST_SLOT_Y*2,BASE_T+.30))
    # Four external tie points for extra restraint until physical snap testing.
    for xx in (-42.,42.):
        for yy in (-37.8,37.8):
            s=s.cut(box(xx,yy,-.1,11.5,2.6,BASE_T+.2))
    return s.clean()

def pcb_proxy(width,depth,z=0,mounting=False):
    s=box(0,0,z,width,depth,BOARD_T)
    if mounting:
        for sx in (-1,1):
            for sy in (-1,1):
                s=s.cut(cylinder(sx*69.,sy*24.,z-.1,3.2,BOARD_T+.2))
    return s.clean()


def pose(i):
    """Two identical printed frames per electrical assembly; alternating half-post orientation."""
    n=i//2
    z=n*(PITCH_SHORT+PITCH_TALL)+(PITCH_SHORT if i%2 else 0)
    return cq.Location(cq.Vector(0,0,z),cq.Vector(0,0,1),180 if i%2 else 0)

def assembly(part,modules=1,exploded=False):
    a=cq.Assembly(name=f'V3_Universal_{modules}module_'+('Exploded' if exploded else 'Assembled'))
    for i in range(modules*2):
        z=(i//2)*(PITCH_SHORT+PITCH_TALL)+(PITCH_SHORT if i%2 else 0)
        theta=180 if i%2 else 0
        move=(i+1)*30 if exploded else 0
        a.add(part,name=f'universal_frame_{i+1}',loc=cq.Location(cq.Vector(0,0,z+move),cq.Vector(0,0,1),theta),color=cq.Color(.20,.28,.36) if i%2==0 else cq.Color(.33,.44,.55))
        sx,sy,th = (LOWER_SIZE if i%2==0 else RELAY_PLACEHOLDER)
        ref=pcb_proxy(sx,sy,0,mounting=(i%2==0))
        a.add(ref,name=f'{"resistor" if i%2==0 else "relay_UNVERIFIED"}_pcb_{i//2+1}',
            loc=cq.Location(cq.Vector(0,0,z+PCB_SUPPORT_Z+move+(12 if exploded else 0)),cq.Vector(0,0,1),theta),color=cq.Color(.09,.47,.26) if i%2==0 else cq.Color(.05,.40,.40))
    return a

def main():
    assert abs(PITCH_SHORT-BOARD_T-PCB_LOWER_MAX_H-8.0)<1e-6
    assert PITCH_TALL-BOARD_T-PCB_RELAY_MAX_H>=8.0
    s=frame()
    assert s.isValid() and len(s.Solids())==1, 'Frame invalid or disconnected'
    cq.exporters.export(s,str(OUT/'universal_frame.step'))
    cq.exporters.export(s,str(OUT/'universal_frame.stl'),tolerance=.08,angularTolerance=.14)
    assembly(s,1).save(str(OUT/'module_assembly.step'),cq.exporters.ExportTypes.STEP)
    assembly(s,2).save(str(OUT/'two_modules.step'),cq.exporters.ExportTypes.STEP)
    assembly(s,1,True).save(str(OUT/'exploded_assembly.step'),cq.exporters.ExportTypes.STEP)
    import trimesh
    mesh=trimesh.load(OUT/'universal_frame.stl',force='mesh')
    assert mesh.is_watertight and len(mesh.split())==1, 'STL not watertight connected body'
    report={
        'variant_count':1,'stl_watertight':bool(mesh.is_watertight),'stl_components':len(mesh.split()),
        'brep_valid':bool(s.isValid()),'brep_solids':len(s.Solids()),
        'printed_parts_per_complete_electrical_module':2,'routine_screws':0,
        'footprint_mm':[BASE_X,BASE_Y], 'printer_build_height_mm':MAX_BUILD_Z,
        'short_pitch_mm':PITCH_SHORT,'tall_pitch_mm':PITCH_TALL,
        'resistor_to_relay_nominal_clearance_mm':PITCH_SHORT-BOARD_T-PCB_LOWER_MAX_H,
        'relay_to_next_nominal_clearance_mm':PITCH_TALL-BOARD_T-PCB_RELAY_MAX_H,
        'mounting':'Four generic short-end clip mounts; no board mounting holes needed',
        'stacking':'Alternate 0/180 degree orientation; short/tall clip-in pitches, shared frame only',
        'physical_fit_qualified':False,
        'relay_PCB_envelope_qualified':False,
        'volume_mm3':round(s.Volume(),1)}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
