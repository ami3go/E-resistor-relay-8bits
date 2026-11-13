"""E-Resistor enclosure V3 — TWO stackable, screwless FDM-printable frame parts.

The resistor PCB geometry is from the repository's KiCad design.  The relay board
is a dimensional placeholder until the actual YHQ001 PCB is measured.  Four
integral split-snap docking pins on each frame mate with four keyed shoulder
sockets under the next frame (same interface for all frames).

Run: python create_v3.py  (cadquery + trimesh)
"""
from __future__ import annotations
import json, math
from pathlib import Path
import cadquery as cq

OUT = Path(__file__).resolve().parent
# Board dimensions (millimetres)
R_X, R_Y, R_HX, R_HY, PCB_T = 145.,55.,138.,48.,1.6  # KiCad verified
U_X, U_Y = 145.,56.  # UNVERIFIED upper relay PCB placeholder
# Common docking footprint
OUT_X, OUT_Y, P_X, P_Y = 174.,82.,81.,35.
FRAME_T, POST_OD = 5.,12.
LOWER_PITCH, UPPER_PITCH = 28.,43.
RES_SUPPORT_Z, RELAY_SUPPORT_Z = 8.,3.6
LOW_COMPONENT_H, RELAY_COMPONENT_H = 14.,27.  # assumed, NOT measured
# Releasable split-snap stack joint, printed upright
DOCK_SHAFT_D, DOCK_HEAD_D, DOCK_BORE_D, DOCK_RELIEF_D = 4.20,5.35,4.75,6.00
DOCK_HEAD_BASE_Z, DOCK_HEAD_H, DOCK_SLOT = 2.90,2.20,0.85
DOCK_COUNTERBORE_Z = 2.80
# Top male peg from local z=pitch..pitch+5.10. Socket relief from z=2.80 to 5.00.
# 0.1 mm tip protrusion is acceptable in an open corner; exact interference tested.

def cyl(x,y,z,d,h): return cq.Solid.makeCylinder(d/2,h,cq.Vector(x,y,z))
def box(x,y,z,w,d,h): return cq.Workplane('XY').box(w,d,h,centered=(True,True,False)).val().translate((x,y,z))
def ring():
    outer = cq.Workplane('XY').rect(OUT_X,OUT_Y).extrude(FRAME_T).edges('|Z').fillet(4).val()
    inner = cq.Workplane('XY').rect(OUT_X-12.8,OUT_Y-12.8).extrude(FRAME_T+2).val().translate((0,0,-1))
    return outer.cut(inner)
def brace(x1,y1,x2,y2,z,height,width):
    length=math.hypot(x2-x1,y2-y1)
    angle=math.degrees(math.atan2(y2-y1,x2-x1))
    mid=box(0,0,z,length,width,height).rotate((0,0,0),(0,0,1),angle).translate(((x1+x2)/2,(y1+y2)/2,0))
    return mid.fuse(cyl(x1,y1,z,width,height)).fuse(cyl(x2,y2,z,width,height)).clean()
def split_snap_peg(px,py,pitch):
    """Male bay: shaft + shoulder + tapered tip. Slotted ~7mm into post for flex."""
    shaft=cyl(px,py,pitch,DOCK_SHAFT_D,DOCK_HEAD_BASE_Z)
    head=cq.Solid.makeCone(DOCK_HEAD_D/2,1.8,DOCK_HEAD_H,cq.Vector(px,py,pitch+DOCK_HEAD_BASE_Z))
    # Slot cuts head and reaches down into tower, separating the tip into flex fingers.
    male=shaft.fuse(head).cut(box(px,py,pitch-1.75,DOCK_SLOT,6.0,DOCK_HEAD_BASE_Z+DOCK_HEAD_H+1.80)).clean()
    return male
def pcb_lock_pin(x,y):
    """Split push pin through verified 3.2mm PCB hole: no machine screws."""
    shaft=cyl(x,y,RES_SUPPORT_Z,2.55,2.05)
    lip=cyl(x,y,RES_SUPPORT_Z+2.05,3.47,.45)
    top=cq.Solid.makeCone(1.735,1.0,1.55,cq.Vector(x,y,RES_SUPPORT_Z+2.50))
    return shaft.fuse(lip).fuse(top).cut(box(x,y,RES_SUPPORT_Z+.65,.80,3.6,3.50)).clean()
