package org.gamescaling.craftbridge.v5;
import java.io.*;
import java.lang.instrument.*;
import java.security.ProtectionDomain;
import org.objectweb.asm.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Minecraft 1.21.1 local, single-player-only observation/control bridge.
 * Temporarily transforms InputConstants for virtual modifiers; no native hooks or external connections.
 * Starts observation-only. Commands are local files in its explicit runtime directory.
 */
public final class WaterTaskBridge {
 static Instrumentation instrumentation;static Class<?> inputClass;static ClassFileTransformer inputTransformer;static volatile boolean virtualKeys=true;
 static Map<String,Integer> codes=new LinkedHashMap<>();static Object[] originCraft;static Object originCarried;static Object[] originItems;static int originSelected;static Object originMode;static long originDay;static boolean originFlying;
 static Object modelOwnedPause;
 static int scroll;static boolean scrollSent;static Object window,keyboard,mouse;static long windowId;
 static Path dir; static Object mc; static ClassLoader loader;
 static volatile boolean running=true; static AtomicBoolean pending=new AtomicBoolean();
 static Map<String,Object> keys=new LinkedHashMap<>(); static Set<String> held=new HashSet<>();
 static String lastCommand="", commandStatus="observation_only", episode="idle", lastError="";
 static long actionStart, actionEnd, lastSample, sequence; static String[] steps;
 static double dx,dy,appliedX,appliedY; static Object[] origin; static UUID playerId;
 static BufferedWriter trace; static final Map<String,Method> methods=new ConcurrentHashMap<>();
 static final Map<String,Field> fields=new ConcurrentHashMap<>();
 public static void agentmain(String args, Instrumentation inst) throws Exception {
  if(dir!=null)throw new IllegalStateException("Already attached");
  Path configPath=Path.of(args).toAbsolutePath();Properties cfg=new Properties();
  try(var r=Files.newBufferedReader(configPath,StandardCharsets.UTF_8)){cfg.load(r);}
  dir=Path.of(cfg.getProperty("runtime")).toAbsolutePath(); Files.createDirectories(dir);
  for(Class<?> c:inst.getAllLoadedClasses())if(c.getName().equals("fgo")||c.getName().equals("net.minecraft.client.Minecraft")){
   loader=c.getClassLoader();mc=callStatic(c,new String[]{"getInstance","Q"});break;
  }
  if(mc==null)throw new IllegalStateException("Minecraft class not loaded; no hooks installed");
  Path actual=((File)field(mc,"gameDirectory","p")).toPath().toRealPath();
  Path expected=Path.of(cfg.getProperty("gameDir")).toRealPath();
  if(!actual.equals(expected))throw new IllegalStateException("Wrong game directory; no controller started");
  if(call(mc,new String[]{"getSingleplayerServer","V"})==null)throw new IllegalStateException("Single-player world required");
  Object opts=field(mc,"options","m");
  String[][] names={{"W","keyUp","w"},{"S","keyDown","y"},{"A","keyLeft","x"},{"D","keyRight","z"},{"Space","keyJump","A"},{"Shift","keyShift","B"},{"Ctrl","keySprint","C"}};
  for(String[] n:names)keys.put(n[0],field(opts,n[1],n[2]));
  window=call(mc,new String[]{"getWindow","aM"});windowId=((Number)call(window,new String[]{"getWindow","j"})).longValue();keyboard=field(mc,"keyboardHandler","o");mouse=field(mc,"mouseHandler","n");
  // Retire older observation loops on the game thread before installing this version.
  CompletableFuture<Void> retired=new CompletableFuture<>();call(mc,new String[]{"execute"},new Class[]{Runnable.class},(Runnable)()->{try{
   for(Class<?> old:inst.getAllLoadedClasses())if(old!=WaterTaskBridge.class && old.getName().startsWith("org.gamescaling.") && old.getSimpleName().equals("WaterTaskBridge")){
    try{Field active=old.getDeclaredField("running");active.setAccessible(true);boolean wasActive=active.getBoolean(null);if(wasActive){Field oldOrigin=old.getDeclaredField("origin");oldOrigin.setAccessible(true);if(oldOrigin.get(null)!=null)for(String name:new String[]{"origin","originItems","originCraft","originCarried","originSelected","originMode","originDay","playerId"}){Field from=old.getDeclaredField(name),to=WaterTaskBridge.class.getDeclaredField(name);from.setAccessible(true);to.setAccessible(true);to.set(null,from.get(null));}try{Field f=old.getDeclaredField("originFlying");f.setAccessible(true);originFlying=f.getBoolean(null);}catch(NoSuchFieldException ignored){}}active.setBoolean(null,false);Method release=old.getDeclaredMethod("release");release.setAccessible(true);release.invoke(null);Field tf=old.getDeclaredField("inputTransformer");tf.setAccessible(true);Object t=tf.get(null);if(t!=null)inst.removeTransformer((ClassFileTransformer)t);Field tr=old.getDeclaredField("trace");tr.setAccessible(true);Object trace=tr.get(null);if(trace instanceof Closeable c)c.close();}catch(ReflectiveOperationException ignored){}
   }retired.complete(null);
  }catch(Throwable e){retired.completeExceptionally(e);}});retired.get(5,TimeUnit.SECONDS);
  initCodes();instrumentation=inst;inputClass=cls("com.mojang.blaze3d.platform.InputConstants","fae");
  inputTransformer=new ClassFileTransformer(){public byte[] transform(Module module,ClassLoader l,String name,Class<?> c,ProtectionDomain p,byte[] bytes){
   if(!name.equals(inputClass.getName().replace('.','/')))return null;
   try{Files.write(dir.resolve(virtualKeys?"InputConstants-before-install.class":"InputConstants-before-restore.class"),bytes);byte[] result=InputKeyTransform.rewrite(bytes,loader,virtualKeys);Files.write(dir.resolve(virtualKeys?"InputConstants-installed.class":"InputConstants-restored.class"),result);return result;}catch(Exception e){throw new IllegalStateException(e);}
  }};
  inst.addTransformer(inputTransformer,true);try{inst.retransformClasses(inputClass);}catch(Throwable e){inst.removeTransformer(inputTransformer);throw e;}
  Path pendingCommand=dir.resolve("command.properties");if(Files.exists(pendingCommand)){Properties previous=new Properties();try(var r=Files.newBufferedReader(pendingCommand,StandardCharsets.UTF_8)){previous.load(r);}lastCommand=previous.getProperty("id","");}
  trace=Files.newBufferedWriter(dir.resolve("telemetry.jsonl"),StandardCharsets.UTF_8,StandardOpenOption.CREATE,StandardOpenOption.APPEND);
  atomic("status.json",json(Map.of("status","attached","gameDir",actual.toString(),"pid",ProcessHandle.current().pid(),"input_enabled",false)));
  Thread t=new Thread(()->{
   while(running){
    try{
     if(pending.compareAndSet(false,true))call(mc,new String[]{"execute"},new Class[]{Runnable.class},(Runnable)()->{try{tick();}catch(Throwable e){lastError=e.toString();commandStatus="failed";try{release();}catch(Exception ignored){}}finally{pending.set(false);}});
     Thread.sleep(10);
    }catch(Throwable e){try{atomic("error.json",json(Map.of("error",e.toString())));}catch(Exception ignored){}break;}
   }
  },"GameScaling-water-bridge");t.setDaemon(true);t.start();
 }
 static Method method(Class<?> c,String[] names,Class<?>[] types)throws Exception{
  String cache=c.getName()+Arrays.toString(names)+Arrays.toString(types);if(methods.containsKey(cache))return methods.get(cache);
  for(String n:names){try{Method m=c.getMethod(n,types);m.setAccessible(true);methods.put(cache,m);return m;}catch(NoSuchMethodException ignored){}
   for(Class<?> p=c;p!=null;p=p.getSuperclass())try{Method m=p.getDeclaredMethod(n,types);m.setAccessible(true);methods.put(cache,m);return m;}catch(NoSuchMethodException ignored){}
  }throw new NoSuchMethodException(cache);
 }
 static Object call(Object o,String[] names)throws Exception{return call(o,names,new Class[0]);}
 static Object call(Object o,String[] names,Class<?>[] types,Object...args)throws Exception{return method(o.getClass(),names,types).invoke(o,args);}
 static Object callStatic(Class<?> c,String[] names)throws Exception{return method(c,names,new Class[0]).invoke(null);}
 static Object field(Object o,String...names)throws Exception{
  String cache=o.getClass().getName()+Arrays.toString(names);Field f=fields.get(cache);if(f!=null)return f.get(o);
  for(String n:names)for(Class<?> p=o.getClass();p!=null;p=p.getSuperclass())try{f=p.getDeclaredField(n);f.setAccessible(true);fields.put(cache,f);return f.get(o);}catch(NoSuchFieldException ignored){}
  throw new NoSuchFieldException(cache);
 }
 static Class<?> cls(String named,String obf)throws Exception{try{return Class.forName(named,false,loader);}catch(ClassNotFoundException e){return Class.forName(obf,false,loader);}}
 static double number(Object o,String...names)throws Exception{return ((Number)call(o,names)).doubleValue();}
 static double[] xyz(Object p)throws Exception{return new double[]{number(p,"getX","dt"),number(p,"getY","dv"),number(p,"getZ","dz")};}
 static void release()throws Exception{applyKeys(Set.of());actionEnd=0;}
 static boolean ready()throws Exception{
  Object screen=field(mc,"screen","y");return (boolean)call(mc,new String[]{"isWindowActive","aA"}) && !(screen!=null && ((cls("net.minecraft.client.gui.screens.PauseScreen","fny").isInstance(screen)&&screen!=modelOwnedPause)||cls("net.minecraft.client.gui.screens.ChatScreen","fmz").isInstance(screen)));
 }
 static void tick()throws Exception{
  if(!running)return;
  Object player=field(mc,"player","s"), level=field(mc,"level","r");
  if(player==null||level==null){release();return;}
  UUID id=(UUID)call(player,new String[]{"getUUID","cz"});
  if(playerId==null)playerId=id;
  if(!playerId.equals(id)){release();throw new IllegalStateException("Player changed");}
  Path command=dir.resolve("command.properties");
  if(Files.exists(command)){
   Properties p=new Properties();try(var r=Files.newBufferedReader(command,StandardCharsets.UTF_8)){p.load(r);}
   String next=p.getProperty("id","");
   if(!next.isEmpty()&&!next.equals(lastCommand)){
    lastCommand=next;
    try{handle(p,player);}catch(Exception e){release();commandStatus="rejected";lastError=e.toString();}
   }
  }
  long now=System.nanoTime();boolean canAct=ready();
  if(actionEnd>0){
   if(!canAct){release();commandStatus="aborted_focus_or_menu";}
   else if(now>=actionEnd){release();commandStatus="completed";}
   else{
    int slot=Math.min(5,(int)((now-actionStart)/33333333L));Set<String> wanted=new HashSet<>(Arrays.asList(steps[slot].strip().split(" +")));wanted.remove("");
    applyKeys(wanted);
    double fraction=Math.min(1,(slot+1)/6.0);double nx=dx*fraction,ny=dy*fraction;
    if(field(mc,"screen","y")==null){Object opt=call(field(mc,"options","m"),new String[]{"sensitivity","d"});double sensitivity=((Number)call(opt,new String[]{"get","c"})).doubleValue();double factor=Math.pow(sensitivity*.6+.2,3)*8;call(player,new String[]{"turn","b"},new Class[]{double.class,double.class},(nx-appliedX)*factor,(ny-appliedY)*factor);}
    else{double cx=number(mouse,"xpos","e"),cy=number(mouse,"ypos","f");double w=number(window,"getScreenWidth","n"),h=number(window,"getScreenHeight","o");cx=Math.max(0,Math.min(w-1,cx+nx-appliedX));cy=Math.max(0,Math.min(h-1,cy+ny-appliedY));Class.forName("org.lwjgl.glfw.GLFW",false,loader).getMethod("glfwSetCursorPos",long.class,double.class,double.class).invoke(null,windowId,cx,cy);call(mouse,new String[]{"onMove","b"},new Class[]{long.class,double.class,double.class},windowId,cx,cy);}
    appliedX=nx;appliedY=ny;
    if(!scrollSent){call(mouse,new String[]{"onScroll","a"},new Class[]{long.class,double.class,double.class},windowId,0.,(double)scroll);scrollSent=true;}

   }
  }
  if(now-lastSample>=50000000L){
   lastSample=now;Map<String,Object>s=new LinkedHashMap<>();s.put("sequence",++sequence);s.put("wall_ms",System.currentTimeMillis());s.put("mono_ns",now);s.put("episode",episode);
   s.put("position",xyz(player));s.put("yaw",number(player,"getYRot","dE"));s.put("pitch",number(player,"getXRot","dG"));s.put("flying",field(call(player,new String[]{"getAbilities","fZ"}),"flying","b"));s.put("on_ground",call(player,new String[]{"onGround","aF"}));s.put("in_water",call(player,new String[]{"isInWater","bf"}));
   s.put("dimension",String.valueOf(call(level,new String[]{"dimension","af"})));s.put("game_tick",call(level,new String[]{"getGameTime","Z"}));s.put("ready",canAct);s.put("action_id",lastCommand);s.put("action_status",commandStatus);s.put("error",lastError);s.put("held",held);
   Object hit=call(player,new String[]{"pick","a"},new Class[]{double.class,float.class,boolean.class},6.0,1.0f,true);
   s.put("ray_type",String.valueOf(call(hit,new String[]{"getType","c"})));
   if(hit.getClass()==cls("net.minecraft.world.phys.BlockHitResult","ewy")){
    Object block=call(hit,new String[]{"getBlockPos","a"});s.put("ray_block",new double[]{number(block,"getX","u"),number(block,"getY","v"),number(block,"getZ","w")});
    Object fluid=call(level,new String[]{"getFluidState","b_"},new Class[]{cls("net.minecraft.core.BlockPos","jd")},block);
    Object fluidType=call(fluid,new String[]{"getType","a"});Class<?> fluids=cls("net.minecraft.world.level.material.Fluids","epf");Object water;try{water=fluids.getField("WATER").get(null);}catch(NoSuchFieldException ex){water=fluids.getField("c").get(null);}s.put("ray_water",fluidType==water);s.put("ray_fluid",String.valueOf(fluidType));s.put("ray_source",call(fluid,new String[]{"isSource","b"}));
   }
   extraSnapshot(s,player,level);
   String line=json(s);try{atomic("snapshot.json",line);}catch(IOException e){System.err.println("GameScaling snapshot skipped: "+e);}
   try{trace.write(line);trace.newLine();trace.flush();if(!running)trace.close();}catch(IOException e){System.err.println("GameScaling trace write failed: "+e);}
  }
 }
 static void handle(Properties p,Object player)throws Exception{
  String op=p.getProperty("op");lastError="";
  if("stop".equals(op)){release();episode="idle";commandStatus="stopped";return;}
  if("shutdown".equals(op)){
   release();virtualKeys=false;Throwable failure=null;
   try{instrumentation.retransformClasses(inputClass);}catch(Throwable e){failure=e;StringWriter sw=new StringWriter();e.printStackTrace(new PrintWriter(sw));Files.writeString(dir.resolve("shutdown-error.txt"),sw.toString());}
   finally{instrumentation.removeTransformer(inputTransformer);running=false;for(int key:codes.values())System.clearProperty("gamescaling.v5.key."+key);}
   commandStatus=failure==null?"shutdown":"shutdown_restore_failed";lastError=failure==null?"":failure.toString();lastSample=0;
   atomic("status.json",json(Map.of("status",commandStatus,"action_id",lastCommand,"keys_released",true,"observer_stopped",true,"transformer_removed",true,"class_restored",failure==null,"error",lastError)));return;
  }
  if("origin".equals(op)){
   release();originFlying=(boolean)field(call(player,new String[]{"getAbilities","fZ"}),"flying","b");double[] v=xyz(player);origin=new Object[]{v[0],v[1],v[2],(float)number(player,"getYRot","dE"),(float)number(player,"getXRot","dG")};
   if(p.containsKey("x")){double x=Double.parseDouble(p.getProperty("x")),y=Double.parseDouble(p.getProperty("y")),z=Double.parseDouble(p.getProperty("z"));float yaw=Float.parseFloat(p.getProperty("yaw")),pitch=Float.parseFloat(p.getProperty("pitch"));if(!Double.isFinite(x)||!Double.isFinite(y)||!Double.isFinite(z)||!Float.isFinite(yaw)||!Float.isFinite(pitch))throw new IllegalArgumentException("Finite baseline pose required");v=new double[]{x,y,z};origin=new Object[]{x,y,z,yaw,pitch};}
   Object inv=call(player,new String[]{"getInventory","fY"});int size=((Number)call(inv,new String[]{"getContainerSize","b"})).intValue();originItems=new Object[size];for(int i=0;i<size;i++)originItems[i]=call(call(inv,new String[]{"getItem","a"},new Class[]{int.class},i),new String[]{"copy","s"});originSelected=((Number)field(inv,"selected","k")).intValue();originMode=call(field(mc,"gameMode","q"),new String[]{"getPlayerMode","j"});originDay=((Number)call(field(mc,"level","r"),new String[]{"getDayTime","aa"})).longValue();
   Object im=field(player,"inventoryMenu","cc"),craft=call(im,new String[]{"getCraftSlots","r"});int cn=((Number)call(craft,new String[]{"getContainerSize","b"})).intValue();originCraft=new Object[cn];for(int i=0;i<cn;i++)originCraft[i]=call(call(craft,new String[]{"getItem","a"},new Class[]{int.class},i),new String[]{"copy","s"});originCarried=call(call(im,new String[]{"getCarried","g"}),new String[]{"copy","s"});
   Map<String,Object> state=new LinkedHashMap<>();state.put("position",v);state.put("flying",originFlying);state.put("yaw",origin[3]);state.put("pitch",origin[4]);state.put("wall_ms",System.currentTimeMillis());extraSnapshot(state,player,field(mc,"level","r"));atomic("origin.json",json(state));commandStatus="origin_recorded";return;
  }
  if("episode".equals(op)){release();episode=p.getProperty("name","idle");commandStatus="episode_set";return;}
  if("reset".equals(op)){
   if(origin==null)throw new IllegalStateException("Record a live origin first");release();episode="reset";
   if(field(mc,"screen","y")!=null)call(player,new String[]{"closeContainer","s"});
   setField(call(player,new String[]{"getInventory","fY"}),originSelected,"selected","k");
   setField(call(player,new String[]{"getAbilities","fZ"}),originFlying,"flying","b");call(player,new String[]{"onUpdateAbilities","z"});
   Object clientMenu=field(player,"inventoryMenu","cc"),clientCraft=call(clientMenu,new String[]{"getCraftSlots","r"});
   call(clientMenu,new String[]{"setCarried","b"},new Class[]{cls("net.minecraft.world.item.ItemStack","cuq")},call(originCarried,new String[]{"copy","s"}));
   Object visibleMenu=field(player,"containerMenu","cd");if(visibleMenu!=clientMenu)call(visibleMenu,new String[]{"setCarried","b"},new Class[]{cls("net.minecraft.world.item.ItemStack","cuq")},call(originCarried,new String[]{"copy","s"}));
   for(int i=0;i<originCraft.length;i++)call(clientCraft,new String[]{"setItem","a"},new Class[]{int.class,cls("net.minecraft.world.item.ItemStack","cuq")},i,call(originCraft[i],new String[]{"copy","s"}));
   Object server=call(mc,new String[]{"getSingleplayerServer","V"});if(server==null)throw new IllegalStateException("Not single player");
   Object[] saved=origin.clone();UUID id=playerId;
   call(server,new String[]{"execute"},new Class[]{Runnable.class},(Runnable)()->{try{
    Object list=call(server,new String[]{"getPlayerList","ah"});Object sp=call(list,new String[]{"getPlayer","a"},new Class[]{UUID.class},id);
    Object world=call(server,new String[]{"overworld","I"});
    call(sp,new String[]{"teleportTo","a"},new Class[]{cls("net.minecraft.server.level.ServerLevel","aqu"),double.class,double.class,double.class,float.class,float.class},world,saved[0],saved[1],saved[2],saved[3],saved[4]);
    call(sp,new String[]{"setDeltaMovement","n"},new Class[]{double.class,double.class,double.class},0.0,0.0,0.0);
    Object inv=call(sp,new String[]{"getInventory","fY"});for(int i=0;i<originItems.length;i++)call(inv,new String[]{"setItem","a"},new Class[]{int.class,cls("net.minecraft.world.item.ItemStack","cuq")},i,call(originItems[i],new String[]{"copy","s"}));
    setField(inv,originSelected,"selected","k");call(sp,new String[]{"setGameMode","a"},new Class[]{cls("net.minecraft.world.level.GameType","dct")},originMode);setField(call(sp,new String[]{"getAbilities","fZ"}),originFlying,"flying","b");call(sp,new String[]{"onUpdateAbilities","z"});call(world,new String[]{"setDayTime","b"},new Class[]{long.class},originDay);
    Object im=field(sp,"inventoryMenu","cc"),craft=call(im,new String[]{"getCraftSlots","r"});for(int i=0;i<originCraft.length;i++)call(craft,new String[]{"setItem","a"},new Class[]{int.class,cls("net.minecraft.world.item.ItemStack","cuq")},i,call(originCraft[i],new String[]{"copy","s"}));call(im,new String[]{"setCarried","b"},new Class[]{cls("net.minecraft.world.item.ItemStack","cuq")},call(originCarried,new String[]{"copy","s"}));call(im,new String[]{"broadcastChanges","d"});

   }catch(Exception e){try{atomic("reset-error.json",json(Map.of("error",e.toString())));}catch(Exception ignored){}}});
   commandStatus="reset_queued_verify_position";return;
  }
  if(!"action".equals(op))throw new IllegalArgumentException("Unknown command");
  if(!ready())throw new IllegalStateException("World must be active without menu");
  long submitted=Long.parseLong(p.getProperty("submitted_ms"));if(Math.abs(System.currentTimeMillis()-submitted)>1500)throw new IllegalStateException("Stale command");
  release();steps=p.getProperty("steps").split(";",-1);if(steps.length!=6)throw new IllegalArgumentException("Six steps required");
  for(String step:steps)for(String k:step.strip().split(" +"))if(!k.isEmpty()&&!codes.containsKey(k)&&!Set.of("LB","RB","MB").contains(k))throw new IllegalArgumentException("Unsupported key: "+k);
  double mx=Double.parseDouble(p.getProperty("mouse_x","0")),my=Double.parseDouble(p.getProperty("mouse_y","0"));
  if(!Double.isFinite(mx)||!Double.isFinite(my)||Math.abs(mx)>1000||Math.abs(my)>1000)throw new IllegalArgumentException("Aim limited to +/-1000 permille");
  dx=mx*Integer.parseInt(p.getProperty("width"))/1000;dy=my*Integer.parseInt(p.getProperty("height"))/1000;appliedX=appliedY=0;scroll=Integer.parseInt(p.getProperty("scroll","0"));if(Math.abs(scroll)>5)throw new IllegalArgumentException("Scroll limit");scrollSent=false;
  actionStart=System.nanoTime();actionEnd=actionStart+200000000L;commandStatus="running";
 }

