"""CAD-mesh-based renders for universal single-part V3 stacked PCB frames."""
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from create_v3 import PCB_SUPPORT_Z, PITCH_SHORT, PITCH_TALL, BOARD_T
OUT=Path(__file__).resolve().parent
BASE=trimesh.load(OUT/'universal_frame.stl',force='mesh')
W,H=1720,1120
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
if not Path(FONT).exists():
    FONT='/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'
    BOLD='/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'
FRAME_COL=np.array([56,68,85]); FRAME_2=np.array([98,112,131]); PCB_LOW=np.array([21,122,75]); PCB_UP=np.array([15,94,87]); RELAY_BLUE=np.array([35,92,191]); CLAMP_GREEN=np.array([51,155,82]); METAL=np.array([151,168,180]); CHIP=np.array([48,54,58]);

def placed_mesh(mesh,z,angle=0):
    m=mesh.copy()
    if angle:m.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(angle),[0,0,1]))
    m.apply_translation((0,0,z))
    return m

def brick(center,size):
    m=trimesh.creation.box(extents=size);m.apply_translation(center);return m

def pcbs(z,upper=False):
    o=[]
    if upper:
        o.append((brick((0,0,z+BOARD_T/2),(145,56,BOARD_T)),PCB_UP))
        # Relay components purely illustrative; no measured production STEP model available.
        for i in range(8):
            x=-58.0+i*16.55
            o.append((brick((x,-8,z+BOARD_T+9.1),(14.2,18.3,18.2)),RELAY_BLUE))
            o.append((brick((x,16.8,z+BOARD_T+5.2),(13.8,8.5,10.4)),CLAMP_GREEN))
        o.append((brick((-65,-6,z+BOARD_T+12.5),(15,16,25)),METAL))
    else:
        o.append((brick((0,0,z+BOARD_T/2),(145,55,BOARD_T)),PCB_LOW))
        for i in range(8):
            x=-57+i*16.3
            o.append((brick((x,-6,z+BOARD_T+.75),(11.5,3,1.5)),CHIP))
        for i in range(5):
            x=-55+i*26
            o.append((brick((x,20,z+BOARD_T+5.5),(15,9.5,11)),CLAMP_GREEN))
    return o

def objects(mode):
    o=[]
    base=PITCH_SHORT+PITCH_TALL
    positions=[0,PITCH_SHORT,base,base+PITCH_SHORT]
    if mode=='assembled':
        ids=[0,1];delta=[0,0];focus=36;scale=4.1
    elif mode=='stacked':
        ids=[0,1,2,3];delta=[0]*4;focus=68;scale=3.30
    elif mode=='exploded':
        ids=[0,1];delta=[0,74];focus=84;scale=3.65
    else:raise ValueError(mode)
    for i in ids:
        z=positions[i]+delta[i]
        angle=180 if i%2 else 0
        o.append((placed_mesh(BASE,z,angle),FRAME_COL if i%2==0 else FRAME_2))
        pcb_z=z+PCB_SUPPORT_Z+(32 if mode=='exploded' else 0)
        for m,col in pcbs(pcb_z,i%2==1):
            if angle:m.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(angle),[0,0,1]))
            o.append((m,col))
    return o,focus,scale

def render(mode):
    objs,focus,scale=objects(mode)
    eye=np.array([1.37,-1.61,1.28]);eye=eye/np.linalg.norm(eye)
    right=np.cross([0,0,1.],eye);right/=np.linalg.norm(right)
    up=np.cross(eye,right);up/=np.linalg.norm(up)
    B=np.stack([right,-up,eye]);center=np.array([0,0,focus]);target=np.array([785,615]);
    im=Image.new('RGB',(W,H),'#f7f9fc');d=ImageDraw.Draw(im)
    light=np.array([.5,-.6,1.]);light/=np.linalg.norm(light)
    all_faces=[]
    for mesh,col in objs:
        V,F,N=mesh.vertices,mesh.faces,mesh.face_normals
        visible=N@B[2];ids=np.where(visible>.02)[0]
        faces=V[F[ids]]
        uv=(faces-center)@B.T
        points=uv[:,:,:2]*scale+target
        depth=uv[:,:,2].mean(axis=1)
        illumination=(.47+.43*np.maximum(0,N[ids]@light)+.10*np.maximum(0,visible[ids])).clip(.35,1.04)
        for xyz,dep,lum in zip(points,depth,illumination):
            polygon=[(int(x),int(y)) for x,y in xyz]
            color=tuple(int(min(255,z*lum)) for z in col)
            all_faces.append((dep,polygon,color))
    all_faces.sort(key=lambda x:x[0]);
    for _,pts,clr in all_faces:d.polygon(pts,fill=clr)
    H1=ImageFont.truetype(BOLD,39);H2=ImageFont.truetype(BOLD,23)
    TXT=ImageFont.truetype(FONT,20);SM=ImageFont.truetype(FONT,17)
    name={'exploded':'Exploded assembly','assembled':'One electrical module','stacked':'Two modules stacked'}[mode]
    d.text((58,42),'V3 UNIVERSAL — '+name,font=H1,fill='#1b314e')
    d.text((58,101),'ONE printed frame variant  |  Two identical copies per electrical module',font=TXT,fill='#596d82')
    d.text((60,1054),'Reference relay PCB geometry and populated component models are illustrative, not measured.',font=SM,fill='#98734e')
    if mode=='exploded':
        labels=[('04','Relay PCB (proxy)','Edge-clipped; size not verified'),('03','UNIVERSAL FRAME #2','Same STL, rotated 180 degrees'),('02','Resistor PCB','145 x 55 mm; KiCad verified'),('01','UNIVERSAL FRAME #1','Same STL; PCB edge clips')]
        ys=[235,430,624,825]
    elif mode=='assembled':
        labels=[('A','Short latch position','23.6 mm between carriers'),('B','Nominal component gap','8.0 mm (assuming 14 mm parts)'),('C','PCB mounting','Universal edge clips; no M3 screws')]
        ys=[490,630,770]
    else:
        labels=[('A','Short (lower to upper)','23.6 mm pitch'),('B','Tall (module to module)','40.0 mm pitch'),('C','Total module pitch','63.6 mm'),('D','Same printed component','Four identical frames shown')]
        ys=[470,590,710,830]
    for (num,h,sub),y in zip(labels,ys):
        d.rounded_rectangle((1085,y,1675,y+104),radius=14,fill='#ffffff',outline='#c5d0de',width=2)
        d.ellipse((1102,y+22,1148,y+68),fill='#334e6e')
        d.text((1114,y+32),num,font=SM,fill='white')
        d.text((1164,y+14),h,font=H2,fill='#203b54')
        d.text((1164,y+57),sub,font=SM,fill='#637993')
    out=OUT/(mode+'_v3.png');im.save(out,optimize=True)
    print(mode,'faces',len(all_faces),'size',out.stat().st_size)
if __name__=='__main__':
    for mode in ('assembled','exploded','stacked'):render(mode)
