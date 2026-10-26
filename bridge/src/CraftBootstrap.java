package org.gamescaling.launcher.v6;
import java.lang.instrument.Instrumentation;
import java.net.URLClassLoader;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.io.*;
import java.util.*;
public class CraftBootstrap {
 static volatile boolean alive=true;static String last="";static URLClassLoader active;
 public static void agentmain(String args,Instrumentation inst)throws Exception{
  Path config=Path.of(args).toAbsolutePath(),base=config.getParent();
  Files.writeString(base.resolve("bootstrap-status.txt"),"Bootstrap started\n");
  Thread watcher=new Thread(()->{
   while(alive){try{
    Path request=base.resolve("reload.properties");
    if(Files.exists(request)){
     Properties p=new Properties();try(var r=Files.newBufferedReader(request,StandardCharsets.UTF_8)){p.load(r);}
     String id=p.getProperty("id","");
     if(!id.isEmpty()&&!id.equals(last)){
      last=id;if(p.getProperty("op","").equals("shutdown")){alive=false;Files.writeString(base.resolve("bootstrap-status.txt"),"Bootstrap shutdown\n");break;}
      Path jar=base.resolve(p.getProperty("jar","craft-bridge-5min.jar")).normalize();if(!jar.getParent().equals(base))throw new IllegalArgumentException("Jar must be in this task directory");
      try{
       active=new URLClassLoader(new java.net.URL[]{jar.toUri().toURL()},ClassLoader.getPlatformClassLoader());
       Class<?> c=Class.forName("org.gamescaling.craftbridge.v5.WaterTaskBridge",true,active);c.getMethod("agentmain",String.class,Instrumentation.class).invoke(null,config.toString(),inst);
       Files.writeString(base.resolve("bootstrap-status.txt"),"Implementation attached: "+id+"\n");
      }catch(Throwable e){StringWriter buffer=new StringWriter();e.printStackTrace(new PrintWriter(buffer));Files.writeString(base.resolve("initialization-error.txt"),buffer.toString());Files.writeString(base.resolve("bootstrap-status.txt"),"Implementation failed: "+id+" (see initialization-error.txt)\n");}
     }
    }
    Thread.sleep(250);
   }catch(Throwable e){try{Files.writeString(base.resolve("bootstrap-error.txt"),e.toString());}catch(Exception ignored){}break;}
   }
  },"GameScaling-craft-bootstrap");watcher.setDaemon(true);watcher.start();
 }
}
