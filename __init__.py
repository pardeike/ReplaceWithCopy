# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Andreas Pardeike

# pyright: reportInvalidTypeForm=false

from .manifest import parse_manifest
from .menu_injector import register_menu_item, unregister_menu_item
bl_info = parse_manifest({"location": "3D View > Object (menu)", "category": "Object"})

import bpy
import sys
from dataclasses import dataclass

if sys.platform.startswith("win"):
    import ctypes  # type: ignore[import-not-found]
    _VK_MENU = 0x12

    def _system_alt_state() -> bool | None:
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(_VK_MENU) & 0x8000)
        except Exception:
            return None
else:
    def _system_alt_state() -> bool | None:
        return None


_ALT_KEY_STATE = False
_ALT_TIMER_RUNNING = False
_SELECTION_HISTORY: list[str] = []
_OPERATOR_PROPS_ID = "OBJECT_OT_replace_with_copy"
_USE_ACTIVE_DEFAULT = False


def _tag_all_areas():
    wm = None
    try:
        wm = bpy.context.window_manager  # type: ignore[attr-defined]
    except Exception:
        wm = None
    if wm is None:
        return
    for window in wm.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in screen.areas:
            try:
                area.tag_redraw()
            except Exception:
                continue


def _set_alt_state(state: bool):
    global _ALT_KEY_STATE
    if state == _ALT_KEY_STATE:
        return
    _ALT_KEY_STATE = state
    _tag_all_areas()


def _extract_alt(window):
    if window is None:
        return None
    for attr_name in ("event_state_get", "eventstate"):
        attr = getattr(window, attr_name, None)
        if attr is None:
            continue
        try:
            event = attr() if callable(attr) else attr
        except Exception:
            continue
        if event is not None:
            return bool(getattr(event, "alt", False))
    return None


def _read_alt_state(context=None) -> bool:
    system_alt = _system_alt_state()
    if system_alt is not None:
        return system_alt

    windows = []
    if context is not None:
        window = getattr(context, "window", None)
        if window is not None:
            windows.append(window)
        wm = getattr(context, "window_manager", None)
        if wm is not None:
            for win in wm.windows:
                if win not in windows:
                    windows.append(win)
    else:
        wm = getattr(bpy.context, "window_manager", None)  # type: ignore[attr-defined]
        if wm is not None:
            windows.extend(wm.windows)

    for win in windows:
        alt = _extract_alt(win)
        if alt is not None:
            return alt
    return False


def _alt_timer():
    global _ALT_TIMER_RUNNING
    if not _ALT_TIMER_RUNNING:
        return None
    try:
        _update_selection_history()
        state = _read_alt_state()
        _set_alt_state(state)
    except Exception:
        pass
    return 0.1


def _ensure_alt_timer():
    global _ALT_TIMER_RUNNING
    if _ALT_TIMER_RUNNING:
        return
    _ALT_TIMER_RUNNING = True
    bpy.app.timers.register(_alt_timer, first_interval=0.1)


def _stop_alt_timer():
    global _ALT_TIMER_RUNNING
    _ALT_TIMER_RUNNING = False


def _update_selection_history(context=None):
    global _SELECTION_HISTORY
    try:
        source = context if context is not None else bpy.context  # type: ignore[attr-defined]
        selected = list(getattr(source, "selected_objects", []))
    except Exception:
        selected = []
    selected_names = {obj.name for obj in selected}
    _SELECTION_HISTORY = [name for name in _SELECTION_HISTORY if name in selected_names]
    for obj in selected:
        if obj.name not in _SELECTION_HISTORY:
            _SELECTION_HISTORY.append(obj.name)


def _get_operator_bool_setting(context, prop_name: str, default: bool) -> bool:
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return default

    getter = getattr(wm, "operator_properties_last", None)
    if getter is not None:
        try:
            props = getter(_OPERATOR_PROPS_ID)
        except Exception:
            props = None
        if props is not None and hasattr(props, prop_name):
            try:
                return bool(getattr(props, prop_name))
            except Exception:
                pass
    return default


def _unique_selected(objs, allowed_names=None):
    seen = set()
    result = []
    for obj in objs:
        if obj is None:
            continue
        name = getattr(obj, "name", None)
        if not name or name in seen or (allowed_names is not None and name not in allowed_names):
            continue
        result.append(obj)
        seen.add(name)
    return result


