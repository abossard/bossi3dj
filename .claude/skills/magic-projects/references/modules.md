# Scenes and modules (Magic 3.0b6)

Source tags: (saved file) = Magic's bundled `SampleProjects/*.magic`, (module file) = `Contents/MacOS/Modules`, `Modules2`, (guide) = User's Guide. File format, ids, sources, modifiers and Internals indexes are in [format.md](format.md); not repeated here.

## Contents
- Scenes, scene modules, SceneInput
- Scene groups, tabs, post-processing
- Pins, chains and connection order
- 3D vs 2D, coordinates, Preview
- Included modules by category
- Iterator
- ISF, GLSL and FFGL
- Additional Module Folders
- ISF AI Prompt Window

## Scenes, scene modules, SceneInput

- A scene is a set of modules ending in the Magic module. Every module must reach Magic, directly or not, to be drawn (guide).
- Numbering starts at 0 everywhere (guide).
- `Scene` attrs seen: `name`, `id`, `isPostProcessing`, `excludedFromPostProcessing`, `keepInGfxMem` (saved file). `keepInGfxMem` matches the tab option Keep Scene In Graphics Memory, ignored when Load All Scenes Into Graphics Memory is on (guide).
- Powering off the Magic module disables the whole scene (guide).
- Scene module: draws another scene inside this one. It behaves like any module, so Translate etc. apply to it (guide).
- Scene module node carries `Bypass` and `Power` even when it has no inputs (saved file, `SceneModulesExample`).
- One scene module output can feed many parents: `FullGrid` sends `TwoRows` into five Translates, which feed one RotateAxis (saved file). Scenes nest: FullGrid > TwoRows > OneRow > LeftRight (saved file).
- A shared source scene: `Effects2DExamples` draws one `Video source` scene (a VideoFile) through a scene module in every example scene (saved file).
- Self-reference at any depth is not drawn; this prevents infinite loops (guide).
- SceneInput: turns a scene into an effect. Each SceneInput in the scene becomes one input pin on its scene module, top to bottom (guide).
- XML: `Node pluginName="SceneInput" sceneInputID="1"`, no children, only a `Power` param (saved file, `SceneInputExample`). Both SceneInputs there have `sceneInputID="1"`, equal to the id of the scene they sit in ("My Effects").
- In `SceneInputExample`, scene module `My Effects` has `Child 917` (Waveform) then `Child 918` (Starfield). Waveform goes through SceneInput 921 > RadialBlur, Starfield through SceneInput 922 > ColorHSB (saved file). So child order = SceneInput order in the scene's `Nodes`.
- Scene changes restart modules unless Ignore Restart is set on the module (guide). 436 of 970 sample nodes carry `dontRestart="0"` (saved file); the name matches that option.

## Scene groups, tabs, post-processing

- Scene groups are organisation only. They have no effect on output; every scene stays reachable from Playlist and Scene modules (guide).
- XML `SceneTreeItems`: nested `SceneTreeItem`. `group="1"` is a group with `name` and `expanded`; `group="0"` is a scene, `id` = `Scene@id` (saved file, `SceneGroupsExample`).
- Group ids and scene ids are separate number spaces: group `id="2"` and scene `id="2"` coexist (saved file).
- Ungrouped scenes are top-level `SceneTreeItem group="0"` entries (saved file).
- Closing a tab only hides the scene; Remove Scene deletes it (guide). `TabsVisible/TabVis sceneID` lists open tabs (saved file; meaning inferred from guide).
- Post-processing scene: Scene > Add/Update Post-Processing Scene adds a scene "Post-Processing" and inserts its scene module before the Magic module in every scene. Re-run it after changes. Tab option Exclude Scene From Post-Processing skips a scene (guide).
- No bundled sample has `isPostProcessing="1"` (saved file).

## Pins, chains and connection order

