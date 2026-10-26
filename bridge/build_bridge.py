"""Build the bridge with a local JDK 21 and ASM 9.8; no game archive is changed."""
import argparse,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--java-home',required=True);p.add_argument('--asm',required=True);p.add_argument('--output-dir');a=p.parse_args();base=Path(__file__).resolve().parent;out=Path(a.output_dir).resolve() if a.output_dir else base;out.mkdir(parents=True,exist_ok=True);jdk=Path(a.java_home)/'bin';asm=Path(a.asm).resolve()
classes=out/'classes';classes.mkdir(exist_ok=True);sources=sorted((base/'src').glob('*.java'))
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-cp',str(asm),'-d',str(classes),*[str(x) for x in sources]],check=True)
subprocess.run([str(jdk/'java.exe'),'-Xverify:all','-cp',str(classes)+';'+str(asm),'org.gamescaling.craftbridge.v5.VerifyRestoreTest'],check=True)
for name in ['craft-bridge-5min.jar']:
 with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED) as z:
  if name=='craft-bridge-5min.jar':z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\r\nAgent-Class: org.gamescaling.launcher.v6.CraftBootstrap\r\nCan-Redefine-Classes: false\r\nCan-Retransform-Classes: true\r\n\r\n')
  for f in classes.rglob('*.class'):z.write(f,f.relative_to(classes).as_posix())
  with zipfile.ZipFile(asm) as dep:
   for n in dep.namelist():
    if n.startswith('org/objectweb/asm/'):z.writestr(n,dep.read(n))
  z.write(base/'ASM-LICENSE.txt','META-INF/ASM-LICENSE.txt')
print('Built verified bootstrap and implementation into',out)