@dataclass
class SelectionState:
    """Snapshot of the current object selection and its ordering."""
    selected: list[bpy.types.Object]
    active: bpy.types.Object | None
    order: list[bpy.types.Object]

    def resolve_template(self, use_active: bool) -> bpy.types.Object | None:
        if not self.selected:
            return None

        if use_active:
            if self.active and self.active in self.selected:
                return self.active
            return self.order[-1] if self.order else self.selected[0]

        for obj in self.order:
            if obj != self.active:
                return obj

        for obj in self.selected:
            if obj != self.active:
                return obj

        return self.active if self.active in self.selected else self.selected[0]

    def targets_for(self, template: bpy.types.Object | None) -> list[bpy.types.Object]:
        if template is None:
            return list(self.order)
        return [obj for obj in self.order if obj != template]


def _selection_snapshot(context) -> SelectionState:
    """Collect a deterministic view of the selection for menu labels and execution."""
    _update_selection_history(context)

    selected = _unique_selected(getattr(context, "selected_editable_objects", []), None)
    selected_names = {obj.name for obj in selected}

    view_layer = getattr(context, "view_layer", None)
    active = None
    if view_layer is not None:
        objects = getattr(view_layer, "objects", None)
        if objects is not None:
            active = getattr(objects, "active", None)

    selection_order = getattr(context, "selected_objects", None)
    if selection_order:
        ordered = _unique_selected(selection_order, selected_names)
    else:
        ordered = _unique_selected(selected, selected_names)

    if active and getattr(active, "name", None) in selected_names and active not in ordered:
        ordered.append(active)

    # Rehydrate history into an ordered list of currently selected objects.
    history_objs = []
    for name in _SELECTION_HISTORY:
        if name not in selected_names:
            continue
        obj = bpy.data.objects.get(name)
        if obj is not None:
            history_objs.append(obj)

    if history_objs:
        ordered = _unique_selected(history_objs + ordered, selected_names)

    return SelectionState(selected=selected, active=active, order=ordered)


def _copy_loc_rot(dst, src):
    # Match rotation mode first
    dst.rotation_mode = src.rotation_mode
    if src.rotation_mode == 'QUATERNION':
        dst.rotation_quaternion = src.rotation_quaternion.copy()
    elif src.rotation_mode == 'AXIS_ANGLE':
        dst.rotation_axis_angle = src.rotation_axis_angle[:]  # (angle, x, y, z)
    else:
        dst.rotation_euler = src.rotation_euler.copy()
    dst.location = src.location.copy()


def _is_alt_pressed(context) -> bool:
    state = _read_alt_state(context)
    _set_alt_state(state)
    return state


def _menu_label(context) -> str:
    selection = _selection_snapshot(context) if context is not None else SelectionState([], None, [])
    if not selection.selected:
        return "Replace with Copy (select template first)"

    use_active = _get_operator_bool_setting(context, "use_active_as_template", _USE_ACTIVE_DEFAULT) if context else _USE_ACTIVE_DEFAULT

    template = selection.resolve_template(use_active)
    targets = selection.targets_for(template)

    template_name = template.name if template is not None else "template"
    count = len(targets)
    target_label = "object" if count == 1 else "objects"

    if _is_alt_pressed(context):
        return f"Replace {count} {target_label} with a reference to {template_name}"
    return f"Replace {count} {target_label} with a copy of {template_name}"


