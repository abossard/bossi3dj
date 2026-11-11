"""Holds the scene clocks still while the grabber runs: drops the events in flight (quiesce), then renews the runtime's
freeze every second until DN["grabber"]["done"], so repeated grabs of a shot show the same frame. Exec after grabber.py."""
import bpy

DN = bpy.app.driver_namespace
RT = DN["vj_runtime"]
RT.quiesce()


def renew():
    st = DN.get("grabber")
    if st is None or st.get("done"):
        RT.freeze(False)
        return None
    RT.freeze(True)
    return 1.0


renew()
bpy.app.timers.register(renew, first_interval=1.0)
