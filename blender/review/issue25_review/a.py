exec(open(__file__.rsplit("/",1)[0]+"/sim.py").read())
# 1 fall from space
run([(0,"vantage","planet",1.0,30.0),(20,"orbit","river",0.3,30.0)],60,"space -> orbit river",2.0)
# 2 change of mind mid-blend
run([(0,"orbit","coast",0.3,30.0),(5,"orbit","sun",0.3,30.0),(5+8,"rise","lake",0.3,30.0)],45,"change of mind",1.0)
# 3 cut mid-blend
run([(0,"orbit","coast",0.3,30.0),(5,"follow","sun",0.3,30.0),(5+10,"vantage","moon",0.3,0.0)],20,"cut mid-blend",0.25)
