# Planet: fixes waiting for round 3 (commit b16e1b4, not grabbed yet)

- CAM_3 day/sunset e0: it had picked a 330 m hill (the lowest horizon toward the moon). It now stands within 20 m of the pyramids' level and frames them under the sky.
- CAM_10 low-flat patches: view rays under the near water met the land's mirror copy kilometres away (a radial mirror on a sphere is only a mirror nearby). The mirror copy now shows only within 1.8 km of the camera.
- CAM_4 notches: at LOD borders, stitching moved border vertices down onto coarse edges but kept their own water level (34 m over the new ground), drawing a wet slab with a neon outline. The water level and depth are now stitched with the position. Water uses the land's LOD levels, and rivers fade out 1.3 to 1.8 km from a set's anchor.
- CAM_1 fog: per-shot fog strength (rt_fog_k), CAM_1 at 6x with a 150 m clear zone. EEVEE froxels within about 150 m of the camera do not hold the sky mask; a 45 m zone veiled the night sky.
- M1: the first cut after 170 s on CAM_SYS_MOON into CAM_1 now takes 37 ms (was 90). A follow-on sweep through CAM_2, 6, 7, 8, 9, 10 and 0 stayed at or under 48 ms. A keep-alive (unhiding inactive sets off-camera) was tried and made cuts worse (up to 1.2 s frames), so it is not used.
