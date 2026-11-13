"""CPU-only 3D renders of the exact V3 mesh plus PROXY PCBs."""
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image,ImageDraw,ImageFont
from create_v3 import LOWER_PITCH,UPPER_PITCH,RES_SUPPORT_Z,RELAY_SUPPORT_Z
OUT=Path(__file__).resolve().parent
SZ=(1800,1200)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
LOW=trimesh.load(OUT/'resistor_frame.stl',force='mesh')
UP=trimesh.load(OUT/'relay_frame.stl',force='mesh')
BLACK=np.array([52,63,79]);GRAY=np.array([96,107,124]);GREEN=np.array([23,126,72]);PCB=np.array([22,99,81]);BLUE=np.array([48,116,208]);TERMINALS=np.array([31,159,95]);METAL=np.array([171,183,193]);DARK=np.array([55,60,70]);BEIGE=np.array([178,175,160]);

def at(mesh,z):
    m=mesh.copy();m.apply_translation([0,0,z]);return m

def brick(center,size):
    m=trimesh.creation.box(extents=size);m.apply_translation(center);return m

def pcb_board(z,relay=False):
    a=[]
    if relay:
        a.append((brick((0,0,z+.8),(145,56,1.6)),PCB))
        for i in range(8):
            x=-58+i*16.4
            a.append((brick((x,-7,z+1.6+17.8/2),(14.5,19.4,17.8)),BLUE))
            a.append((brick((x,17.7,z+1.6+11/2),(14.1,10.5,11)),TERMINALS))
        a.append((brick((-65,-4,z+1.6+25/2),(16,18,25)),METAL))
    else:
        a.append((brick((0,0,z+.8),(145,55,1.6)),GREEN))
        for i in range(8):
            a.append((brick((-58+i*16.4,-7,z+1.6+.7),(12,3.5,1.4)),DARK))
        # Placeholder component envelopes; actual KiCad board has mixed terminals and SMD resistors.
        for i in range(6):
            a.append((brick((-57+i*22.5,20,z+1.6+5),(15,9,10)),TERMINALS))
    return a

def parts(mode):
    objs=[]
    if mode=='exploded':
        objs += [(LOW,BLACK)]
        objs += pcb_board(50)
        objs += [(at(UP,100),GRAY)]
        objs += pcb_board(195,True)
        return objs,105,3.25
    if mode=='assembled':
        objs += [(LOW,BLACK), (at(UP,LOWER_PITCH),GRAY)]
        objs += pcb_board(RES_SUPPORT_Z)
        objs += pcb_board(LOWER_PITCH+RELAY_SUPPORT_Z,True)
        return objs,35,4.2
    if mode=='stacked':
        for i in range(2):
            dz=i*(LOWER_PITCH+UPPER_PITCH)
            objs += [(at(LOW,dz),BLACK),(at(UP,dz+LOWER_PITCH),GRAY)]
            objs += pcb_board(dz+RES_SUPPORT_Z)
            objs += pcb_board(dz+LOWER_PITCH+RELAY_SUPPORT_Z,True)
        return objs,80,3.35
    raise ValueError(mode)

def render(mode):
    objects,focus,scale=parts(mode)
    eye=np.array([1.35,-1.65,1.24]);eye=eye/np.linalg.norm(eye)
    right=np.cross([0,0,1],eye);right/=np.linalg.norm(right)
    up=np.cross(eye,right);up/=np.linalg.norm(up)
    B=np.stack([right,-up,eye])
    aim=np.array([0,0,focus])
    cx,cy=865,650
    img=Image.new('RGB',SZ,'#f5f8fc');draw=ImageDraw.Draw(img)
    light=np.array([.6,-.7,1]);light/=np.linalg.norm(light)
    faces=[]
    for mesh,color in objects:
        F=mesh.faces;V=mesh.vertices;N=mesh.face_normals
        vis=N@B[2]
        ids=np.where(vis>0.02)[0]
        pos=V[F[ids]]
        uv=(pos-aim)@B.T
        uv=uv[:,:,:2]*scale+np.array([cx,cy]);depth=(pos-aim)@B[2]
        depths=depth.mean(axis=1)
        luma=(.49+.43*np.maximum(0,N[ids]@light)+.10*np.maximum(0,vis[ids])).clip(.35,1.05)
        for poly,dep,shade in zip(uv,depths,luma):
            col=tuple(int(min(255,v*shade)) for v in color)
            faces.append((dep,[(int(x),int(y)) for x,y in poly],col))
    faces.sort(key=lambda f:f[0]);
    for dep,p,col in faces:draw.polygon(p,fill=col)
    title={'assembled':'V3 — Two-piece module','exploded':'V3 — Exploded assembly','stacked':'V3 — Two modules locked together'}[mode]
    font=ImageFont.truetype(FONT,23);small=ImageFont.truetype(FONT,19)
    hdr=ImageFont.truetype(BOLD,42);med=ImageFont.truetype(BOLD,25)
    draw.text((54,46),title,font=hdr,fill='#223955')
    draw.text((56,106),'Stack-compatible printed resistor frame + relay frame',font=font,fill='#526a81')
    if mode=='exploded':
        info=[('4  Relay PCB','YHQ001 placeholder; dimensions not measured'),('3  Relay frame','43-mm pitch; snap posts and sockets'),('2  Resistor PCB','145×55 mm; 138×48 mm M3-hole spacing'),('1  Resistor frame','28-mm pitch; integral mounting pins')]
        for i,(title,desc) in enumerate(info):
            y=260+166*i
            draw.rounded_rectangle((1110,y,1745,y+118),radius=18,fill='#ffffff',outline='#cad3e1',width=2)
            draw.text((1134,y+14),title,font=med,fill='#273d57')
            draw.text((1134,y+56),desc,font=small,fill='#4d647d')
    else:
        draw.rounded_rectangle((1085,835,1743,1095),radius=18,fill='#ffffff',outline='#c5d1de',width=2)
        lines=['2 printed parts per module','4 positive snap joints per interface','0 routine screws; split tapered lock heads','71 mm pitch between complete modules','8 mm nominal clearance (14-mm lower components)']
        for i,t in enumerate(lines):draw.text((1112,858+42*i),t,font=font,fill='#304861')
    draw.text((54,1147),'Relays, RJ45 and resistors are illustrative proxies; physical PCB fit and snap durability remain unverified.',font=small,fill='#9b6348')
    path=OUT/(mode+'_v3.png');img.save(path,optimize=True)
    print(mode,path.stat().st_size,'triangles=',len(faces))
if __name__=='__main__':
    for mode in ('exploded','assembled','stacked'):render(mode)
