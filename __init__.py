# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Andreas Pardeike

# pyright: reportInvalidTypeForm=false

from .manifest import parse_manifest
from .menu_injector import register_menu_item, unregister_menu_item
bl_info = parse_manifest({"location": "3D View > Object (menu)", "category": "Object"})

import bpy

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


class OBJECT_OT_replace_with_copy(bpy.types.Operator):
    """Replace selected objects with copies of the template.\n
    Default: ACTIVE is template. Hold Alt on invoke to use non-active as template."""
    bl_idname = "object.replace_with_copy"
    bl_label = "Replace With Copy"
    bl_options = {'REGISTER', 'UNDO'}

    use_active_as_template: bpy.props.BoolProperty(
        name="Active is Template",
        description="If enabled, the active object is used as the template; otherwise the first non-active selected is used as template",
        default=True,
    )

    make_unique_data: bpy.props.BoolProperty(
        name="Make Unique Mesh/Data",
        description="Copy object data (mesh/curve/etc.) so replacements do not share data with the template",
        default=False,
    )

    match_scale: bpy.props.BoolProperty(
        name="Also Match Scale",
        description="If enabled, the copy will take the target's scale. If disabled, it keeps the template's scale",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and len(context.selected_editable_objects) >= 2

    def invoke(self, context, event):
        # Alt inverts the default to support the “template first, then targets” workflow.
        if hasattr(event, "alt") and event.alt:
            self.use_active_as_template = False
        return self.execute(context)

    def execute(self, context):
        sel = list(context.selected_editable_objects)
        if not sel:
            self.report({'ERROR'}, "Nothing selected")
            return {'CANCELLED'}

        active = context.view_layer.objects.active
        if active is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        # Decide template
        template = None
        if self.use_active_as_template:
            template = active
            targets = [o for o in sel if o != template]
        else:
            # Use the first non-active selected as template; everything else are targets
            non_active = [o for o in sel if o != active]
            if not non_active:
                self.report({'ERROR'}, "Need at least one non-active selected object to use as template")
                return {'CANCELLED'}
            template = non_active[0]
            targets = [o for o in sel if o != template]

        if not targets:
            self.report({'ERROR'}, "Select at least one target in addition to the template")
            return {'CANCELLED'}

        # Process each target
        view_layer = context.view_layer
        scene_coll = context.scene.collection

        for tgt in targets:
            if tgt == template:
                continue

            tgt_name = tgt.name_full
            tgt_parent = tgt.parent
            tgt_parent_type = tgt.parent_type
            tgt_parent_bone = tgt.parent_bone
            tgt_parent_inv = tgt.matrix_parent_inverse.copy()
            tgt_users_colls = list(tgt.users_collection)

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
            _copy_loc_rot(new_obj, tgt if True else template)  # loc+rot from target
            if self.match_scale:
                new_obj.scale = tgt.scale.copy()
            else:
                new_obj.scale = template.scale.copy()

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
    for cls in classes:
        bpy.utils.register_class(cls)
    _MENU_HANDLE = register_menu_item(
        menu="VIEW3D_MT_object",
        operator=OBJECT_OT_replace_with_copy,
        label="Replace With Copy",
        anchor_operator="object.join",
        before_anchor=True,
    )
    print("Registered ReplaceWithCopy")


def unregister():
    global _MENU_HANDLE
    if _MENU_HANDLE is not None:
        unregister_menu_item(_MENU_HANDLE)
        _MENU_HANDLE = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