def relay_edge_clip(sx,sy):
    """Flexible edge retainer at each relay-board end; dimensions provisional."""
    x=sx*(U_X/2+1.65); y=sy*(U_Y/2-8.0)
    stem=box(x,y,1.0,1.65,6.0,7.65)
    lip=box(x-sx*1.50,y,RELAY_SUPPORT_Z+PCB_T+.18,1.45,6.0,.72)
    taper=(cq.Workplane('XY',origin=(0,0,RELAY_SUPPORT_Z+PCB_T+.90))
         .center(x-sx*1.30,y).rect(1.5,6)
         .workplane(offset=1.15).center(sx*.55,0).rect(.65,6)
         .loft(combine=True).val())
    return stem.fuse(lip).fuse(taper).clean()

def make_frame(kind: str):
    assert kind in ('resistor','relay')
    pitch=LOWER_PITCH if kind=='resistor' else UPPER_PITCH
    s=ring()
    for sx in (-1,1):
        for sy in (-1,1):
            x,y=sx*P_X,sy*P_Y
            s=s.fuse(cyl(x,y,0,POST_OD,pitch))
            # Short gussets: every additive feature starts at the build plate,
            # avoiding horizontal 30–50mm spanning beams needing supports.
            hx,hy=sx*R_HX/2,sy*R_HY/2
            if kind=='resistor':
                s=s.fuse(brace(x,y,hx,hy,0,FRAME_T,9.5))
                s=s.fuse(cyl(hx,hy,FRAME_T,8.7,RES_SUPPORT_Z-FRAME_T))
                s=s.fuse(pcb_lock_pin(hx,hy))
            else:
                # Four isolated seating ledges, with small vertical edge clips.
                ux,uy=sx*(U_X/2-4.5),sy*(U_Y/2-4.5)
                s=s.fuse(brace(x,y,ux,uy,0,RELAY_SUPPORT_Z,7.5))
                s=s.fuse(cyl(ux,uy,0,8.2,RELAY_SUPPORT_Z))
                # The spring-clip stem is tied to the frame by a local short bridge.
                cx,cy=sx*(U_X/2+1.65),sy*(U_Y/2-8.0)
                s=s.fuse(brace(x,y,cx,cy,0,3.1,5.5))
                s=s.fuse(relay_edge_clip(sx,sy))
            s=s.fuse(split_snap_peg(x,y,pitch))
    # Female socket in all four posts: Ø4.75 entry with enlarged Ø6 shoulder
    # on upper side of base ring. Snap shoulder seats at z=2.9 (>2.8 ledge).
    for sx in (-1,1):
        for sy in (-1,1):
            x,y=sx*P_X,sy*P_Y
            s=s.cut(cyl(x,y,-.1,DOCK_BORE_D,FRAME_T+.2))
            s=s.cut(cyl(x,y,DOCK_COUNTERBORE_Z,DOCK_RELIEF_D,FRAME_T-DOCK_COUNTERBORE_Z+.2))
            # Opposing Ø2.4mm horizontal service ports let a narrow tweezer/tool
            # compress the two snap fingers for disassembly. Printability: short
            # (<12mm) Ø2.4 holes, no unsupported flat ceilings.
            s=s.cut(cq.Solid.makeCylinder(1.20,13.0,cq.Vector(x-6.5,y,3.92),cq.Vector(1,0,0)))
    # Anti-splay side tie slots, available without extra printed parts.
    for x in (-42.,42.):
        for y in (-37.8,37.8): s=s.cut(box(x,y,-.1,12.0,2.6,FRAME_T+.2))
    return s.clean()

def pcb(x,y,z,hx=None,hy=None):
    s=box(0,0,z,x,y,PCB_T)
    if hx is not None:
        for sx in (-1,1):
            for sy in (-1,1): s=s.cut(cyl(sx*hx/2,sy*hy/2,z-.1,3.2,PCB_T+.2))
    return s.clean()

