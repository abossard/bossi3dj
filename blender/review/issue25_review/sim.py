import math, os, sys
ROOT="/Users/abossard/Desktop/projects/bossi3dj"
HERE=ROOT+"/blender/review"
G={"__name__":"x","__file__":HERE+"/verify_paths.py"}
ARGV=sys.argv[:]; sys.argv=["x"]
exec(open(G["__file__"]).read().split("# 1. live paths")[0],G)
dr,fl,pc,T,TARGETS,DT,half_v=(G[k] for k in ("dr","fl","pc","T","TARGETS","DT","half_v"))
def land(p,fwd,lens):
    u,h=dr.spherical(p); pitch=math.asin(fl.clamp(fl.dot(fwd,u),-1,1)); dip=math.acos(fl.R/(fl.R+max(h,0))); hv=half_v(lens)
    return fl.clamp((-dip-(pitch-hv))/(2*hv),0,1)
def run(prog, secs, tag, every=1.0):
    C=pc.PathCamera(TARGETS,T); t=0; prev=None; i=0; mt=0; dark=0
    print("==",tag)
    while t<secs:
        while i+1<len(prog) and prog[i+1][0]<=t: i+=1
        _,path,target,w,blend=prog[i]
        out=C.step(DT,path,target,w,1.0,blend)
        live=C.live(path,target,math.exp(C.lh))
        tr=math.degrees(fl.angle(prev[1],out[1]))/DT if prev else 0
        if t>prog[1][0]: mt=max(mt,tr)
        l=land(*out[:2],out[3]); 
        if C.blending() and l<0.1: dark+=DT
        if abs(t/every-round(t/every))<DT/every/2 and t>=prog[1][0]-1:
            print("t %5.1f %-14s eye %6.0f land %.2f k %.2f bl %d off-live %5.1f deg turn %5.1f"%(t,path+" "+target,dr.spherical(out[0])[1],l,(math.degrees(fl.angle(*C.views)) if C.views else 0),C.blending(),math.degrees(fl.angle(out[1],live[1])),tr))
        prev=out; t+=DT
    print("max turn %.1f deg/s, blend s land<0.1: %.1f"%(mt,dark))
sys.argv=ARGV
