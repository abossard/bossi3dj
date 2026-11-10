"""Zero-copy Syphon output of the camera-view 3D viewport for synthwave_pyramids.blend.

Started by synthwave_runtime.start_syphon(); run it again to replace the
previous instance. It publishes the Syphon server CAM_OUT ("CAM_OUT - Blender"
in Magic) at 1920x1080 with the viewport compositor (bloom) and colour
management included, and never reads pixels back to the CPU:

- a SpaceView3D POST_PIXEL draw handler redraws the viewport's render texture
  (after the compositor, scene linear) into a private 1920x1080 offscreen
  through Blender's own display transform, cropped to the camera frame. That is
  GPU_viewport_draw_to_screen_ex, the function Blender uses to put a viewport
  on screen, called through ctypes: the Python gpu API has no blit, and the
  framebuffer Python draw handlers see is the empty overlay buffer;
- the offscreen's Metal texture (MTLTexture::get_metal_handle) is handed to
  Syphon on Blender's own Metal command queue, so the copy into the shared
  IOSurface runs on the GPU in order with the frame.

Needs the Metal backend on macOS (Blender 5.2 arm64; symbols resolved from the
running binary, start() raises when one is missing) and syphon-python, PyObjC.

Preview for the web page (synthwave_web.py): only while someone asked for it
in the last PREVIEW_IDLE seconds (driver_namespace[PREVIEW_WANTED] holds that
time), the same frame is also drawn into a small offscreen and read back at
PREVIEW_FPS as a bottom-up 24-bit BMP in driver_namespace[PREVIEW_KEY]. That
readback is the only GPU to CPU copy here, and it costs nothing when no page shows it.
"""
import ctypes
import struct
import time
import traceback

import bpy
import gpu
import numpy as np
import objc
from bpy_extras import view3d_utils
from mathutils import Matrix
from syphon.server import SyphonMetalServer

SERVER = "CAM_OUT"
SIZE = (1920, 1080)
FLIPPED = False        # Syphon flips the copy when True; row 0 of the shared frame must be the ground for GL receivers (Magic)
REGISTRY_KEY = "syphon_out"
PIXEL_OFS = 0.375      # GLA_PIXEL_OFS, the half-pixel setup of Blender's own viewport blit
PREVIEW_SIZE = (640, 360)
PREVIEW_FPS = 10.0
PREVIEW_IDLE = 2.0     # s after the last request before the readback stops
PREVIEW_KEY, PREVIEW_WANTED = "syphon_preview", "syphon_preview_wanted"


class Rcti(ctypes.Structure):
    _fields_ = [("xmin", ctypes.c_int), ("xmax", ctypes.c_int), ("ymin", ctypes.c_int), ("ymax", ctypes.c_int)]


def native():
    """Entry points of the running Blender (C++ names from `nm` of the 5.2 arm64 binary)."""
    lib, P = ctypes.CDLL(None), ctypes.c_void_p

    def fn(name, restype, *argtypes):
        f = lib[name]
        f.restype, f.argtypes = restype, argtypes
        return f

    return {
        "bound_viewport": fn("_ZN7blender33WM_draw_region_get_bound_viewportEPNS_7ARegionE", P, P),
        "draw_viewport": fn("_ZN7blender30GPU_viewport_draw_to_screen_exEPNS_11GPUViewportEiPKNS_4rctiEbb",
                            None, P, ctypes.c_int, ctypes.POINTER(Rcti), ctypes.c_bool, ctypes.c_bool),
        "metal_handle": fn("_ZN7blender3gpu10MTLTexture16get_metal_handleEv", P, P),
        "tex_width": fn("_ZN7blender17GPU_texture_widthEPKNS_3gpu7TextureE", ctypes.c_int, P),
        "tex_height": fn("_ZN7blender18GPU_texture_heightEPKNS_3gpu7TextureE", ctypes.c_int, P),
        "flush": fn("_ZN7blender9GPU_flushEv", None),
        "queue": P.in_dll(lib, "_ZN16GHOST_ContextMTL25s_sharedMetalCommandQueueE"),   # static id<MTLCommandQueue>
    }


def c_pointer(py_obj):
    """The C pointer a gpu.types wrapper stores right after PyObject_HEAD."""
    return ctypes.c_void_p.from_address(id(py_obj) + 16).value


def metal_texture(lib, offscreen):
    tex = offscreen.texture_color
    ptr = c_pointer(tex)
    if not ptr or ptr % 8 or (lib["tex_width"](ptr), lib["tex_height"](ptr)) != (tex.width, tex.height):
        raise RuntimeError("GPUTexture layout mismatch, not using the Metal handle")
    handle = lib["metal_handle"](ptr)
    if not handle:
        raise RuntimeError("offscreen texture has no Metal handle")
    return objc.objc_object(c_void_p=ctypes.c_void_p(handle))


