#!/usr/bin/env python3
from pathlib import Path
import uuid

ROWS = [
    ("B0", "953||2k74",   "2k74||2k74", "2k077"),
    ("B1", "2k74||8k25", "2k74||11k",   "4k251"),
    ("B2", "0R||DNP",     "11k||36k5",   "8k453"),
    ("B3", "11k||36k5",   "11k||36k5",   "16k905"),
    ("B4", "2k74||36k5",  "36k5||226k",  "33k973"),
    ("B5", "36k5||226k",  "36k5||DNP",   "67k925"),
    ("B6", "8k25||8k25",  "226k||316k",  "135k889"),
    ("B7", "2k74||226k",  "536k||536k",  "270k707"),
]
BASE_TEXT = "BASE: 698||698||2k74||11k = 301R10"
LAYER = "F.SilkS"

def U(): return str(uuid.uuid4())
def E(s): return s.replace('\\', '\\\\').replace('"', '\\"')

def txt(s,x,y,size=0.72,th=0.11,layer=LAYER):
    return f'''  (fp_text user "{E(s)}" (at {x:.3f} {y:.3f}) (layer "{layer}")\n    (effects (font (size {size:.3f} {size:.3f}) (thickness {th:.3f})))\n    (tstamp {U()})\n  )\n'''

def line(x1,y1,x2,y2,w=0.12,layer=LAYER):
    return f'''  (fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f})\n    (stroke (width {w:.3f}) (type solid)) (layer "{layer}")\n    (tstamp {U()})\n  )\n'''

def wrap(name, items):
    return f'''(footprint "{name}" (version 20240108) (generator "e_resistor_table_generator")\n  (layer "F.Cu")\n  (descr "Padless E-Resistor relay bit population legend")\n  (tags "E-Resistor legend table silkscreen")\n  (attr board_only exclude_from_pos_files exclude_from_bom)\n  (fp_text reference "REF**" (at 0 -5) (layer "F.SilkS") hide\n    (effects (font (size 1 1) (thickness 0.15)))\n    (tstamp {U()})\n  )\n  (fp_text value "{name}" (at 0 -6.5) (layer "F.Fab") hide\n    (effects (font (size 1 1) (thickness 0.15)))\n    (tstamp {U()})\n  )\n{''.join(items)})\n'''

def compact():
    name="E_Resistor_Bit_Table_Compact"
    cols=[0,6,19,33,44.5]; top=-1.25; rh=1.75; bottom=15.85
    xc=[(cols[i]+cols[i+1])/2 for i in range(4)]
    a=[txt("E-RESISTOR BIT TABLE",22.25,-2.6,0.78,0.13), txt(BASE_TEXT,22.25,17.4,0.65,0.11)]
    for h,x in zip(("BIT","R1||R2","R3||R4","REQ"),xc): a.append(txt(h,x,0))
    for i,row in enumerate(ROWS):
        y=(i+1)*rh
        for v,x in zip(row,xc): a.append(txt(v,x,y))
    for x in cols: a.append(line(x,top,x,bottom))
    for i in range(10):
        y=top+i*rh; a.append(line(cols[0],y,cols[-1],y))
    a.append(line(cols[0],bottom,cols[-1],bottom))
    return name,wrap(name,a)

def full():
    name="E_Resistor_Bit_Table_Full"
    cols=[0,6,17.5,29,40.5,52,63]; top=-1.4; rh=2.45; bottom=top+9*rh
    xc=[(cols[i]+cols[i+1])/2 for i in range(6)]
    a=[txt("E-RESISTOR 8-BIT CELL POPULATION",31.5,-3.0,1.0,0.15), txt(BASE_TEXT,31.5,bottom+1.65,0.78,0.12)]
    for h,x in zip(("BIT","R1","R2","R3","R4","REQ"),xc): a.append(txt(h,x,top+rh/2,0.82,0.12))
    for i,(bit,p1,p2,req) in enumerate(ROWS):
        r1,r2=p1.split("||"); r3,r4=p2.split("||")
        y=top+(i+1.5)*rh
        for v,x in zip((bit,r1,r2,r3,r4,req),xc): a.append(txt(v,x,y,0.82,0.12))
    for x in cols: a.append(line(x,top,x,bottom))
    for i in range(10): a.append(line(cols[0],top+i*rh,cols[-1],top+i*rh))
    return name,wrap(name,a)

if __name__ == "__main__":
    lib=Path(__file__).with_name("E_Resistor_Legends.pretty")
    lib.mkdir(exist_ok=True)
    for fn in (compact,full):
        name,data=fn(); (lib/f"{name}.kicad_mod").write_text(data,encoding="utf-8")
        print(lib/f"{name}.kicad_mod")