 static void initCodes(){
  for(char c='A';c<='Z';c++)codes.put(""+c,(int)c);
  String[] digits={"zero","one","two","three","four","five","six","seven","eight","nine"};for(int i=0;i<10;i++)codes.put(digits[i],48+i);
  String[] f={"One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten","Eleven","Twelve"};for(int i=0;i<12;i++)codes.put(f[i],290+i);
  String[] names={"Space","Shift","Ctrl","Alt","Esc","Enter","Tab","Back","Insert","Delete","Right","Left","Down","Up","Home","End","Caps","Pause","Equal","Minus","Period","Slash","Quote"};int[] values={32,340,341,342,256,257,258,259,260,261,262,263,264,265,268,269,280,284,61,45,46,47,39};for(int i=0;i<names.length;i++)codes.put(names[i],values[i]);
 }
 static int modifiers(Set<String>s){return (s.contains("Shift")?1:0)|(s.contains("Ctrl")?2:0)|(s.contains("Alt")?4:0);}
 static void applyKeys(Set<String>wanted)throws Exception{
  for(var entry:codes.entrySet())System.setProperty("gamescaling.v5.key."+entry.getValue(),Boolean.toString(wanted.contains(entry.getKey())));
  for(String name:new HashSet<>(held))if(!wanted.contains(name))event(name,false,modifiers(wanted));
  for(String name:wanted)if(!held.contains(name))event(name,true,modifiers(wanted));held=new HashSet<>(wanted);
 }
 static void event(String name,boolean down,int mods)throws Exception{
  if(Set.of("LB","RB","MB").contains(name)){int button=name.equals("LB")?0:name.equals("RB")?1:2;call(mouse,new String[]{"onPress","a"},new Class[]{long.class,int.class,int.class,int.class},windowId,button,down?1:0,mods);return;}
  int code=codes.get(name);call(keyboard,new String[]{"keyPress","a"},new Class[]{long.class,int.class,int.class,int.class,int.class},windowId,code,0,down?1:0,mods);
  if(down&&name.equals("Esc")){Object currentScreen=field(mc,"screen","y");modelOwnedPause=currentScreen!=null&&cls("net.minecraft.client.gui.screens.PauseScreen","fny").isInstance(currentScreen)?currentScreen:null;}
  if(down&&field(mc,"screen","y")!=null&&(mods&6)==0){int ch=code;if(code>=65&&code<=90&&(mods&1)==0)ch=code+32;if(code==32||code>=39&&code<=90)call(keyboard,new String[]{"charTyped","a"},new Class[]{long.class,int.class,int.class},windowId,ch,mods);}
 }
 static void setField(Object o,Object value,String...names)throws Exception{field(o,names);fields.get(o.getClass().getName()+Arrays.toString(names)).set(o,value);}
 static Object itemRegistry()throws Exception{Class<?> c=cls("net.minecraft.core.registries.BuiltInRegistries","lt");try{return c.getField("ITEM").get(null);}catch(NoSuchFieldException e){return c.getField("g").get(null);}}
 static Map<String,Object> item(Object stack)throws Exception{
  boolean empty=(boolean)call(stack,new String[]{"isEmpty","e"});if(empty)return Map.of("id","minecraft:air","count",0);
  Object it=call(stack,new String[]{"getItem","g"});String id=String.valueOf(call(itemRegistry(),new String[]{"getKey","b"},new Class[]{Object.class},it));return Map.of("id",id,"count",call(stack,new String[]{"getCount","H"}));
 }
 static List<Object> contents(Object inv)throws Exception{int n=((Number)call(inv,new String[]{"getContainerSize","b"})).intValue();List<Object>a=new ArrayList<>();for(int i=0;i<n;i++)a.add(item(call(inv,new String[]{"getItem","a"},new Class[]{int.class},i)));return a;}
 static void extraSnapshot(Map<String,Object>s,Object player,Object level)throws Exception{
  Object inv=call(player,new String[]{"getInventory","fY"}),screen=field(mc,"screen","y");s.put("inventory",contents(inv));s.put("selected_slot",field(inv,"selected","k"));s.put("health",number(player,"getHealth","ew"));s.put("mode",String.valueOf(call(field(mc,"gameMode","q"),new String[]{"getPlayerMode","j"})));s.put("day_time",call(level,new String[]{"getDayTime","aa"}));s.put("screen",screen==null?null:screen.getClass().getName());s.put("cursor",new double[]{number(mouse,"xpos","e"),number(mouse,"ypos","f")});s.put("window",new double[]{number(window,"getScreenWidth","n"),number(window,"getScreenHeight","o")});
  Object menu=field(player,"containerMenu","cd");s.put("menu",menu.getClass().getName());s.put("carried",item(call(menu,new String[]{"getCarried","g"})));Object inventoryMenu=field(player,"inventoryMenu","cc");s.put("crafting_grid",contents(call(inventoryMenu,new String[]{"getCraftSlots","r"})));s.put("crafting_result",contents(field(inventoryMenu,"resultSlots","H")));
  s.put("model_owned_pause",screen!=null&&screen==modelOwnedPause);s.put("shift_down",callStatic(cls("net.minecraft.client.gui.screens.Screen","fod"),new String[]{"hasShiftDown","s"}));
 }

