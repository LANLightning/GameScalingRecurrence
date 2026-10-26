import struct
class NBT:
 def __init__(self,data):self.data=memoryview(data);self.i=0
 def read(self,n):
  result=self.data[self.i:self.i+n];self.i+=n
  if len(result)!=n:raise ValueError('Truncated NBT')
  return result
 def num(self,f):return struct.unpack('>'+f,self.read(struct.calcsize('>'+f)))[0]
 def string(self):return bytes(self.read(self.num('H'))).decode('utf8')
 def tag(self,t):
  if t in range(1,7):return self.num({1:'b',2:'h',3:'i',4:'q',5:'f',6:'d'}[t])
  if t==7:return bytes(self.read(self.num('i')))
  if t==8:return self.string()
  if t==9:
   typ=self.num('B');n=self.num('i');return [self.tag(typ) for _ in range(n)]
  if t==10:
   d={}
   while True:
    typ=self.num('B')
    if typ==0:return d
    name=self.string();d[name]=self.tag(typ)
  if t in (11,12):return [self.num('i' if t==11 else 'q') for _ in range(self.num('i'))]
  raise ValueError(t)
 def root(self):
  t=self.num('B');self.string();return self.tag(t)
