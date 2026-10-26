from pathlib import Path
import argparse,json,subprocess
p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--llama-video',required=True);p.add_argument('--output',required=True);p.add_argument('--ffmpeg',default=str(Path(__file__).resolve().parents[1]/'ffmpeg/ffmpeg.exe'));a=p.parse_args();d=Path(a.directory).resolve();f=Path(a.ffmpeg);probe=f.with_name('ffprobe.exe')
def duration(name):return float(json.loads(subprocess.check_output([str(probe),'-v','error','-show_entries','format=duration','-of','json',str(Path(a.llama_video) if name=='llama.mp4' else d/name)]))['format']['duration'])
times=[duration('ninfer.mp4'),duration('llama.mp4')];end=max(times);font="C\\:/Windows/Fonts/arial.ttf";chains=[]
for i,(label,t) in enumerate(zip(['NInfer BF16 - GameScaling','llama.cpp Q8 - GameScaling'],times)):
 pad=max(0,end-t)+.2
 chains.append(f"[{i}:v]fps=10,tpad=stop_mode=clone:stop_duration={pad},pad=iw:ih+32:0:32:black,drawtext=fontfile='{font}':text='{label}':fontcolor=white:fontsize=20:x=12:y=5,drawbox=x=0:y=32:w=iw:h=ih-32:color=black:t=fill:enable='gte(t,{t})',drawtext=fontfile='{font}':text='Recording ended - no further actions':fontcolor=white:fontsize=22:x=20:y=240:enable='gte(t,{t})'[v{i}]")
chains.append('[v0][v1]hstack=inputs=2:shortest=1[v]')
subprocess.run([str(f),'-hide_banner','-loglevel','warning','-i',str(d/'ninfer.mp4'),'-i',str(Path(a.llama_video)),'-filter_complex',';'.join(chains),'-map','[v]','-t',str(end),'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(Path(a.output))],check=True)
print('Full-duration comparison complete; shorter episode is visibly marked ended')