- Output pin on the right, inputs on the left. Generators (Polygon, ImageFile) have only an output; modifiers (ColorRGB, Scale) have both; Magic has only inputs (guide).
- One output can feed many inputs; the source is drawn once per path. Cheaper than duplicating the module (guide).
- Ordinary modules: all inputs are composited into one input before processing. Top pin = top layer, drawn in front (guide).
- In XML, first `Child` = top pin (see format.md). `Kaleidoscope` in `MIDIFileExample` has 4 children, `RotateAxis` in `SceneModulesExample` has 5 (saved file).
- Layers modules use independent inputs: top pin is input 1, next pin input 2. Extra inputs beyond what a module uses are generally not drawn (guide).
- Many FFGL plugins, ISF files and some GLSLShader shaders also use independent inputs (guide).
- Layers in `LayersExamples` (saved file):
  - Mask: child 1 VideoFile, child 2 `circle.png`. The video is cut to the circle.
  - Blend: child 1 `donut.png`, child 2 VideoFile, `Mode 8`.
  - Mix: child 1 VideoFile, child 2 Starfield, `Amount` linked to a Sine modifier.
  - InputSelector: 4 ColorHSB>ImageFile chains, `Input #` from `Ramp 0.2 > Scale 4`.
- Inserting a chain: a selected chain without forks can be inserted into a connector (Insert Selection, Insert Paste) (guide).
- Connect Sequentially (Cmd+W), Many To One (Cmd+K), One To Many (Shift+Cmd+K) (guide).
- Power off disables the module and everything feeding it. Bypass disables only that module; modules without inputs have no bypass (guide). No-input modules saved without `Bypass`: Polygon, Text, Fractal, Image, Model, VideoFile, VideoCapture, Waveform, Spectrum. Starfield has an input and a `Bypass` (saved file).
- DepthTest: inputs intersect in 3D instead of stacking by pin order. No params besides Bypass/Power (guide, saved file `DepthTestExample`: DepthTest over a rotated Polygon and a rotated Model).

## 3D vs 2D, coordinates, Preview

- Every module works in 3D space, but pixel-level modules output a flat 2D plane. Any output can still be rotated, scaled, translated (guide).
- Color and Transforms preserve 3D input; Geometry modules draw in 3D space (guide).
- Flat 2D output: all Effects2D, GLSLShader, ISFShader, Fractal. Media modules are 2D, scaled to the output height (guide).
- Use Effects2D as post-processing after the 3D geometry is drawn (guide).
- Coordinates: y is always -1..1, scaled to output height; x edge = aspect ratio (1.777 at the default 1280x720) (guide). Live numbers in format.md.
- Preview Window (Shift+Cmd+E): shows a second scene, never affects the Magic Window. Can cost up to 50% frame rate (guide).
- Preview Only vs Preview & Edit (also switches the editor) (guide).
- Preview Mode (Scene > Preview Mode): tab and group clicks go to the Preview Window; only the Playlist changes the Magic Window (guide).
- Preview Here (Cmd+J) shows one module's output; title bar shows "P" (guide).
- Cmd-click a tab edits a scene without showing it (guide).

## Included modules by category

Native modules are `.dylib`; ISF ones are `.fs` (module file). The exact Magic 3 param names and defaults of every bundled module are in `magic/magic_modules_v3.json`, written by Magic 3.0b6 itself (`magicproj catalog --plugin NAME`); the params below are a summary. Magic fills in any param a generated file leaves out (verified: a project with 221 bare modules saved back complete). Every module has `Power`; modules with an input add `Bypass`.

Color (preserve 3D) (guide; params saved file)
- ColorRGB: applies RGBA color. `Red Green Blue Alpha` (0..1), `Override` (ignore other color modules in the chain), `Additive` (3.0: additive vs traditional blending). Old saves also carry `Premultiply`, which Magic 3 drops.
- ColorHSB: applies HSBA color. `Hue` (0 red, .333 green, .666 blue), `Saturation`, `Brightness`, `Alpha`, `Override`, `Additive`. Old saves' `Set`/`Premultiply` are dropped by Magic 3.

