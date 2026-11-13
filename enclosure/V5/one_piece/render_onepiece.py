"""Render CAD-derived images for one-piece V5 rack using rasterized mesh faces.
No relays or populated components modeled; PCB silhouettes are placeholders.
"""
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from create_onepiece import OUT,PCB_T,R_X,R_Y,L_X,L_Y,PAIR_PITCH,R0_Z,L0_Z,board_levels

BODY=trimesh.load(OUT/'onepiece_frame.stl',force='mesh')
RES=np.array([37,151,85]); REL=np.array([42,117,184]); FRAME=np.array([70,82,106])
BASE=(1780,1050)
FONT_PATH='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD_PATH='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def ff(pt,bold=False):return ImageFont.truetype(BOLD_PATH if bold else FONT_PATH,pt)
def bare_board(kind,z,shift_y=0):
    x,y=(R_X,R_Y) if kind=='resistor' else (L_X,L_Y)
    m=trimesh.creation.box(extents=(x,y,PCB_T))
    m.apply_translation((0,1.5+shift_y,z+PCB_T/2))
    return m

def surfaces(mode):
    if mode=='frame':return [(BODY,FRAME)]
    all_=[(BODY,FRAME)]
    for kind,i,z in board_levels():
        shift=-83 if mode=='exploded' else 0
        all_.append((bare_board(kind,z,shift),RES if kind=='resistor' else REL))
    return all_

def render(mode):
    W,H=BASE
    img=Image.new('RGB',BASE,'#f6f8fb');d=ImageDraw.Draw(img)
    objects=surfaces(mode)
    camera=np.array([1.18,-1.6,1.04]); camera/=np.linalg.norm(camera)
    right=np.cross(np.array([0,0,1]),camera); right/=np.linalg.norm(right)
    up=np.cross(camera,right);up/=np.linalg.norm(up)
    B=np.stack([right,-up,camera])
    allpts=np.concatenate([o[0].vertices for o in objects],axis=0)
    prj=allpts@B.T
    minx,maxx=float(prj[:,0].min()),float(prj[:,0].max())
    miny,maxy=float(prj[:,1].min()),float(prj[:,1].max())
    scale=min(1120/(maxx-minx),760/(maxy-miny))
    cx=675-scale*(minx+maxx)/2
    cy=566-scale*(miny+maxy)/2
    light=np.array([-.65,-.44,1]);light/=np.linalg.norm(light)
    tris=[]
    for mesh,col in objects:
        fac=mesh.faces;norm=mesh.face_normals;V=mesh.vertices
        front=norm@camera
        inds=np.where(front>0.015)[0]
        points=V[fac[inds]]
        proj=points@B.T
        screen=proj[:,:,:2]*scale+np.array([cx,cy])
        depths=proj[:,:,2].mean(axis=1)
        illum=(.56+.40*np.maximum(0,norm[inds]@light)+.05*np.maximum(front[inds],0)).clip(.45,1.05)
        for xyz,depth,fac_light in zip(screen,depths,illum):
            color=tuple(int(min(255,round(v*fac_light))) for v in col)
            tris.append((float(depth),[(int(x),int(y)) for x,y in xyz],color))
    tris.sort(key=lambda t:t[0])
    for depth,poly,color in tris:d.polygon(poly,fill=color)
    titles={'frame':'V5 — ONE-PIECE 10-SLOT RACK','assembled':'V5 — 10 BOARDS LOADED','exploded':'V5 — SLIDE-IN EXPLODED VIEW'}
    d.text((58,40),titles[mode],font=ff(38,True),fill='#263b54')
    d.text((60,99),'Five resistor + five relay PCBs in one printed open rack',font=ff(21),fill='#5b6d83')
    x0=1325
    d.rounded_rectangle((x0,164,1740,898),radius=22,fill='#ffffff',outline='#c6d1de',width=2)
    d.text((x0+24,196),'Mechanical specification',font=ff(26,True),fill='#273e58')
    rows=[
        ('FRAME','1 × single STL'),
        ('PRINT SIZE','174 × 84 × 138 mm'),
        ('BOARD SLOTS','10 (R/L alternating)'),
        ('PCB THICKNESS','1.6 mm'),
        ('R → RELAY','5 mm face clearance'),
        ('RELAY → R','20 mm face clearance'),
        ('PAIR PITCH','28.2 mm'),
        ('LOAD DIRECTION','Slide from front'),
    ]
    y=250
    for a,b in rows:
        d.text((x0+26,y),a,font=ff(16,True),fill='#627489')
        d.text((x0+26,y+24),b,font=ff(20),fill='#243a52')
        d.line((x0+26,y+58,x0+390,y+58),fill='#e4e9ef',width=1)
        y+=79
    if mode=='exploded':
        d.text((75,955),'PCB silhouettes are pulled forward to show the insertion direction',font=ff(21),fill='#365775')
    elif mode=='frame':
        d.text((75,955),'Four continuous guide spines with 10 paired slots; no modular stacking interfaces',font=ff(21),fill='#365775')
    else:
        d.text((75,955),'Illustrative unpopulated PCBs; electrical component envelopes NOT modeled',font=ff(21),fill='#365775')
    d.text((58,1010),'CAUTION: 5 / 20 mm bare-board gaps do not clear the previously assumed populated component heights.',font=ff(18,True),fill='#9b593c')
    path=OUT/f'{mode}.png'
    img.save(path,optimize=True)
    print(path.name,path.stat().st_size,len(tris),'faces')

if __name__=='__main__':
    for mode in ('frame','assembled','exploded'):render(mode)
