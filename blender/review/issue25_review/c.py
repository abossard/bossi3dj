exec(open(__file__.rsplit("/",1)[0]+"/sim.py").read())
import subprocess, types
src=subprocess.run(["git","-C",ROOT,"show","ea44a0b:blender/scenes/path_camera.py"],capture_output=True,text=True).stdout
old=types.ModuleType("old"); exec(compile(src,"old","exec"),old.__dict__)
def case(mod,shots,w,t2,fade,far,tag):
    TG=dict(TARGETS)
    if far:
        TG["coast"]=pc.ground_target("coast", fl.offset(T.c,T.e,T.n,-20000.0,14000.0), T, 800.0)
        TG["lake"]=pc.ground_target("lake", fl.offset(T.c,T.e,T.n,15000.0,-18000.0), T, 600.0)
    C=mod.PathCamera(TG,T)
    for _ in range(90): prev=C.step(DT,*shots[0],w,1.0,fade)
    mt=(0,); was=False; ends=[]; over=0
    for i in range(int(50/DT)):
        t=i*DT; s=shots[1] if t<t2 else shots[2]
        out=C.step(DT,*s,w,1.0,fade)
        tr=math.degrees(fl.angle(prev[1],out[1]))/DT
        over+= tr>72
        if tr>mt[0]: mt=(round(tr,1),round(t,2),round(dr.spherical(out[0])[1]))
        if was and not C.blending():
            live=C.live(*s,math.exp(C.lh)); ends.append((round(t,2),round(getattr(C,"land_k",0),3),round(math.degrees(fl.angle(out[1],live[1])),1)))
        was=C.blending(); prev=out
    print(tag,"max turn",mt,"frames>72:",over,"blend ends (t,k,deg off live):",ends)
for shots,w,t2,fade,far in [
 ([('follow','lake'),('follow','coast'),('follow','sun')],0.6,24.0,30,True),
 ([('orbit','moon'),('follow','lake'),('orbit','sun')],0.6,19.4,30,True),
 ([('vantage','coast'),('vantage','river'),('rise','pyramids')],0.3,4.7,30,True),
 ([('vantage','planet'),('follow','coast'),('rise','river')],0.3,8.4,30,False),
 ([('follow','moon'),('vantage','sun'),('follow','moon')],0.3,11.0,30,False),
 ([('vantage','moon'),('follow','river'),('orbit','sun')],0.6,24.3,30,False),
 ([('vantage','coast'),('follow','lake'),('follow','sun')],0.6,99,6,False),
 ([('vantage','coast'),('follow','lake'),('follow','sun')],0.6,99,6,True),
]:
    print(shots,w,t2,"fade",fade,"far" if far else "near")
    case(old,shots,w,t2,fade,far,"  old"); case(pc,shots,w,t2,fade,far,"  new")