Effects2D (flat output; `.fs` except Trails and Resolution) (module file; descriptions from headers)
- Array: copies input in x/y. `X Amount`, `X Distance`, `Y Amount`, `Y Distance`.
- ChromaKeyFast: alpha by key color. `Strength`, `Falloff`, `Color` (0 Green, 1 Blue).
- Contrast: `Contrast`, `Brightness` (-1..1, 0 = no change).
- HueSaturation: `Hue` (circular), `Saturation`, `Lightness`.
- Invert: 1-rgb. `Invert Alpha`.
- Kaleidoscope: mirror slices. `Iterations`, `Zoom`, `Rotation`, `Fill Edges`.
- LumaKey: alpha by luminance. `Strength`, `Falloff`, `Invert`.
- NoiseBlur: grainy directional blur. `Amount`, `Angle`.
- Pixelate: `Amount`. Posterize: `Amount`. Transparency: `Amount`.
- RadialBlur: zoom blur. `Distance`, `Density`.
- Resolution (dylib): resize input to pixels, optional rescale to output height. `Width`, `Height`, `Scale` (guide).
- Trails (dylib): motion trails via alpha. `Strength`, `Blur`, `Blur Radius`, `Speed`, `Z/X` (guide, saved file). Strength depends on frame rate (guide).

Geometry (3D space) (guide; params saved file where used)
- DepthTest: depth-sorted intersection of inputs.
- Lissajous (new in 3.0): plots two audio channels against each other. `Source 0`, `Source 1`.
- Model: 3D model file (AssImp). `File`, `Reload`, `Center`, `Scale`, `Colorize`, `Wireframe`, `3-Light`, `Global Light`, `L. Azimuth`, `L. Elevation`, `L. Intensity`.
- Polygon: 2D polygon. `Sides`, `Fit`.
- SineWave: `Frequency` (0..512), `Phase`, `Solid`, `Fit Width` (3.0).
- Spectrum: audio spectrum. `Source`, `Bars`, `Threshold` (dB), `Log X Scale`, `Log Y Scale`, `Rounded`, `Smoothness`, `Start At 0`, `Fit Width`.
- Starfield: moving stars; a connected input becomes the star image. `Speed`, `Size`, `Circles`, `Stars/sec`, `Distance`, `Spread`. Max 5000 stars.
- Waveform: audio waveform. `Source`, `Solid`, `Line Width`, `Circle`, `Overwrite`, `Fit Width`. Draws nothing for MIDI/OSC sources.

Layers (independent inputs) (guide; Blend, Mask, Mix are `.fs`, module file)
- Blend: input 1 blended with input 2. `Mode` VALUES 1..28: 1 Lighten, 2 Darken, 3 Multiply, 4 Average, 5 Add, 6 Subtract, 7 Difference, 8 Negation, 9 Exclusion, 10 Screen, 11 Overlay, 12 Soft Light, 13 Hard Light, 14 Color Dodge, 15 Color Burn, 16 Linear Dodge, 17 Linear Burn, 18 Linear Light, 19 Vivid Light, 20 Pin Light, 21 Hard Mix, 22 Reflect, 23 Glow, 24 Phoenix, 25 Hue, 26 Saturation, 27 Color, 28 Luminosity. Header `DEFAULT` is 0, outside VALUES (module file).
- Mask: alpha of input 1 from input 2. `Use Alpha` (else color channels).
- Mix: `Amount` 0 = input 1 only, 1 = input 2 only.
- MultiMix (dylib): crossfades inputs in pin order. `Index` (0.5 = halfway 0 to 1), `Smooth`, `Repeat`.
- InputSelector (dylib): draws one input. `Input #` (0 = top), unlimited inputs.
- Null: does nothing; for annotations.

Media (2D, scaled to output height) (guide)
- ImageFile: `File`, `Reload`, `Scale`. Pre-3.0 saves call it `Image`; Magic 3 loads those and saves `ImageFile` (verified by re-saving LayersExamples).
- ImageFolder: `Folder`, `Reload`, `Cache`, `Scale`, `Looping`.
- JpegFolder: hardware JPEG folder. `Folder`, `Index`, `Play`, `FPS`, `Scene Start`, `Looping`.
- VideoCapture: webcam. `Device`, `Scale`, `Crop`, `Flip`, `Stop All`, `Start This`.
- VideoFile: FFmpeg playback, Hap best. `File`, `Speed`, `Start Time`, `End Time`, `Goto Start`, `Scene Start`, `Looping`, `Audio`, `Audio Gain`.
- VideoFolder: `Folder`, `Cur. File`, `Goto Prev/Next`, `Randomize`, `Loop Folder`. No audio.
- VideoStream: IP stream. `URL`, `Reload`, `Scale`, `Crop`.