 static void atomic(String name,String value)throws IOException{
  // Avoid replacing an open Windows file. CRC protects concurrent partial reads.
  String payload=value;
  if(name.equals("snapshot.json")){CRC32 crc=new CRC32();crc.update(value.getBytes(StandardCharsets.UTF_8));payload=json(Map.of("payload",value,"crc32",crc.getValue()));}
  IOException last=null;
  for(int i=0;i<3;i++)try{Files.writeString(dir.resolve(name),payload,StandardCharsets.UTF_8,StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE);return;}catch(IOException e){last=e;try{Thread.sleep(1);}catch(InterruptedException x){Thread.currentThread().interrupt();}}
  throw last;
 }
 static String json(Object v){
  if(v==null)return "null";if(v instanceof Number||v instanceof Boolean)return v.toString();
  if(v instanceof Map<?,?>m){List<String>a=new ArrayList<>();m.forEach((k,x)->a.add(json(k.toString())+":"+json(x)));return "{"+String.join(",",a)+"}";}
  if(v instanceof Iterable<?>list){List<String>a=new ArrayList<>();for(Object x:list)a.add(json(x));return "["+String.join(",",a)+"]";}
  if(v.getClass().isArray()){List<String>a=new ArrayList<>();for(int i=0;i<Array.getLength(v);i++)a.add(json(Array.get(v,i)));return "["+String.join(",",a)+"]";}
  return "\""+v.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t")+"\"";
 }
}
