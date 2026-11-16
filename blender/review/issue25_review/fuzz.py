import math, os, sys, random, time, types
ROOT="/Users/abossard/Desktop/projects/bossi3dj"
G={"__name__":"x","__file__":ROOT+"/blender/review/verify_paths.py"}
av=sys.argv[:]; sys.argv=["x"]
exec(open(G["__file__"]).read().split("# 1. live paths")[0],G); sys.argv=av
dr,fl,pc,T,TARGETS,half_v=(G[k] for k in ("dr","fl","pc","T","TARGETS","half_v"))
import energy as en
FAR=dict(TARGETS, coast=pc.ground_target("coast", fl.offset(T.c,T.e,T.n,-20000.0,14000.0), T, 800.0), lake=pc.ground_target("lake", fl.offset(T.c,T.e,T.n,15000.0,-18000.0), T, 600.0))
src=open(ROOT+"/blender/scenes/path_camera.py").read()
off=types.ModuleType("off"); exec(compile(src.replace("BLEND_LAND = 0.35","BLEND_LAND = 0.0 "),"off","exec"),off.__dict__)
class Rec(pc.PathCamera):
    def turn_limited(self, base, out, dt, cut, left, blend_s):
        r=super().turn_limited(base,out,dt,cut,left,blend_s)
        self.rec=(base[1],out[1],r[1],left)
        return r
seed=int(sys.argv[1]); secs=float(sys.argv[2]); mode=sys.argv[3]   # fixed | jitter
random.seed(seed)
stats={}   # blend_s -> dict
def st(b): return stats.setdefault(b,dict(n=0,maxturn=(0,),maxturn_off=(0,),over=0,over_off=0,endgap=(0,),endjump=(0,),chg=(0,),nan=0,blends=0))
t0=time.time(); errs=[]
while time.time()-t0<secs:
    shots=[(random.choice(pc.PATHS),random.choice(pc.TARGETS)) for _ in range(3)]
    w=random.choice((0.0,0.3,0.3,0.6,1.0)); t2=random.uniform(0.5,25) if random.random()<0.7 else 99
    b=random.choice((0.5,2.0,6.0,15.0,30.0,30.0,60.0)); far=random.random()<0.4
    speed=random.choice((1.0,1.0,0.3,3.6)); TG=FAR if far else TARGETS
    S=st(b); S["n"]+=1; L=60.0*36.0/b
    desc=(shots,w,round(t2,1),b,"far" if far else "near",speed,seed)
    for which,mod in (("on",None),("off",off)):
        C=Rec(TG,T) if mod is None else mod.PathCamera(TG,T)
        rs=random.Random(seed*1000+S["n"])
        try:
            for _ in range(90): prev=C.step(1/30,*shots[0],w,speed,b)
            t=0.0; was=False; pbase=None; i=0; lastgap=0
            while t<45.0:
                dt=1/30 if mode=="fixed" else rs.choice((1/60,1/30,1/30,1/24,0.05,0.1,0.0))
                s=shots[1] if t<t2 else shots[2]
                chg=(s!=C.D.shot)
                out=C.step(dt,*s,w,speed,b)
                if any(x!=x for v in out[:3] for x in v) or out[3]!=out[3]: S["nan"]+=1
                bl=C.blending()
                if dt>0:
                    tr=math.degrees(fl.angle(prev[1],out[1]))/dt
                    key="maxturn" if mod is None else "maxturn_off"
                    if not (chg and not bl) :   # leave the cut frame out
                        if tr>S[key][0]: S[key]=(round(tr,1),round(t,2),desc)
                        if tr>L*1.0001: S["over" if mod is None else "over_off"]+=1
                    if mod is None:
                        base,kept,shown,left=C.rec
                        if chg and bl and was:   # change mid-blend
                            if tr>S["chg"][0]: S["chg"]=(round(tr,1),round(t,2),desc)
                        if was and not bl and not chg:      # blend ended this frame
                            S["blends"]+=1
                            own=math.degrees(fl.angle(pbase,base))/dt
                            if lastgap>S["endgap"][0]: S["endgap"]=(round(lastgap,2),round(t,2),desc)
                            if tr-own>S["endjump"][0]: S["endjump"]=(round(tr-own,1),round(tr,1),round(own,1),round(t,2),desc)
                        if bl: lastgap=math.degrees(fl.angle(base,shown))
                        pbase=base
                was=bl; prev=out; t+=dt
        except Exception as ex:
            errs.append((repr(ex),desc,which))
for b in sorted(stats):
    S=stats[b]; print("blend",b,"runs",S["n"],"limit %.0f"%(60*36/b),"nan",S["nan"],"blend ends",S["blends"])
    for k in ("maxturn","maxturn_off","over","over_off","chg","endgap","endjump"): print("   ",k,S[k])
print("errors",len(errs),errs[:3])
