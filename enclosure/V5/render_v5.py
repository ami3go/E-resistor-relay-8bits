"""CPU software render: actual V5 frame STL, unpopulated 1.6-mm PCB proxies."""
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image,ImageDraw,ImageFont
from create_v5 import PITCH,R_Z,U_Z,PCB_T,R_X,R_Y,U_X,U_Y,GAP_R_TO_U,GAP_U_TO_NEXT_R
HERE=Path(__file__).resolve().parent
FRAME=trimesh.load(HERE/'shelf_unit.stl',force='mesh')
RES=np.array([35,144,83]);REL=np.array([24,116,157]);DARK=np.array([59,73,94])
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(n,b=False):return ImageFont.truetype(BOLD if b else FONT,n)
def board(x,y,z):
    m=trimesh.creation.box(extents=(x,y,PCB_T))
    m.apply_translation((0,1.5,z+PCB_T/2))
    return m
def elements(levels=5,exploded=False):
    out=[]
    for i in range(levels):
        z=i*PITCH+(i*21 if exploded else 0)
        f=FRAME.copy();f.apply_translation((0,0,z))
        out.append((f,DARK))
        out.append((board(R_X,R_Y,z+R_Z+(7 if exploded else 0)),RES))
        out.append((board(U_X,U_Y,z+U_Z+(17 if exploded else 0)),REL))
    return out
def draw_rack(mode='rack'):
    n={'rack':5,'pair':1,'exploded':3}[mode]
    W,H=1800,1140
    image=Image.new('RGB',(W,H),'#f4f7fb')
    d=ImageDraw.Draw(image)
    eye=np.array([1.38,-1.60,1.04]);eye/=np.linalg.norm(eye)
    right=np.cross([0,0,1],eye);right/=np.linalg.norm(right)
    up=np.cross(eye,right);up/=np.linalg.norm(up)
    B=np.stack((right,-up,eye))
    light=np.array([.65,-.50,.95]);light/=np.linalg.norm(light)
    aim=np.array([0.,0.,{'rack':70,'pair':16,'exploded':80}[mode]])
    scale={'rack':4.4,'pair':5.4,'exploded':3.95}[mode]
    cx={'rack':775,'pair':785,'exploded':790}[mode]
    triangles=[]
    for mesh,color in elements(n,mode=='exploded'):
        faces=mesh.faces;v=mesh.vertices;norm=mesh.face_normals
        inds=np.flatnonzero(norm@B[2]>0.012)
        xyz=v[faces[inds]];ref=(xyz-aim)@B.T
        coords=ref[:,:,:2]*scale+np.array([cx,640])
        depths=ref[:,:,2].mean(axis=1)
        lightness=(.54+.40*np.maximum(0,norm[inds]@light)+.055*np.maximum(0,norm[inds]@B[2])).clip(.38,1.08)
        for points,depth,shade in zip(coords,depths,lightness):
            triangles.append((float(depth),tuple((int(x),int(y)) for x,y in points),
                             tuple(int(min(255,c*shade)) for c in color)))
    triangles.sort(key=lambda t:t[0])
    for _,p,fill in triangles:d.polygon(p,fill=fill)
    title={'rack':'V5 | Five-pair compact PCB shelf rack','pair':'V5 | Single slide-in shelf section','exploded':'V5 | Exploded shelf assemblies'}[mode]
    d.text((70,44),title,font=font(38,True),fill='#22374f')
    d.text((70,101),'Ten PCB substrates, one universal shelf STL printed five times',font=font(22),fill='#52677c')
    px=1330
    d.rounded_rectangle((px,172,1762,985),radius=18,fill='white',outline='#c6d2df',width=2)
    d.text((px+22,195),'PCB face-to-face layout',font=font(24,True),fill='#263a53')
    top=285;side_scale=4.1 if mode!='pair' else 7.5
    for i in range(5 if mode!='pair' else 2):
        for label,z,color in [('R',R_Z+i*PITCH,(32,150,86)),('L',U_Z+i*PITCH,(33,129,175))]:
            y=top+z*side_scale
            d.rectangle((px+37,int(y),px+225,int(y+PCB_T*side_scale)),fill=color)
            d.text((px+238,int(y-2)),f'{label}{i+1}',font=font(16,True),fill='#3b4b5d')
    bottom=870 if mode!='pair' else 730
    d.line((px+27,bottom,px+404,bottom),fill='#cad5df',width=2)
    for idx,line in enumerate(('5.0 mm : R PCB top to relay bottom',
                               '20.0 mm : relay top to next R PCB',
                               'Pitch: 28.2 mm per pair',
                               'Each bare PCB is 1.6 mm thick')):
        d.text((px+37,bottom+17+38*idx),line,font=font(16,idx<2),fill='#354a62')
    d.text((68,1065),'WARNING — populated terminal blocks and relay components may collide at these gaps.',
           font=font(20,True),fill='#9c6246')
    image.save(HERE/f'{mode}_v5.png',optimize=True)
    print(f'{mode} render complete; {len(triangles)} faces')
if __name__=='__main__':
    for kind in ('rack','pair','exploded'):draw_rack(kind)
