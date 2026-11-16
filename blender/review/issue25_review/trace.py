import math, sys, types, subprocess
ROOT="/Users/abossard/Desktop/projects/bossi3dj"
G={"__name__":"x","__file__":ROOT+"/blender/review/verify_paths.py"}
av=sys.argv[:]; sys.argv=["x"]
exec(open(G["__file__"]).read().split("# 1. live paths")[0],G); sys.argv=av
dr,fl,pc,T,TARGETS,half_v=(G[k] for k in ("dr","fl","pc","T","TARGETS","half_v"))
FAR=dict(TARGETS, coast=pc.ground_target("coast", fl.offset(T.c,T.e,T.n,-20000.0,14000.0), T, 800.0), lake=pc.ground_target("lake", fl.offset(T.c,T.e,T.n,15000.0,-18000.0), T, 600.0))
src=open(ROOT+"/blender/scenes/path_camera.py").read()
def mod(s):
    m=types.ModuleType("m"); exec(compile(s,"m","exec"),m.__dict__); return m
off=mod(src.replace("BLEND_LAND = 0.35","BLEND_LAND = 0.0 "))
old=mod(subprocess.run(["git","-C",ROOT,"show","158d3c1:blender/scenes/path_camera.py"],capture_output=True,text=True).stdout)
def land(p,fwd,lens):
    u,h=dr.spherical(p); pitch=math.asin(fl.clamp(fl.dot(fwd,u),-1,1)); dip=math.acos(fl.R/(fl.R+max(h,0))); hv=half_v(lens)
    return fl.clamp((-dip-(pitch-hv))/(2*hv),0,1)
def run(m,TG,shots,w,t2,b,speed,show=False,tag=""):
    C=m.PathCamera(TG,T); ks=[]
    if hasattr(C,"on_land") and m is pc:
        ol=C.on_land
        def rec(pose_,k,ends,left): ks.append(k); return ol(pose_,k,ends,left)
        C.on_land=rec
    for _ in range(90): prev=C.step(1/30,*shots[0],w,speed,b)
    t=0; mx=(0,)
    while t<t2+3:
        s=shots[1] if t<t2 else shots[2]; chg=s!=C.D.shot
        out=C.step(1/30,*s,w,speed,b)
        tr=math.degrees(fl.angle(prev[1],out[1]))*30
        if t>0.05 and tr>mx[0]: mx=(round(tr,1),round(t,2))
        if show and abs(t-t2)<0.12:
            eye=dr.spherical(out[0])[1]; deye=dr.spherical(C.D.pose[0])[1]
            print("  t %.2f chg %d bl %d eye %.0f dir-eye %.0f k %.2f land %.2f turn %.1f"%(t,chg,C.blending(),eye,deye,ks[-1] if ks else -1,land(out[0],out[1],out[3]),tr))
        prev=out; t+=1/30
    print(tag,"max turn after start",mx)
for TG,shots,w,t2,b,sp in [
 (FAR,[('follow','lake'),('rise','moon'),('vantage','moon')],0.6,6.9,30.0,1.0),
 (FAR,[('follow','coast'),('follow','moon'),('orbit','moon')],0.3,6.5,15.0,1.0),
 (FAR,[('vantage','coast'),('orbit','sun'),('vantage','river')],0.3,3.0,6.0,1.0),
 (FAR,[('orbit','lake'),('rise','sun'),('follow','moon')],1.0,13.8,60.0,1.0)]:
    print(shots,w,t2,b)
    run(pc,TG,shots,w,t2,b,sp,True,"  new"); run(off,TG,shots,w,t2,b,sp,False,"  keep off"); run(old,TG,shots,w,t2,b,sp,False,"  158d3c1")
