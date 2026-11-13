"""Editable CadQuery V1 geometry for E-Resistor open stacker.

Resistor PCB geometric constraints extracted from:
  https://github.com/ami3go/E-resistor-relay-8bits/blob/main/Resistors-board/Resistors-board.kicad_pcb
Relay PCB mechanical footprint NOT available; articulated adapters are adjustable.

Install: pip install cadquery
Run: python create_step.py
STEP and STL generated from the same OpenCascade B-Rep solids.
"""
import math
from pathlib import Path
import cadquery as cq

HERE=Path(__file__).resolve().parent
FRAME_X, FRAME_Y, RAIL, FRAME_T = 178,86,7.5,4.5
RES_X, RES_Y, RES_T=145,55,1.6
RES_HOLE_X,RES_HOLE_Y=138,48
RES_BOSS_H=6.4
LOWER_POST_H=21
TRAY_T=5.2
ARM_T=3.6
STACK_POST_H=45
CORNER_X,CORNER_Y=83,39
PIVOT_X,PIVOT_Y=74,38
Z_TRAY=FRAME_T+LOWER_POST_H
Z_TOP=Z_TRAY+TRAY_T
Z_RELAY=Z_TOP+ARM_T


def plate(x,y,t,r):
    return cq.Workplane('XY').rect(x,y).extrude(t).edges('|Z').fillet(r).val()


def tube_or_cylinder(x,y,d,t,z=0):
    return cq.Solid.makeCylinder(d/2,t,cq.Vector(x,y,z))


def capsule(x1,y1,x2,y2,width,height,z=0):
    a=math.atan2(y2-y1,x2-x1)
    length=math.hypot(x2-x1,y2-y1)
    mid=cq.Workplane('XY').rect(length,width).extrude(height).val().rotate((0,0,0),(0,0,1), math.degrees(a)).translate(((x1+x2)/2,(y1+y2)/2,z))
    return mid.fuse(tube_or_cylinder(x1,y1,width,height,z)).fuse(tube_or_cylinder(x2,y2,width,height,z)).clean()


def outer_ring(t):
    outer=plate(FRAME_X,FRAME_Y,t,5)
    inner=plate(FRAME_X-2*RAIL,FRAME_Y-2*RAIL,t+2,3).translate((0,0,-1))
    return outer.cut(inner)


def subtract_frame_features(w,t):
    for x in (-CORNER_X,CORNER_X):
        for y in (-CORNER_Y,CORNER_Y):
            w=w.cut(tube_or_cylinder(x,y,3.6,t+2,-1))
    for x in (-48,0,48):
        for y in (-39,39):
            w=w.cut(cq.Workplane('XY').rect(12,2.5).extrude(t+2).val().translate((x,y,-1)))
    return w.clean()


def base():
    w=outer_ring(FRAME_T)
    for sx in (-1,1):
        for sy in (-1,1):
            x,y=sx*RES_HOLE_X/2,sy*RES_HOLE_Y/2
            w=w.fuse(capsule(x,y,sx*CORNER_X,sy*CORNER_Y,10,FRAME_T))
            w=w.fuse(tube_or_cylinder(x,y,9.3,RES_BOSS_H,FRAME_T))
    w=subtract_frame_features(w,FRAME_T)
    for sx in (-1,1):
        for sy in (-1,1):
            x,y=sx*RES_HOLE_X/2,sy*RES_HOLE_Y/2
            # M3 insert installed from top. Small bore provides screw tip relief.
            w=w.cut(tube_or_cylinder(x,y,3.1,RES_BOSS_H+.1,FRAME_T))
            w=w.cut(tube_or_cylinder(x,y,4.2,5.5,FRAME_T+RES_BOSS_H-5.4))
    return w.clean()


def tray():
    w=outer_ring(TRAY_T)
    for sx in (-1,1):
        for sy in (-1,1):
            w=w.fuse(capsule(sx*CORNER_X,sy*CORNER_Y,sx*PIVOT_X,sy*PIVOT_Y,8.8,TRAY_T))
    w=subtract_frame_features(w,TRAY_T)
    for sx in (-1,1):
        for sy in (-1,1):
            # Pivot anchor M3 heatset from upper face, 0.8 mm bottom skin.
            w=w.cut(tube_or_cylinder(sx*PIVOT_X,sy*PIVOT_Y,4.2,4.6,TRAY_T-4.4))
    return w.clean()


