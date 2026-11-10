class_name HttpLite
## Just enough HTTP/1.1 for the control page: one request per connection, answered and closed.
## Pure: bytes in, a request dictionary out; status and body in, response bytes out.

const REASONS := {
	200: "OK",
	400: "Bad Request",
	403: "Forbidden",
	404: "Not Found",
	409: "Conflict",
	413: "Payload Too Large",
	415: "Unsupported Media Type",
}


## The request in `buf` as {method, path, headers (lower-case names), body}, or {} while it is
## still incomplete (no blank line yet, or fewer body bytes than Content-Length).
static func parse(buf: PackedByteArray) -> Dictionary:
	var end := _header_end(buf)
	if end < 0:
		return {}
	var lines := buf.slice(0, end).get_string_from_utf8().split("\r\n")
	var first := lines[0].split(" ")
	var headers := {}
	for i in range(1, lines.size()):
		var colon := lines[i].find(":")
		if colon > 0:
			headers[lines[i].substr(0, colon).strip_edges().to_lower()] = (
				lines[i].substr(colon + 1).strip_edges()
			)
	var length := int(headers.get("content-length", "0"))
	if buf.size() < end + 4 + length:
		return {}
	return {
		"method": first[0],
		"path": first[1].split("?")[0] if first.size() > 1 else "",
		"headers": headers,
		"body": buf.slice(end + 4, end + 4 + length).get_string_from_utf8(),
	}


static func response(status: int, content_type: String, body: PackedByteArray) -> PackedByteArray:
	var head := (
		"HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
		% [status, REASONS.get(status, "Error"), content_type, body.size()]
	)
	head += "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
	var out := head.to_utf8_buffer()
	out.append_array(body)
	return out


static func json(status: int, data: Variant) -> PackedByteArray:
	return response(status, "application/json", JSON.stringify(data).to_utf8_buffer())


## Index of the blank line that ends the header, -1 when it has not arrived.
static func _header_end(buf: PackedByteArray) -> int:
	for i in range(0, buf.size() - 3):
		if buf[i] == 13 and buf[i + 1] == 10 and buf[i + 2] == 13 and buf[i + 3] == 10:
			return i
	return -1
