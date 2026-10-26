from pathlib import Path
import json, os, subprocess, re, sys
BASE=Path(os.environ['NINFER_BASE_SOURCE']).resolve()
BUILD=Path(os.environ['NINFER_BASE_BUILD']).resolve()
ROOT=Path(__file__).resolve().parent
MODE = sys.argv[1] if len(sys.argv)>1 else 'serve'
commands=json.loads((BUILD/'compile_commands.json').read_text(encoding='utf8'))
byrel={Path(x['file']).relative_to(BASE).as_posix():x for x in commands if Path(x['file']).is_relative_to(BASE)}
# Read MSVC environment; the original build/source are never mutated.
res=subprocess.check_output(['cmd.exe','/d','/c','"'+os.environ['MSVC_ENV_BAT']+'" -vcvars_ver=14.44 >nul && set'],text=True,errors='replace')
for line in res.splitlines():
 if '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
(ROOT/'obj').mkdir(exist_ok=True)
objects=[]
test_files={'qualify':'qualify_small_ops.cu','causal':'qualify_causal_decode.cu','template':'qualify_template.cpp','extra':'qualify_extra.cu'}
for file in sorted(list((ROOT/'src').rglob('*')) + ([ROOT/'tests'/test_files[MODE]] if MODE in test_files else [])):
 if file.suffix not in ['.cpp','.cu']:continue
 rel=file.relative_to(ROOT).as_posix()
 entry=byrel.get(rel) or byrel['src/ops/gdn_gating_proj/bf16/bf16_gdn_gating_proj_kernels.cu' if file.suffix=='.cu' else 'src/models/qwen3_5/frontend/chat_template.cpp']
 target=ROOT/'obj'/ (rel.replace('/','_')+'.obj')
 objects.append(target)
 if target.exists() and target.stat().st_mtime>file.stat().st_mtime:continue
 cmd=entry['command'].replace('\\\\','\\').replace('--split-compile=2','--split-compile=1')
 original=str(Path(entry['file']))
 cmd=cmd.replace(original,str(file))
 cmd=re.sub(r'@\S+\.modmap','',cmd)
 cmd=re.sub(r'/Fo\S+', '/Fo'+str(target).replace('\\','/'),cmd)
 cmd=re.sub(r'/Fd[^\s,]+','/Fd'+str(ROOT/'obj'/'build.pdb').replace('\\','/'),cmd)
 if file.suffix=='.cu':cmd=re.sub(r' -o \S+',' -o '+str(target).replace('\\','/'),cmd)
 cmd=cmd.replace(' -I',' -I',1)
 first=cmd.find(' -I')
 cmd=cmd[:first]+' -I'+str(ROOT/'src')+' '+cmd[first:]
 print('COMPILE',rel,flush=True)
 (ROOT/'last-command.txt').write_text(cmd,encoding='utf8')
 r=subprocess.run(cmd,cwd=ROOT)
 if r.returncode:raise SystemExit(r.returncode)
# Reuse unchanged objects from the exact local engine build. Explicit override
# objects resolve the changed translation units before archive member selection.
lines=(BUILD/'build.ninja').read_text(encoding='utf8').splitlines()
i=next(i for i,l in enumerate(lines) if l.startswith('build apps\\ninfer-serve.exe:'))
libs=next(l.split(' = ',1)[1] for l in lines[i+1:i+30] if l.startswith('  LINK_LIBRARIES ='))
args=['/nologo','/MACHINE:X64','/INCREMENTAL:NO','/SUBSYSTEM:CONSOLE','/NODEFAULTLIB:LIBCMT','/OUT:'+str(ROOT/('ninfer-serve-small.exe' if MODE=='serve' else 'qualify-'+MODE+'.exe'))]
args += [str(p) for p in objects]
if MODE=='serve': args += [str(BUILD/'apps/CMakeFiles/ninfer-serve.dir/serve/main.cpp.obj')]
for lib in libs.split():
 p=Path(lib)
 args.append(str(BUILD/p) if (BUILD/p).exists() else lib)
args+=['/LIBPATH:'+str(Path(os.environ['CUDA_LIB_DIR']))]
(ROOT/'link.rsp').write_text('\n'.join('"'+x+'"' for x in args),encoding='utf8')
print('LINK',flush=True)
r=subprocess.run([os.environ['MSVC_LINK'],'@'+str(ROOT/'link.rsp')],cwd=ROOT)
raise SystemExit(r.returncode)



