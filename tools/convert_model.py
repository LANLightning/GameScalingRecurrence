import os,sys,runpy
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'converter'))
root=Path(__file__).resolve().parents[1]
sys.argv=['tools.convert','--model',str(root/'models/GameScaling-0.8B-S3'),'--recipe',str(root/'tools/gamescaling_q8.py'),'--components','text,vision','--device','cpu','--rows-per-chunk','128','--name','gamescaling-0.8b-s3-q8','--out',str(root/'models/ninfer/gamescaling-0.8b-s3-q8.ninfer')]
import torch
torch.set_num_threads(8)
runpy.run_module('tools.convert',run_name='__main__')

