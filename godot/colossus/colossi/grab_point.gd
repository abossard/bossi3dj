class_name GrabPoint
extends Marker3D
## A spot on the Colossus where the Wanderer can hold on. Local +Z is the surface normal.

enum Kind { LEDGE, FUR }

@export var links: Array[NodePath] = []
@export var kind: Kind = Kind.FUR
## The Grab Point the climb aims for; one per Colossus.
@export var head := false


func normal() -> Vector3:
	return global_transform.basis.z.normalized()


func linked() -> Array[GrabPoint]:
	var out: Array[GrabPoint] = []
	for p in links:
		var g := get_node_or_null(p) as GrabPoint
		if g:
			out.append(g)
	return out