Special (guide)
- Antialias: `Quality` (SSAA 2x, MSAA 2x-16x; MSAA keeps 3D).
- Fractal (`.fs`): Julia set. `Iterations`, `Real`, `Imaginary`, `Zoom`, `Center X`, `Center Y`.
- GLSLShader, ISFShader: see ISF section.
- Iterator: see Iterator section.
- OSCSender: see format.md. One IP and port per project; Performer edition.
- Restart: restarts modules on its input. `Restart Now`.
- SyphonClient: receives a Syphon server. `Server`; Performer edition.
- Text: `Text` (`\\` = newline), `Font`, `Align`, `Size` (% of height), `Bold`, `Italic`, `Underline`, `Line #`.
- TextFile: `.txt` file. `File`, `Reload`, `Font`, `Align`, `Size`, `Line #`.

Transforms (3D) (guide; params saved file)
- RotateAxis: `Axis` (`X-Axis`/`Y-Axis`/`Z-Axis`), `Angle` in rotations. Saved with empty `Bypass`/`Power` values in samples (saved file).
- RotateVector: `Angle` in rotations around the line origin to `X Y Z`.
- Scale: `X Y Z`, `X For All` (X drives all axes).
- Translate: `X Y Z`.

Modules2 (Vidvox ISF pack, "Blur to v002" in the menu) (guide): 173 `.fs` in 14 folders (module file): Blur 8, Color Adjustment 11, Color Effect 21, Distortion Effect 15, Film 3, Generator 21, Geometry Adjustment 15, Glitch 17, Halftone Effect 8, Masking 6, Sharpen 3, Stylize 31, Tile Effect 5, v002 9.
- Generator `.fs` have no image input (module file).
- Two image inputs: Layer Mask, Color Relookup, Glitch Shifter, Trail Mask, v002 Light Leak (module file).
- Audio inputs: FFT Color Lines, FFT Filled Waveform, FFT Spectrogram (module file).
- Name clashes: `Kaleidoscope` and `Posterize` exist in both Effects2D and Stylize (module file). A node stores only the name.

## Iterator

- Draws its input `Iterations` times. `Offset` shifts the start: 10 iterations at offset 5 run 5..14 (guide).
- Params inside the chain below the Iterator are evaluated per iteration. Link a param to Internals `Iteration #` (guide).
- XML of an `Iteration #` link (saved file, `IteratorBasicExamples`):
  `<InputValue name="Sides" linked="1" layerID="2147483645" feature="7" subFeature="0" value="4">` + Offset modifier `type="2" param="3"`.
- Only Internals feature 7 appears in the samples (saved file). Total Iterations (feature 8) is in format.md, unused there.
- Sample convention: a manual Global `iters` drives `Iterations` (`layerID="2147483646" feature=<iters id>`) and expressions normalise, e.g. `Expression(x/iters)`, `Expression(1.5*x/iters)` (saved file: IteratorBasic, IteratorCube, IteratorSpectrum, StereoSpectrum_30Band).
- Typical uses (saved file):
  - Grid: Translate X = `Iteration # Scale 0.3`, Polygon Sides = `Iteration # Offset 3`.
  - Nested: Iterator(4) > Translate X > Iterator(3) > Translate Y gives a 4x3 grid. A param follows the nearest Iterator below Magic, i.e. the closest one on its output side (saved file, `Shapes` scene; "nearest" from guide).
  - Pick a source per iteration: InputSelector `Input #` = `Iteration #` (`Image Inputs` scene; MIDIPiano maps notes to 13 key scenes with `Expression(... x%12)`).
  - Scatter: `Iteration # > RandomTrigger 0.5 > Scale 2 > Offset -1` for x/y/z (Particles, IteratorCube).
  - Piano: `Iterations 88`, `Offset 21` = MIDI notes 21..108 (MIDIPiano).
- One Iterator can take several children; each chain is iterated (StereoSpectrum_30Band: left and right chains) (saved file).
- Iterator Freqs.: audio Freq. Range split automatically across the nearest Iterator's iterations (guide). XML `feature="1" subFeature="6"` on an audio `Layer` (saved file). Used for bar heights, hue, brightness.
- Iterator Notes: MIDI velocity of the note = current iteration number (guide). MIDIPiano links Power/Bypass to MIDI `feature="10"` under such an Iterator (saved file); feature 10 = Iterator Notes is inferred.
- Iteration # is not available for Globals (guide).