def camera_rect(context):
    """Camera frame in region pixels (x, y, w, h), lower-left origin."""
    region, rv3d, space = context.region, context.region_data, context.space_data
    cam = space.camera if space.use_local_camera and space.camera else context.scene.camera
    if cam is None:
        return None
    cam = cam.evaluated_get(context.evaluated_depsgraph_get())   # drivers on lens and shift move the frame
    # the frame's corners 10 km out along their rays: at the view frame's own half metre, single precision far from
    # the origin (a camera 100 km out) put the crop a few pixels off, a dark strip along the frame's edges
    pts = [view3d_utils.location_3d_to_region_2d(region, rv3d, cam.matrix_world @ (v * 10000.0))
           for v in cam.data.view_frame(scene=context.scene)]
    if any(p is None for p in pts):
        return None
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    x0, y0 = round(min(xs)), round(min(ys))
    return x0, y0, round(max(xs)) - x0, round(max(ys)) - y0


def crop_projection(x, y, w, h):
    """Ortho that maps region texels x..x+w, y..y+h onto the whole offscreen.
    With Blender's half-pixel offset a 1920x1080 frame copies texel for texel."""
    l, b = x - PIXEL_OFS, y - PIXEL_OFS
    r, t = l + w, b + h
    return Matrix(((2.0 / (r - l), 0.0, 0.0, -(r + l) / (r - l)),
                   (0.0, 2.0 / (t - b), 0.0, -(t + b) / (t - b)),
                   (0.0, 0.0, -1.0, 0.0),
                   (0.0, 0.0, 0.0, 1.0)))


class Sender:
    def __init__(self):
        self.lib = native()
        queue = objc.objc_object(c_void_p=self.lib["queue"])
        self.server = SyphonMetalServer(SERVER, queue.device(), queue)
        self.offscreen = None    # needs a GPU context, so it is made in the first draw
        self.texture = None
        self.rect = None         # last camera frame in region pixels
        self.frames = 0
        self.failed = False
        self.small = None        # preview offscreen, made on the first preview request
        self.preview_t = 0.0
        self.handle = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), "WINDOW", "POST_PIXEL")

    def draw(self):
        if bpy.app.driver_namespace.get(REGISTRY_KEY) is not self:   # orphan after a file load
            bpy.app.timers.register(self.close)
            return
        context = bpy.context
        if self.failed or context.region_data is None or context.region_data.view_perspective != "CAMERA":
            return
        viewport = self.lib["bound_viewport"](context.region.as_pointer())
        rect = camera_rect(context) if viewport else None
        if rect is None or rect[2] <= 0 or rect[3] <= 0:
            return
        self.rect = rect
        try:
            if self.offscreen is None:
                self.offscreen = gpu.types.GPUOffScreen(*SIZE, format="RGBA8")
                self.texture = metal_texture(self.lib, self.offscreen)
            self.composite(self.offscreen, viewport, context.region, rect)
            self.publish()
            self.frames += 1
            now = time.time()
            if now - bpy.app.driver_namespace.get(PREVIEW_WANTED, 0.0) < PREVIEW_IDLE and now - self.preview_t >= 1.0 / PREVIEW_FPS:
                self.preview_t = now
                self.preview(viewport, context.region, rect)
        except Exception:
            self.failed = True
            traceback.print_exc()

    def preview(self, viewport, region, rect):
        if self.small is None:
            self.small = gpu.types.GPUOffScreen(*PREVIEW_SIZE, format="RGBA8")
        self.composite(self.small, viewport, region, rect)
        rgba = np.asarray(self.small.texture_color.read())   # rows bottom-up, the order BMP stores them in
        w, h = PREVIEW_SIZE
        pixels = rgba[:, :, 2::-1].tobytes()                 # BGR; w * 3 is a multiple of 4, so no row padding
        header = b"BM" + struct.pack("<IHHI", 54 + len(pixels), 0, 0, 54) + struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(pixels), 2835, 2835, 0, 0)
        bpy.app.driver_namespace[PREVIEW_KEY] = header + pixels

    def composite(self, target, viewport, region, rect):
        # Draw the viewport texture at the origin, as on screen, under a projection that crops to the camera frame.
        bounds = Rcti(0, region.width - 1, 0, region.height - 1)
        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        with target.bind(), gpu.matrix.push_pop(), gpu.matrix.push_pop_projection():
            gpu.matrix.load_identity()
            gpu.matrix.load_projection_matrix(crop_projection(*rect))
            self.lib["draw_viewport"](viewport, 0, ctypes.byref(bounds), True, False)   # display transform, no overlays

    def publish(self):
        self.lib["flush"]()   # submit Blender's command buffer, so the copy below runs after this frame's draw
        cb = self.server.command_queue.commandBuffer()
        self.server.publish_frame_texture(self.texture, region=(0, 0, *SIZE), size=SIZE, is_flipped=FLIPPED,
                                          command_buffer=cb, auto_commit=False)
        cb.commit()

    def close(self):
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            self.handle = None
        if self.server is not None:
            self.server.stop()
            self.server = None
        self.texture = None
        for name in ("offscreen", "small"):
            off = getattr(self, name)
            if off is not None:
                try:
                    off.free()
                except Exception as e:
                    print("syphon_out: %s not freed: %s" % (name, e))
                setattr(self, name, None)


def start():
    old = bpy.app.driver_namespace.pop(REGISTRY_KEY, None)
    if old is not None:
        old.close()
    sender = Sender()
    bpy.app.driver_namespace[REGISTRY_KEY] = sender
    print("syphon_out: publishing %s %dx%d from the camera view" % (SERVER, *SIZE))
    return sender


if __name__ == "__main__":
    start()