def arm():
    w=capsule(0,0,30,0,9.2,ARM_T)
    w=w.cut(tube_or_cylinder(0,0,3.6,ARM_T+.2,-.1))
    w=w.cut(capsule(8,0,28,0,3.6,ARM_T+.2,-.1))
    # Flat-bottom relief permits a slim or countersunk M3 head under arm.
    w=w.cut(capsule(8,0,28,0,6.0,1.9,-.1))
    return w.clean()


def post(length):
    w=tube_or_cylinder(0,0,11.4,length)
    w=w.cut(tube_or_cylinder(0,0,3.0,length+.2,-.1))
    w=w.cut(tube_or_cylinder(0,0,4.2,5.7,-.1))
    w=w.cut(tube_or_cylinder(0,0,4.2,5.7,length-5.6))
    return w.clean()


def pcb_proxy(xsize,ysize,thick,holes_x,holes_y):
    w=cq.Workplane('XY').box(xsize,ysize,thick,centered=(True,True,False)).val()
    for x in (-holes_x/2,holes_x/2):
        for y in (-holes_y/2,holes_y/2):
            w=w.cut(tube_or_cylinder(x,y,3.2,thick+.2,-.1))
    return w.clean()


def save_parts(parts):
    for name,s in parts.items():
        assert s.isValid(), f'{name} invalid OpenCascade BRep'
        assert len(s.Solids()) == 1, f'{name} not one solid'
        cq.exporters.export(s,str(HERE/(name+'.step')))
        cq.exporters.export(s,str(HERE/(name+'.stl')),tolerance=.09,angularTolerance=.14)
        print(f'{name:>12s}: Volume={s.Volume():.2f} mm^3; valid={s.isValid()}')


def make_assy(parts,with_boards=False):
    a=cq.Assembly(name='E_Resistor_Stackable_V1')
    a.add(parts['base'],name='01_base',color=cq.Color(.23,.27,.31))
    a.add(parts['tray'],name='02_upper_tray',loc=cq.Location(cq.Vector(0,0,Z_TRAY)),color=cq.Color(.23,.27,.31))
    for sx in (-1,1):
        for sy in (-1,1):
            c=(sx*CORNER_X,sy*CORNER_Y)
            a.add(parts['lower_post'],name=f'lower_post_{sx}_{sy}',loc=cq.Location(cq.Vector(*c,FRAME_T)),color=cq.Color(.52,.53,.55))
            a.add(parts['stack_post'],name=f'stack_post_{sx}_{sy}',loc=cq.Location(cq.Vector(*c,Z_TOP)),color=cq.Color(.52,.53,.55))
            px,py=sx*PIVOT_X,sy*PIVOT_Y
            theta=math.degrees(math.atan2(sy*24-py,sx*69-px))
            location=cq.Location(cq.Vector(px,py,Z_TOP),cq.Vector(0,0,1),theta)
            a.add(parts['arm'],name=f'adapter_arm_{sx}_{sy}',loc=location,color=cq.Color(.89,.63,.19))
    if with_boards:
        a.add(pcb_proxy(RES_X,RES_Y,RES_T,RES_HOLE_X,RES_HOLE_Y),name='LOWER_VERIFIED_OUTLINE_PCB',loc=cq.Location(cq.Vector(0,0,FRAME_T+RES_BOSS_H)),color=cq.Color(.15,.46,.25))
        a.add(pcb_proxy(145,56,1.6,138,48),name='UPPER_UNVERIFIED_PLACEHOLDER_PCB',loc=cq.Location(cq.Vector(0,0,Z_RELAY)),color=cq.Color(.10,.30,.40))
    a.save(str(HERE/('frame_with_reference_pcbs.step' if with_boards else 'frame_assembly.step')),cq.exporters.ExportTypes.STEP)

if __name__=='__main__':
    parts={'base':base(),'tray':tray(),'arm':arm(),'lower_post':post(LOWER_POST_H),'stack_post':post(STACK_POST_H)}
    save_parts(parts)
    make_assy(parts)
    make_assy(parts,with_boards=True)
    print('nominal air clearance above 14 mm lower component:', round(Z_RELAY-(FRAME_T+RES_BOSS_H+RES_T+14),2),'mm')
    print('stack pitch:',round(Z_TOP+STACK_POST_H,2),'mm')