## ISF, GLSL and FFGL

- Built-in ISF: Effects2D and Layers `.fs`, `Special/Fractal.fs`, all of Modules2 (module file). Guide says "over 200"; the folders hold 189 `.fs` (module file).
- ISF in a project is referenced by `pluginName` = file stem only. No sample node has a path attribute or `isfFilename` (saved file).
- Old saves keep stale params: sample Kaleidoscope nodes have `Iterations`, `Corners`; the current `.fs` has `Iterations Zoom Rotation Fill Edges` (saved file, module file).
- Param naming rules and the `catalog` command: format.md.
- Image inputs in header order map to pins top to bottom: `inputImage`, then `inputImage2`/`maskImage` (module file Mask.fs; "first input" from guide).
- Magic adds `Speed` to time-dependent ISF modules and `Overwrite` to ISF modules with audio input (guide).
- ISF module menu: Open In Text Editor, Reload, Reload All, Modify With AI Prompt (guide).
- Custom ISF: either put the folder in Additional Module Folders (appears as a module), or load the `.fs` into an ISFShader module (guide).
- ISFShader: `File`; after loading, File disappears and the ISF params show. Has an input pin by default (guide). No sample uses it (saved file).
- GLSLShader: GLSL Sandbox/Shadertoy style fragment shader in a `.txt`. `File`, `Reload`, `Speed`, `X/Y/Z/W Param` (feed `mouse`) (guide).
- Saved `File` is relative to the project with Windows separators: `..\Modules\Special\GLSLShaders\default.txt` (saved file, `GLSLShaderExample`).
- 67 bundled shaders in `Modules/Special/GLSLShaders`; they use `uniform float time`, `vec2 resolution`, `vec2 mouse`; two use a backbuffer sampler (module file).
- Load Default Module Files (Scene Editor Options) auto-loads `default.txt` in new GLSLShader modules (guide).
- FFGL: Performer edition only. Add the plugin's parent folder to Additional Module Folders; keep its extra libraries in the same folder (guide).

## Additional Module Folders

- Help > Additional Module Folders. Scanned with subfolders after a restart; subfolders become submenus; list order = menu order (guide).
- Folders added in v3 default to "V3+ Only" (guide).
- Stored in `~/Library/Application Support/MAGIC/MAGIC_1_0.xml` as `<VALUE name="addtlModuleFolders"><addtlModuleFolders><file name="/abs/path" disabled="0"/>...`. Read only that element. The file holds other secrets; never write it, never print other values.
- `magicproj catalog` reads this list and adds those `.fs` files.

## ISF AI Prompt Window

- Window > ISF AI Prompt Window (Shift+Cmd+U). Generates or edits ISF modules with Claude, GPT or Gemini; pay-per-prompt credits; key set via Help > ISF AI Prompt Key (guide).
- No module selected: generates a new module wired to Magic. Module selected: edits it, keeping param values and modifiers (guide).
- Names increment per prompt unless Increment ISF AI Module Names is off; Edit > Rename works only for ISF modules (guide).
- Files go to the user temp folder (or Help > ISF AI Prompt Download Folder) and are copied into the project folder on save. Prompt history, model and cost are appended as comments in the `.fs` (guide).

## All bundled modules (Magic 3.0b6)

From `magic_modules_v3.json`. Modules without `Bypass` (no input pin): Checkerboard, Color Bars, Color Schemes, Color Test Grid, FFT Color Lines, FFT Filled Waveform, FFT Spectrogram, Fractal, Heart, ImageFile, ImageFolder, JpegFolder, Life, Linear Gradient, Lines, Lissajous, Model, Noise, OSCSender, Polygon, Radial Gradient, Random Lines, Random Shape, Sine Warp Gradient, SineWave, Solid Color, Spectrum, Spiral, Star, Stripes, SyphonClient, Text, TextFile, Triangle, VideoCapture, VideoFile, VideoFolder, VideoStream, Waveform.

