import math, sys, types, subprocess, random
exec(open("trace.py").read().split("def land")[0])
import energy as en
def chgturn(m,TG,shots,w,t2,b,speed=1.0):
    C=m.PathCamera(TG,T)
    for _ in range(90): prev=C.step(1/30,*shots[0],w,speed,b)
    t=0; r=0; gapeye=0
    while t<t2+0.1:
        s=shots[1] if t<t2 else shots[2]; chg=s!=C.D.shot and t>0.01
        was=C.blending()
        out=C.step(1/30,*s,w,speed,b)
        if chg and was and C.blending():
            r=math.degrees(fl.angle(prev[1],out[1]))*30
            gapeye=abs(math.log((dr.spherical(out[0])[1]+30)/(dr.spherical(C.D.pose[0])[1]+30)))
        prev=out; t+=1/30
    return r,gapeye
mA=mod(src.replace("le = math.log(dr.spherical(out[0])[1] + dr.H0)","le = math.log(dr.spherical(self.D.pose[0])[1] + dr.H0)"))
mB=mod(src.replace("        own = fl.angle(prev[0], base[1])","        own = 0.0 if getattr(self,'_chg',False) else fl.angle(prev[0], base[1])").replace("        cut = changed and not self.D.blending()","        cut = changed and not self.D.blending(); self._chg = changed"))
cases=[(FAR,[('follow','lake'),('rise','moon'),('vantage','moon')],0.6,6.9,30.0),(FAR,[('follow','coast'),('follow','moon'),('orbit','moon')],0.3,6.5,15.0),(FAR,[('vantage','coast'),('orbit','sun'),('vantage','river')],0.3,3.0,6.0)]
for c in cases:
    print("change frame deg/s: new %.0f | k from Director eye %.0f | own=0 on change %.0f | keep off %.0f | 158d3c1 %.0f"%tuple(chgturn(m,*c)[0] for m in (pc,mA,mB,off,old)))
random.seed(7)
for name,TG in (("near",TARGETS),("far",FAR)):
    for b in (30.0,15.0):
        n=0; over=[0,0,0]; worst=(0,); held=0
        for _ in range(150):
            shots=[(random.choice(pc.PATHS),random.choice(pc.TARGETS)) for _ in range(3)]
            if shots[1]==shots[2] or shots[0]==shots[1]: continue
            w=random.choice((0.0,0.3,0.3,0.6,1.0)); t2=random.uniform(1,12)
            n+=1; L=60*36/b
            for i,m in enumerate((pc,off,old)):
                r,g=chgturn(m,TG,shots,w,t2,b)
                over[i]+= r>L
                if i==0 and r>worst[0]: worst=(round(r),shots,w,round(t2,1),round(g,2))
        print(name,"fade",b,"changes mid-blend",n,"change frame over limit %d: new %d, keep off %d, 158d3c1 %d"%(L,*over),"worst",worst)
# item 7: accent
class Dv: beat=1.0; e=1.0; kick=0.5; phase=0.3
A=pc.PathCamera(TARGETS,T); B=pc.PathCamera(TARGETS,T); mx=0; tilt=9; lensr=9; dd=0
for i in range(90+600):
    s=("orbit","coast") if i<90 else ("orbit","sun")
    a=A.step(1/30,*s,0.3,1.0,30.0,Dv); b_=B.step(1/30,*s,0.3,1.0,30.0)
    ref=en.accent(b_,Dv)
    mx=max(mx,math.degrees(fl.angle(a[1],ref[1])),abs(a[3]-ref[3]))
    if A.blending(): tilt=min(tilt,math.degrees(fl.angle(a[1],b_[1]))); lensr=min(lensr,abs(a[3]/b_[3]-0.85)); dd=max(dd,math.degrees(fl.angle(A.D.pose[1],B.D.pose[1])))
print("accent: step(drive) vs accent(step()) max diff %.2g deg; least tilt in blend %.3f deg (BEAT_TILT %.3f); lens ratio off 0.85 by %.2g; D.pose diff with/without drive %.2g deg"%(mx,tilt,math.degrees(en.BEAT_TILT),lensr,dd))
