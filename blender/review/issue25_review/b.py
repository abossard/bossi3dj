exec(open(__file__.rsplit("/",1)[0]+"/sim.py").read())
import random, time
random.seed(int(sys.argv[1])); far=sys.argv[2]=="far"; fade=float(sys.argv[3])
if far:
    TARGETS["coast"]=pc.ground_target("coast", fl.offset(T.c,T.e,T.n,-20000.0,14000.0), T, 800.0)
    TARGETS["lake"]=pc.ground_target("lake", fl.offset(T.c,T.e,T.n,15000.0,-18000.0), T, 600.0)
best=[]; kend=[]; t0=time.time(); n=0
while time.time()-t0<float(sys.argv[4]):
    n+=1
    shots=[(random.choice(pc.PATHS),random.choice(pc.TARGETS)) for _ in range(3)]
    w=random.choice((0.0,0.3,0.3,0.6,1.0)); t2=random.uniform(2,25) if random.random()<0.6 else 99
    C=pc.PathCamera(TARGETS,T)
    for _ in range(90): prev=C.step(DT,*shots[0],w,1.0,fade)
    was=False; mt=(0,)
    for i in range(int(50/DT)):
        t=i*DT; s=shots[1] if t<t2 else shots[2]
        cutframe = i==0 or abs(t-t2)<DT/2 and fade==0
        out=C.step(DT,*s,w,1.0,fade)
        tr=math.degrees(fl.angle(prev[1],out[1]))/DT
        if tr>mt[0]: mt=(round(tr,1),round(t,2),round(math.degrees(fl.angle(*C.views)) if C.views else 0,2),int(C.blending()),round(dr.spherical(out[0])[1]))
        if was and not C.blending(): kend.append((round(math.degrees(fl.angle(*C.views)) if C.views else 0,3),shots,w,round(t2,1)))
        was=C.blending(); prev=out
    best.append((mt,shots,w,round(t2,1)))
best.sort(reverse=True); kend.sort(reverse=True)
print(sys.argv[1:],"runs",n)
for b in best[:5]: print(" turn",b)
print(" k left at blend end >0:",sum(k[0]>0 for k in kend),"of",len(kend), kend[:3])
