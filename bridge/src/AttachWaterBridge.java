import com.sun.tools.attach.VirtualMachine;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public class AttachWaterBridge {
 public static void main(String[] args)throws Exception {
  Path config=Path.of(args[0]).toAbsolutePath();Properties p=new Properties();
  try(var r=Files.newBufferedReader(config,StandardCharsets.UTF_8)){p.load(r);}
  String pid=args.length>1?args[1]:p.getProperty("pid");
  System.out.println("Attaching observation-only bridge to Minecraft PID "+pid);
  VirtualMachine vm=VirtualMachine.attach(pid);
  try{
   Properties sys=vm.getSystemProperties();String command=sys.getProperty("sun.java.command","").replace('\\','/').toLowerCase(Locale.ROOT);
   String game=p.getProperty("gameDir").replace('\\','/').toLowerCase(Locale.ROOT);
   if(!command.contains(game))throw new IllegalStateException("Target JVM game directory not verified. No agent loaded.");
   vm.loadAgent(config.getParent().resolve("craft-bridge-5min.jar").toString(),config.toString());
   System.out.println("Bootstrap attached. Check bootstrap-status.txt; starts observation only.");
  }finally{vm.detach();}
 }
}
