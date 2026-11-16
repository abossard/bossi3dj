import math, os, sys, subprocess, types
ROOT="/Users/abossard/Desktop/projects/bossi3dj"
src=open(ROOT+"/blender/tests/test_path_blends.py").read().replace("os.path.abspath(__file__)","'%s/blender/tests/x.py'"%ROOT)
G={"__name__":"tpb"}; exec(compile(src,"tpb","exec"),G)
cur=open(ROOT+"/blender/scenes/path_camera.py").read()
def mod(s,name):
    m=types.ModuleType(name); exec(compile(s,name,"exec"),m.__dict__); return m
def git(rev): return subprocess.run(["git","-C",ROOT,"show",rev+":blender/scenes/path_camera.py"],capture_output=True,text=True).stdout
def rep(a,b):
    assert a in cur, a
    return cur.replace(a,b)
V={
 "current":cur,
 "158d3c1":git("158d3c1"),
 "ea44a0b":git("ea44a0b"),
 "no write-back":rep("        if tr is not None:\n            self.D.pose = (self.D.pose[0],)","        if False:\n            self.D.pose = (self.D.pose[0],)"),
 "no turn limit":rep("        if prev is None or cut or dt <= 0.0 or left is None or left <= dt:","        if True:"),
 "no cut pass":rep("if prev is None or cut or dt <= 0.0 or left is None or left <= dt:","if prev is None or dt <= 0.0:\n            return out\n        if left is None or left<=dt:\n            left=dt\n        if False:"),
 "no left cap in on_land":rep("min(k, BLEND_LAND_TURN * left / gap) if gap > 1e-6 else k","k"),
 "no ease-out (k=ease-in only)":rep("k = min(ramp(s_, dr.spherical(tr.a[0])[1]), ramp(1.0 - s_, dr.spherical(target_pose[0])[1]))","k = ramp(s_, dr.spherical(tr.a[0])[1])"),
 "no height term (share only)":rep("(le - math.log(eye + dr.H0)) / BLEND_LAND_EASE[1])","-1.0)"),
 "accent dropped":rep("return en.accent(out, drive) if drive is not None else out\n\n    def turn_limited","return out\n\n    def turn_limited"),
 "keep off (BLEND_LAND=0)":rep("BLEND_LAND = 0.35","BLEND_LAND = 0.0 "),
 "no BLEND_TURN_MAX cap":rep("        allowed = min(allowed, max(own,","        allowed = min(allowed, 1e9+max(own,"),
}
for name,s in V.items():
    m=mod(s,"v"); G["pc"]=m
    row=[]; fails=[]
    for cname,targets,prog,seconds,dark_max,turn_max in G["CASES"]:
        try:
            dark,turn,end,cut=G["run"](targets,prog,seconds)
        except Exception as ex:
            row.append("ERR %r"%ex); fails.append(cname); continue
        f=[n for n,ok in (("dark",dark<=dark_max),("turn",turn<=turn_max),("end",end<=0.5),("cut",cut<=1e-4)) if not ok]
        row.append("%.1f/%.1f/%.2f/%.2g%s"%(dark,turn,end,cut,"!"+",".join(f) if f else ""))
        if f: fails.append(cname)
    print("%-30s %s  => %s"%(name," | ".join(row),"FAILS %d"%len(fails) if fails else "passes"))
