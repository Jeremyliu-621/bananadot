extends Control

# bananadot viewer — instantiates a Godot node for the current component type
# and wires up the state textures. Designed to live in an iframe on the
# bananadot results page.
#
# Textures are delivered via postMessage from the parent frame:
#   { kind: 'load', componentType, pixel, textures: { <state>: <dataUrl> } }
#
# On _ready(), the viewer posts { kind: 'ready' } back to the parent so the
# parent knows when it's safe to send the first load. Avoids the ready-race
# where a load is sent before viewer.gd has installed its listener.
#
# Supported types mirror backend/app/pipeline/godot.py _SPECS:
#   button       → TextureButton (normal, hover, pressed, disabled)
#   panel        → NinePatchRect (normal)
#   checkbox     → TextureButton toggle (unchecked, checked)
#   progress_bar → TextureProgressBar (empty, full)

var _widget: Control = null
var _widget_type: String = ""
var _message_cb: JavaScriptObject = null

# State-name → node-property map per component type. Keys mirror the backend's
# generated PNG filenames (<state>.png).
const _STATE_MAP := {
	"button": {
		"normal":   "texture_normal",
		"hover":    "texture_hover",
		"pressed":  "texture_pressed",
		"disabled": "texture_disabled",
	},
	"panel": {
		"normal": "texture",
	},
	"checkbox": {
		"unchecked": "texture_normal",
		"checked":   "texture_pressed",
	},
	"progress_bar": {
		"empty": "texture_under",
		"full":  "texture_progress",
	},
}


func _ready() -> void:
	_install_message_listener()
	_notify_parent_ready()


func _install_message_listener() -> void:
	if not OS.has_feature("web"):
		return
	var window := JavaScriptBridge.get_interface("window")
	if window == null:
		return
	# Must keep a reference — JavaScriptBridge callbacks are GC-sensitive.
	_message_cb = JavaScriptBridge.create_callback(_on_js_message)
	window.addEventListener("message", _message_cb)


func _notify_parent_ready() -> void:
	if not OS.has_feature("web"):
		return
	# Tell the parent frame we're ready to receive `{kind: 'load', ...}`.
	# Using targetOrigin '*' is fine — we never send sensitive data.
	JavaScriptBridge.eval(
		"window.parent && window.parent.postMessage({ kind: 'bananadot-ready' }, '*');",
		true,
	)


func _on_js_message(args: Array) -> void:
	if args.is_empty():
		return
	var event = args[0]
	var data = event.data
	if data == null:
		return
	var kind := ""
	if data.kind != null:
		kind = str(data.kind)
	if kind != "load":
		return
	var widget_type := "button"
	if data.componentType != null:
		widget_type = str(data.componentType)
	var pixel := false
	if data.pixel != null:
		pixel = int(data.pixel) == 1
	if data.textures == null:
		push_warning("bananadot viewer: load message missing `textures`")
		return
	_load_from_textures(data.textures, widget_type, pixel)


func _load_from_textures(textures: JavaScriptObject, widget_type: String, pixel: bool) -> void:
	var filter := RenderingServer.CANVAS_ITEM_TEXTURE_FILTER_NEAREST if pixel \
		else RenderingServer.CANVAS_ITEM_TEXTURE_FILTER_LINEAR
	RenderingServer.canvas_item_set_default_texture_filter(get_canvas_item(), filter)

	if widget_type != _widget_type:
		_rebuild_widget(widget_type)

	var state_map: Dictionary = _STATE_MAP.get(widget_type, _STATE_MAP["button"])
	for key in state_map.keys():
		var state_name := String(key)
		var url_v = textures[state_name]
		if url_v == null:
			continue
		var url := str(url_v)
		if url.begins_with("data:"):
			_set_from_data_url(url, String(state_map[state_name]))
		else:
			push_warning("bananadot viewer: only data: URLs are supported; got %s..." % url.substr(0, 40))


func _set_from_data_url(url: String, property_name: String) -> void:
	var comma := url.find(",")
	if comma == -1:
		push_warning("bananadot viewer: malformed data url for %s" % property_name)
		return
	var b64 := url.substr(comma + 1)
	var bytes := Marshalls.base64_to_raw(b64)
	var img := Image.new()
	if img.load_png_from_buffer(bytes) != OK:
		push_warning("bananadot viewer: could not decode data-url PNG for %s" % property_name)
		return
	var tex := ImageTexture.create_from_image(img)
	if is_instance_valid(_widget):
		_widget.set(property_name, tex)


func _rebuild_widget(widget_type: String) -> void:
	for c in get_children():
		c.queue_free()

	var container := CenterContainer.new()
	container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(container)

	match widget_type:
		"button":
			var b := TextureButton.new()
			b.ignore_texture_size = true
			b.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
			b.custom_minimum_size = Vector2(280, 280)
			container.add_child(b)
			_widget = b
		"panel":
			var p := NinePatchRect.new()
			p.custom_minimum_size = Vector2(280, 200)
			container.add_child(p)
			_widget = p
		"checkbox":
			var cb := TextureButton.new()
			cb.ignore_texture_size = true
			cb.toggle_mode = true
			cb.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
			cb.custom_minimum_size = Vector2(200, 200)
			container.add_child(cb)
			_widget = cb
		"progress_bar":
			var pb := TextureProgressBar.new()
			pb.custom_minimum_size = Vector2(280, 60)
			pb.max_value = 100.0
			pb.value = 60.0
			pb.fill_mode = TextureProgressBar.FILL_LEFT_TO_RIGHT
			container.add_child(pb)
			_widget = pb
		_:
			push_warning("bananadot viewer: unknown type %s, defaulting to button" % widget_type)
			var b := TextureButton.new()
			b.ignore_texture_size = true
			b.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
			b.custom_minimum_size = Vector2(280, 280)
			container.add_child(b)
			_widget = b
			widget_type = "button"

	_widget_type = widget_type


