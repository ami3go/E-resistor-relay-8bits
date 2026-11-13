"""CPU-only isometric CAD visualization for V2; no GPU required."""
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image,ImageDraw,ImageFont
OUT=Path(__file__).resolve().parent
SZ=(1800,1200)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
CH=trimesh.load(OUT/'chassis_v2.stl',force='mesh')
DARK=np.array([58,72,89]);GREEN=np.array([23,125,76]);PCB=np.array([15,103,88]);BLUE=np.array([45,107,207]);TERMINALS=np.array([49,154,91]);SILVER=np.array([163,174,187]);BLACK=np.array([53,59,65]);

def box_at(center,dim):
    m=trimesh.creation.box(extents=dim);m.apply_translation(center);return m

def board(z,relay=False):
    objs=[]
    if relay:
        objs.append((box_at((0,0,z+.8),(145,56,1.6)),PCB))
        for i in range(8):
            x=-58+i*16.6
            objs.append((box_at((x,-6,z+1.6+18.2/2),(14.8,20,18.2)),BLUE))
            objs.append((box_at((x,17.5,z+1.6+12.5/2),(14.8,10,12.5)),TERMINALS))
        objs.append((box_at((-65,-3,z+1.6+27/2),(15.5,18,27)),SILVER))
    else:
        objs.append((box_at((0,0,z+.8),(145,55,1.6)),GREEN))
        for i in range(8):
            objs.append((box_at((-57+i*16.2,-8,z+1.6+.5),(11.4,3.5,1.)),BLACK))
        for i in range(6):
            objs.append((box_at((-58+i*23,22,z+1.6+5.5),(15,9,11)),TERMINALS))
    return objs

def shapes(mode):
    obj=[]
    if mode=='assembled':
        obj.extend([(CH,DARK),*board(8),*board(32,True)]);focus=42;scale=4.25
    elif mode=='stacked':
        for i in range(2):
            dz=i*74
            c=CH.copy();c.apply_translation((0,0,dz))
            obj.extend([(c,DARK),*board(8+dz),*board(32+dz,True)])
        focus=80;scale=3.5
    else:
        obj.extend([(CH,DARK),*board(106),*board(158,True)]);focus=85;scale=3.55
    return obj,focus,scale

def project_matrix(focus,scale):
    eye=np.array([1.4,-1.65,1.35]);eye=eye/np.linalg.norm(eye)
    right=np.cross([0,0,1],eye);right/=np.linalg.norm(right)
    up=np.cross(eye,right);up/=np.linalg.norm(up)
    return np.stack([right,-up,eye]),np.array([0,0,focus]),scale

def render(mode):
    objs,focus,scale=shapes(mode)
    B,target,sc=project_matrix(focus,scale)
    width,height=SZ;cx=840;cy=625
    image=Image.new('RGB',SZ,'#f7f9fc');draw=ImageDraw.Draw(image)
    light=np.array([.6,-.7,1.]);light/=np.linalg.norm(light)
    tris=[]
    for m,col in objs:
        F=m.faces;V=m.vertices;N=m.face_normals
        to_eyes=N@B[2]
        ids=np.where(to_eyes>0.02)[0]
        loc=V[F[ids]]
        flat=(loc-target)@B.T
        proj=flat[:,:,:2]*sc+np.array([cx,cy])
        depths=flat[:,:,2].mean(axis=1)
        illum=(.49+.43*np.maximum(0,N[ids]@light)+.10*np.maximum(0,to_eyes[ids])).clip(.42,1.02)
        for idx,points,dep,s in zip(ids,proj,depths,illum):
            clr=tuple(int(min(255,v*s)) for v in col)
            tris.append((dep,[(int(x),int(y)) for x,y in points],clr))
    tris.sort(key=lambda t:t[0])
    for _,p,col in tris:draw.polygon(p,fill=col)
    F=ImageFont.truetype(bold,40);M=ImageFont.truetype(font,25);S=ImageFont.truetype(font,21)
    title={'assembled':'V2 | Integrated frame','stacked':'V2 | Two complete modules','exploded':'V2 | Exploded assembly'}[mode]
    draw.text((66,56),title,font=F,fill='#21344d')
    draw.text((66,111),'One printed chassis per module · no routine screws',font=M,fill='#51657d')
    if mode=='exploded':
        for y,t,sub in [(265,'3 · Ethernet 8-relay PCB','unverified mechanical envelope'),(475,'2 · Resistor PCB','145 x 55 mm verified KiCad outline'),(800,'1 · Integrated chassis','snap pins + relay edge clips + stack posts')]:
            draw.rounded_rectangle((1100,y,1720,y+100),radius=18,fill='#ffffff',outline='#bdcad8',width=2)
            draw.text((1128,y+12),t,font=M,fill='#263950')
            draw.text((1128,y+51),sub,font=S,fill='#62748a')
    else:
        draw.rounded_rectangle((1100,875,1715,1084),radius=16,fill='#ffffff',outline='#c2ccd9',width=2)
        for i,t in enumerate(('1 printable part / module','0 required M3 fasteners','4 integrated tower supports','Stack locking: friction-fit + optional ties')):
            draw.text((1130,897+42*i),t,font=S,fill='#354c62')
    draw.text((65,1131),'PCB component models are illustrative only. Confirm relay PCB size and clearance before printing.',font=S,fill='#9b6848')
    image.save(OUT/f'{mode}_v2.png',optimize=True)
    print(mode,len(tris),(OUT/f'{mode}_v2.png').stat().st_size)

if __name__=='__main__':
    for mode in ('assembled','exploded','stacked'): render(mode)