class OBJECT_OT_replace_with_copy(bpy.types.Operator):
    """Replace selected objects with copies of the template.\n
    Default: first selected (non-active) is template. Enable the option to use the active object instead.\n
    Hold Alt while invoking to keep the new copies linked to the template data."""
    bl_idname = "object.replace_with_copy"
    bl_label = "Replace With Copy"
    bl_options = {'REGISTER', 'UNDO'}

    use_active_as_template: bpy.props.BoolProperty(
        name="Active is Template",
        description="If enabled, the active object (usually last selected) is used as the template; otherwise the first non-active selected is used",
        default=False,
    )

    make_unique_data: bpy.props.BoolProperty(
        name="Make Unique Mesh/Data",
        description="Copy object data (mesh/curve/etc.) so replacements do not share data with the template; hold Alt to keep data linked",
        default=True,
    )

    match_scale: bpy.props.BoolProperty(
        name="Match Target Scale",
        description="If enabled, the copy takes each target's scale; disable to keep the template's original scale",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and len(context.selected_editable_objects) >= 2

    def invoke(self, context, event):
        use_linked_data = bool(getattr(event, "alt", False))
        self.make_unique_data = not use_linked_data
        return self.execute(context)

    def execute(self, context):
        selection = _selection_snapshot(context)
        if not selection.selected:
            self.report({'ERROR'}, "Nothing selected")
            return {'CANCELLED'}

        if selection.active is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        use_active = bool(self.use_active_as_template)

        template = selection.resolve_template(use_active)
        if template is None:
            self.report({'ERROR'}, "Unable to determine template object")
            return {'CANCELLED'}

        targets = selection.targets_for(template)

        if not targets:
            if use_active:
                self.report({'ERROR'}, "Select at least one target object in addition to the active template")
            else:
                self.report({'ERROR'}, "Need at least one non-active selected object to use as template")
            return {'CANCELLED'}

        # Process each target
        view_layer = context.view_layer
        scene_coll = context.scene.collection

        for tgt in targets:
            tgt_name = tgt.name_full
            tgt_selected = tgt.select_get()
            tgt_parent = tgt.parent
            tgt_parent_type = tgt.parent_type
            tgt_parent_bone = tgt.parent_bone
            tgt_parent_inv = tgt.matrix_parent_inverse.copy()
            tgt_users_colls = list(tgt.users_collection)
            tgt_children_info = [
                (child, child.matrix_world.copy(), child.parent_type, child.parent_bone)
                for child in tgt.children
            ]
            try:
                tgt_hidden_view = tgt.hide_get(view_layer=view_layer)
            except (TypeError, RuntimeError):
                try:
                    tgt_hidden_view = tgt.hide_get()
                except Exception:
                    tgt_hidden_view = False
            tgt_hide_render = tgt.hide_render

            # Create copy
            new_obj = template.copy()
            if self.make_unique_data and new_obj.data:
                new_obj.data = new_obj.data.copy()

            # Link to same collections as target (fallback to scene collection)
            if tgt_users_colls:
                for c in tgt_users_colls:
                    if new_obj.name not in c.objects:
                        c.objects.link(new_obj)
            else:
                # Rare, but ensure it's in the scene
                scene_coll.objects.link(new_obj)

            # Parent like target
            new_obj.parent = tgt_parent
            new_obj.parent_type = tgt_parent_type
            if tgt_parent_type == 'BONE':
                new_obj.parent_bone = tgt_parent_bone
            new_obj.matrix_parent_inverse = tgt_parent_inv

            # Transforms: copy loc+rot from target, scale per option
            _copy_loc_rot(new_obj, tgt)
            if self.match_scale:
                new_obj.scale = tgt.scale.copy()
            else:
                new_obj.scale = template.scale.copy()

            # Ensure visibility and selection mirror the target
            new_obj.hide_render = tgt_hide_render
            try:
                new_obj.hide_set(tgt_hidden_view, view_layer=view_layer)
            except (TypeError, RuntimeError):
                try:
                    new_obj.hide_set(tgt_hidden_view)
                except Exception:
                    pass
            try:
                new_obj.select_set(tgt_selected)
            except Exception:
                pass

            # Update external references from target to new object
            try:
                bpy.data.user_remap(from_=tgt, to=new_obj)
            except AttributeError:
                # Blender versions prior to 3.0 used positional args
                try:
                    bpy.data.user_remap(tgt, new_obj)
                except Exception:
                    pass

            # Reparent children while preserving their transforms
            try:
                new_parent_inv = new_obj.matrix_world.inverted()
            except Exception:
                new_parent_inv = None

            for child, child_world, child_parent_type, child_parent_bone in tgt_children_info:
                child.parent = new_obj
                child.parent_type = child_parent_type
                if child_parent_type == 'BONE':
                    child.parent_bone = child_parent_bone
                child.matrix_world = child_world
                if new_parent_inv is not None:
                    child.matrix_parent_inverse = new_parent_inv @ child_world

            # Delete target, then take its name
            # Ensure target is unlinked properly
            bpy.data.objects.remove(tgt, do_unlink=True)
            new_obj.name = tgt_name

        # Keep template selected and active
        try:
            view_layer.objects.active = template
            template.select_set(True)
        except Exception:
            pass

        return {'FINISHED'}


classes = (
    OBJECT_OT_replace_with_copy,
)

_MENU_HANDLE = None


def register():
    global _MENU_HANDLE
    _ensure_alt_timer()
    _SELECTION_HISTORY.clear()
    for cls in classes:
        bpy.utils.register_class(cls)
    _MENU_HANDLE = register_menu_item(
        menu="VIEW3D_MT_object",
        operator=OBJECT_OT_replace_with_copy,
        label=_menu_label,
        anchor_operator="object.duplicate_move_linked",
        before_anchor=False,
    )
    print("Registered ReplaceWithCopy")


def unregister():
    global _MENU_HANDLE
    _stop_alt_timer()
    _SELECTION_HISTORY.clear()
    if _MENU_HANDLE is not None:
        unregister_menu_item(_MENU_HANDLE)
        _MENU_HANDLE = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
