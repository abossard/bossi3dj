class_name OscDecode
## OSC 1.0 packet decoding, bundles included. Pure: bytes in, [address, args] pairs out.


static func decode(packet: PackedByteArray) -> Array:
	var out: Array = []
	_decode_into(packet, out)
	return out


static func _decode_into(p: PackedByteArray, out: Array) -> void:
	if p.size() >= 16 and _read_string(p, 0)[0] == "#bundle":
		var j := 16
		while j + 4 <= p.size():
			var size := _read_i32(p, j)
			j += 4
			if size <= 0 or j + size > p.size():
				return
			_decode_into(p.slice(j, j + size), out)
			j += size
		return
	var addr_at: Array = _read_string(p, 0)
	var address: String = addr_at[0]
	if not address.begins_with("/"):
		return
	var tags_at: Array = _read_string(p, addr_at[1])
	var tags: String = tags_at[0]
	var i: int = tags_at[1]
	var args: Array = []
	for tag in tags.substr(1):
		if "fid".contains(tag) and i + (8 if tag == "d" else 4) > p.size():
			return
		match tag:
			"f":
				args.append(_read_f32(p, i))
				i += 4
			"i":
				args.append(_read_i32(p, i))
				i += 4
			"d":
				args.append(_be(p, i, 8).decode_double(0))
				i += 8
			"s":
				var s: Array = _read_string(p, i)
				args.append(s[0])
				i = s[1]
			"T":
				args.append(true)
			"F":
				args.append(false)
			_:
				return
	out.append([address, args])


static func _be(p: PackedByteArray, at: int, n: int) -> PackedByteArray:
	var b := p.slice(at, at + n)
	b.reverse()
	return b


static func _read_i32(p: PackedByteArray, at: int) -> int:
	return _be(p, at, 4).decode_s32(0)


static func _read_f32(p: PackedByteArray, at: int) -> float:
	return _be(p, at, 4).decode_float(0)


## [string, index after its 4-byte padding]
static func _read_string(p: PackedByteArray, at: int) -> Array:
	var end := at
	while end < p.size() and p[end] != 0:
		end += 1
	var s := p.slice(at, end).get_string_from_utf8()
	return [s, (end + 4) & ~3]
