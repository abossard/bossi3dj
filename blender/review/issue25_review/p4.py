import math, sys, types, subprocess, random
exec(open("trace.py").read().split("def run")[0])
base=mod(subprocess.run(["git","-C",ROOT,"show","ea44a0b:blender/scenes/path_camera.py"],capture_output=True,text=True).stdout)
def fall(m,settle,prog_b,w0=1.0):
    C=m.PathCamera(TARGETS,T)
    for _ in range(int(settle*30)): prev=C.step(1/30,"vantage","planet",w0,1.0,30.0)
    dark=0; t=0; darks=[]; mt=0; upj=0; was=False; n=0
    while t<45:
        out=C.step(1/30,*prog_b,0.3,1.0,30.0)
        if C.blending():
            n+=1
            if land(out[0],out[1],out[3])<0.1: dark+=1/30; darks.append(round(t,1))
        mt=max(mt,math.degrees(fl.angle(prev[1],out[1]))*30)
        if was and not C.blending(): upj=math.degrees(fl.angle(prev[2],out[2]))
        was=C.blending(); prev=out; t+=1/30
    return "dark %.1f of %.1f s blend (t %s..%s) maxturn %.1f up jump at end %.2f deg"%(dark,n/30,darks[0] if darks else "-",darks[-1] if darks else "-",mt,upj)
for settle in (3,20):
  for tgt in (("orbit","river"),("follow","coast"),("orbit","moon")):
    for name,m in (("ea44a0b",base),("158d3c1",old),("new",pc)):
        print("settle",settle,tgt,name,fall(m,settle,tgt))
