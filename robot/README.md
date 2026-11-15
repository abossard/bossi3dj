# Robot Scene

A fighting Android, pre-rendered in high quality in Blender and played in Magic, with Live Layers from Blender on top. Concept stage: no Blender build yet.

- Runtime: Magic plays the Clip Library and switches Clips on audio events; a live Blender scene sends Live Layers over Syphon; Magic composites them with the Clips' Mattes.
- Blender here is a render framework: it builds the Clips, their Mattes and the Render Package that a Magic generator reads.
- Terms: [GLOSSARY.md](../GLOSSARY.md), "Robot Scene".
- Where it stands, decisions, open questions: [docs/handover/robot-orchestrator.md](../docs/handover/robot-orchestrator.md).
