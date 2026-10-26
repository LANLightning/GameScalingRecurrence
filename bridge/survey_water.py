import gzip,json,math,struct,zlib,time
from pathlib import Path
from nbt_reader import NBT
import argparse
p=argparse.ArgumentParser();p.add_argument('--world',required=True);p.add_argument('--origin',default=str(Path(__file__).resolve().parent/'runtime/origin.json'));args=p.parse_args()
base=Path(__file__).resolve().parent
origin=json.loads(Path(args.origin).read_text(encoding='utf8'));world=Path(args.world);ox,oy,oz=origin.get('position',origin.get('position_xyz'));radius=96
assert (world/'level.dat').exists(), 'World folder must contain level.dat'
columns=[];missing=[];files=set();chunks=0
for cz in range(math.floor((oz-radius)/16),math.floor((oz+radius)/16)+1):
 for cx in range(math.floor((ox-radius)/16),math.floor((ox+radius)/16)+1):
  reg=world/'region'/f'r.{cx//32}.{cz//32}.mca'
  if not reg.exists():missing.append([cx,cz]);continue
  with reg.open('rb') as f:
   f.seek(4*((cx%32)+(cz%32)*32));loc=int.from_bytes(f.read(4),'big');offset=loc>>8
   if offset==0:missing.append([cx,cz]);continue
   f.seek(offset*4096);size=int.from_bytes(f.read(4),'big');typ=f.read(1)[0];payload=f.read(size-1)
  if typ not in (1,2,3):raise RuntimeError(f'Unsupported chunk compression {typ}')
  obj=NBT(gzip.decompress(payload) if typ==1 else zlib.decompress(payload) if typ==2 else payload).root();chunks+=1;files.add(str(reg))
  remaining=set(range(256))
  for sec in sorted(obj.get('sections',[]),key=lambda x:x['Y'],reverse=True):
   block=sec.get('block_states',{});palette=block.get('palette',[])
   if not palette:continue
   if all(p['Name'] in ('minecraft:air','minecraft:cave_air','minecraft:void_air') for p in palette):continue
   bits=max(4,(len(palette)-1).bit_length());per=64//bits;mask=(1<<bits)-1;raw=block.get('data',[])
   for xz in tuple(remaining):
    x=xz%16;z=xz//16
    for y in range(15,-1,-1):
     idx=y*256+z*16+x;pal=0 if len(palette)==1 else (raw[idx//per]>>((idx%per)*bits))&mask;p=palette[pal]
     if p['Name'] in ('minecraft:air','minecraft:cave_air','minecraft:void_air'):continue
     gx=cx*16+x;gz=cz*16+z;gy=int(sec['Y'])*16+y
     if abs(gx-ox)<=radius and abs(gz-oz)<=radius:columns.append({'x':gx,'y':gy,'z':gz,'name':p['Name'],'properties':p.get('Properties',{})})
     remaining.remove(xz);break
   if not remaining:break
waters=[c for c in columns if c['name']=='minecraft:water' and c['properties'].get('level','0')=='0']
def dist(c):
 x=max(c['x'],min(c['x']+1,ox));z=max(c['z'],min(c['z']+1,oz));return math.sqrt((x-ox)**2+(c['y']+1-oy)**2+(z-oz)**2)
waters.sort(key=dist)
result={'kind':'saved_world_surface_survey','origin':[ox,oy,oz],'scope_horizontal_chebyshev_radius':radius,'chunks_read':chunks,'missing_chunks':missing,'source_files':sorted(files),'source_water_columns':len(waters),'definition':'Nearest by 3D distance from initial feet position to the surface of an exposed source-water block among saved topmost non-air columns in the surveyed square. Not nearest walking path, not live-verified. Trees/overhangs hide water from this definition.','nearest_candidates':[{**c,'distance_to_surface':dist(c)} for c in waters[:12]]}
(base/'water-survey.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
(base/'surface-columns.json').write_text(json.dumps(columns),encoding='utf8')
print(json.dumps(result,ensure_ascii=False)[:3800])
