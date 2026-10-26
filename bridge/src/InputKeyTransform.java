package org.gamescaling.craftbridge.v5;
import org.objectweb.asm.*;
public final class InputKeyTransform {
 public static byte[] rewrite(byte[] bytes,ClassLoader loader,boolean inject){
  ClassReader r=new ClassReader(bytes);ClassWriter w=new ClassWriter(ClassWriter.COMPUTE_FRAMES|ClassWriter.COMPUTE_MAXS){protected ClassLoader getClassLoader(){return loader;}};
  r.accept(new ClassVisitor(Opcodes.ASM9,w){public MethodVisitor visitMethod(int access,String n,String desc,String sig,String[] ex){
   MethodVisitor mv=super.visitMethod(access,n,desc,sig,ex);if(!(n.equals("isKeyDown")||n.equals("a"))||!desc.equals("(JI)Z"))return mv;
   return new MethodVisitor(Opcodes.ASM9,mv){int phase=0;
    void clear(){if(phase!=0)throw new IllegalStateException("Unrecognized legacy virtual-key instruction sequence");}
    public void visitLdcInsn(Object value){clear();if(value instanceof String s && s.matches("gamescaling\\.v[345]\\.key\\.")){phase=1;return;}super.visitLdcInsn(value);}
    public void visitVarInsn(int op,int var){if(phase==1&&op==Opcodes.ILOAD&&var==2){phase=2;return;}clear();super.visitVarInsn(op,var);}
    public void visitMethodInsn(int op,String owner,String name,String desc,boolean itf){
     boolean match=(phase==2&&op==Opcodes.INVOKESTATIC&&owner.equals("java/lang/Integer")&&name.equals("toString")&&desc.equals("(I)Ljava/lang/String;"))||(phase==3&&op==Opcodes.INVOKEVIRTUAL&&owner.equals("java/lang/String")&&name.equals("concat")&&desc.equals("(Ljava/lang/String;)Ljava/lang/String;"))||(phase==4&&op==Opcodes.INVOKESTATIC&&owner.equals("java/lang/Boolean")&&name.equals("getBoolean")&&desc.equals("(Ljava/lang/String;)Z"));
     if(match){phase++;return;}clear();super.visitMethodInsn(op,owner,name,desc,itf);
    }
    public void visitInsn(int op){if(phase==5&&op==Opcodes.IOR){phase=0;return;}clear();if(inject&&op==Opcodes.IRETURN){super.visitLdcInsn("gamescaling.v5.key.");super.visitVarInsn(Opcodes.ILOAD,2);super.visitMethodInsn(Opcodes.INVOKESTATIC,"java/lang/Integer","toString","(I)Ljava/lang/String;",false);super.visitMethodInsn(Opcodes.INVOKEVIRTUAL,"java/lang/String","concat","(Ljava/lang/String;)Ljava/lang/String;",false);super.visitMethodInsn(Opcodes.INVOKESTATIC,"java/lang/Boolean","getBoolean","(Ljava/lang/String;)Z",false);super.visitInsn(Opcodes.IOR);}super.visitInsn(op);}
    public void visitEnd(){clear();super.visitEnd();}
   };
  }},ClassReader.EXPAND_FRAMES);return w.toByteArray();
 }
}