def assembly(low,up,n=1,exploded=False):
    a=cq.Assembly(name=f'V3_{n}module_'+('exploded' if exploded else 'stack'))
    for i in range(n):
        z=i*(LOWER_PITCH+UPPER_PITCH)
        off=i*85 if exploded else 0
        a.add(low, name=f'resistor_frame_{i+1}',loc=cq.Location(cq.Vector(0,0,z+off)),color=cq.Color(.22,.27,.33))
        a.add(pcb(R_X,R_Y,0,R_HX,R_HY),name=f'resistor_PCB_{i+1}',loc=cq.Location(cq.Vector(0,0,z+off+RES_SUPPORT_Z+(16 if exploded else 0))),color=cq.Color(.12,.47,.25))
        a.add(up,name=f'relay_frame_{i+1}',loc=cq.Location(cq.Vector(0,0,z+off+LOWER_PITCH+(27 if exploded else 0))),color=cq.Color(.36,.42,.50))
        a.add(pcb(U_X,U_Y,0),name=f'RELAY_PROXY_UNVERIFIED_{i+1}',loc=cq.Location(cq.Vector(0,0,z+off+LOWER_PITCH+RELAY_SUPPORT_Z+(49 if exploded else 0))),color=cq.Color(.04,.42,.37))
    return a

def main():
    assert abs(LOWER_PITCH+RELAY_SUPPORT_Z-(RES_SUPPORT_Z+PCB_T+LOW_COMPONENT_H)-8.0)<.001
    assert UPPER_PITCH>RELAY_SUPPORT_Z+PCB_T+RELAY_COMPONENT_H+5
    low=make_frame('resistor');up=make_frame('relay')
    for name,s in [('resistor_frame',low),('relay_frame',up)]:
        assert s.isValid(),f'{name}: BRep invalid'
        assert len(s.Solids())==1,f'{name}: not single solid'
        cq.exporters.export(s,str(OUT/(name+'.step')))
        cq.exporters.export(s,str(OUT/(name+'.stl')),tolerance=.08,angularTolerance=.14)
    assembly(low,up).save(str(OUT/'module_assembly.step'),cq.exporters.ExportTypes.STEP)
    assembly(low,up,2).save(str(OUT/'two_modules.step'),cq.exporters.ExportTypes.STEP)
    assembly(low,up,1,True).save(str(OUT/'exploded_assembly.step'),cq.exporters.ExportTypes.STEP)
    import trimesh
    info={}
    for name,s in [('resistor_frame',low),('relay_frame',up)]:
        m=trimesh.load(OUT/(name+'.stl'),force='mesh')
        assert m.is_watertight,f'{name}: mesh not watertight'
        assert len(m.split())==1,f'{name}: mesh not connected'
        info[name]={'solid_valid':s.isValid(),'solids':len(s.Solids()),'watertight':bool(m.is_watertight),'meshes':len(m.split()),'volume_mm3':round(s.Volume(),2),'max_height_mm':(LOWER_PITCH if name=='resistor_frame' else UPPER_PITCH)+DOCK_HEAD_BASE_Z+DOCK_HEAD_H}
    info.update({'printed_parts_per_module':2,'required_screws_per_module':0,'footprint_mm':[OUT_X,OUT_Y],'frame_pitch_mm':{'resistor':LOWER_PITCH,'relay':UPPER_PITCH},'complete_module_pitch_mm':LOWER_PITCH+UPPER_PITCH,'nominal_resistor_to_relay_gap_mm':LOWER_PITCH+RELAY_SUPPORT_Z-(RES_SUPPORT_Z+PCB_T+LOW_COMPONENT_H),'nominal_headroom_to_next_module_mm':UPPER_PITCH-(RELAY_SUPPORT_Z+PCB_T+RELAY_COMPONENT_H),'upper_PCB_dimensions_unverified':True,'stack_joint':'four integrated split snap pegs to four shoulder sockets; nominal geometry only','needs_physical_test':True})
    (OUT/'verification.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info,indent=2))

if __name__=='__main__':main()