- Modules/Color: ColorHSB, ColorRGB
- Modules/Effects2D: Array, ChromaKeyFast, Contrast, HueSaturation, Invert, Kaleidoscope, LumaKey, NoiseBlur, Pixelate, Posterize, RadialBlur, Resolution, Trails, Transparency
- Modules/Geometry: DepthTest, Lissajous, Model, Polygon, SineWave, Spectrum, Starfield, Waveform
- Modules/Layers: Blend, InputSelector, Mask, Mix, MultiMix, Null
- Modules/Media: ImageFile, ImageFolder, JpegFolder, VideoCapture, VideoFile, VideoFolder, VideoStream
- Modules/Special: Antialias, Fractal, GLSLShader, ISFShader, Iterator, OSCSender, Restart, SyphonClient, Text, TextFile
- Modules/Transforms: RotateAxis, RotateVector, Scale, Translate
- Modules2/Blur: Diagonal Blur, Edge Blur, Fast Blur, Hatch Blur, Median, Multi Pass Gaussian Blur, Soft Blur, VVMotionBlur 3.0
- Modules2/Color Adjustment: Apply Alpha, Auto Levels, Bright, Color Controls, Color Levels, Exposure Adjust, Gamma Correction, RGBA Swap, Set Alpha, Vibrance, White Point Adjust
- Modules2/Color Effect: Auto Color Tone, Channel Slide, Color Invert, Color Monochrome, Color Posterize, Color Replacement, Duotone, False Color, Layer Mask, Luminance Posterize, Maximum Component, Minimum Component, Motion Heat Map, Multi Hue Shift, RGB EQ, RGB Invert, RGB Strobe, RGB Trails 3.0, Sepia Tone, Strobe, Trio Tone
- Modules2/Distortion Effect: Bump Distortion, Circle Splash Distortion, Circle Wrap Distortion, Cubic Warp, Edge Distort, Frosted Glass, Interlace Mirror, Optical Flow Distort, Ripples, Shockwave, Shockwave Pulse, Trapezoid Distortion, Twirl, XYZoom, Zoom
- Modules2/Film: Ghosting, Interlace, Lens Flare
- Modules2/Generator: Checkerboard, Color Bars, Color Schemes, Color Test Grid, FFT Color Lines, FFT Filled Waveform, FFT Spectrogram, Heart, Life, Linear Gradient, Lines, Noise, Radial Gradient, Random Lines, Random Shape, Sine Warp Gradient, Solid Color, Spiral, Star, Stripes, Triangle
- Modules2/Geometry Adjustment: 3d Rotate, Collage, Deinterlace, Dual Side Scroller And Flip, Flip H, Flip V, HorizVertHold, Layer Position, Mirror, Radial Replicate, Replicate, Rotate, Shake, Side Scroller And Flip, Sphere Map
- Modules2/Glitch: Bad TV, Color Relookup, Convergence, Echo Trace, FastMosh, Freeze Frame, Glitch Shifter, HSVtoRGB, Micro Buffer, Micro Buffer RGB, Pixel Shifter, RGBtoHSV, Replicate Random, Slit Scan, Solarize, Time Glitch RGB, Vertex Manipulator
- Modules2/Halftone Effect: CMYK Halftone, CMYK Halftone-Lookaround, Circular Screen, Dither-Bayer, Dot Screen, Line Screen, RGB Halftone, RGB Halftone-lookaround
- Modules2/Masking: Chroma Desaturation Mask, Chroma Mask, Motion Mask, Optical Flow Generator, Shape Mask, Trail Mask
- Modules2/Sharpen: Sharpen Luminance, Sharpen RGB, Unsharp Mask
- Modules2/Stylize: ASCII Art, Bloom, Chroma Zoom, City Lights, Diagonalize, Dilate, Dilate-Fast, Double Vision, Edge Blowout, Edges, Emboss, Erode, Erode-Fast, Gloom, Glow, Glow-Fast, God Rays, Hyperspace, MultiFrame 2x2, MultiFrame 3x3, Neon, Night Vision, Pixellate, Sketch, Thermal Camera, Toon, Triangles, VHS Glitch, Zooming Feedback
- Modules2/Tile Effect: Kaleidoscope Tile, Meta Image, Mirror Edge, Quad Tile, Sine Warp Tile
- Modules2/v002: v002 Bleach Bypass, v002 Crosshatch, v002 Dilate, v002 Erode, v002 Light Leak, v002 Technicolor, v002 Vignette, v002-CRT-Displacement, v002-CRT-Mask
