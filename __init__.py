# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Andreas Pardeike

bl_info = {
    "name": "Replace With Copy",
    "author": "Brrainz",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Object",
    "description": "Replace selected objects with a copy of the template object",
    "category": "Object",
}

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

_NAME_SEPARATOR = "\x1f"


def _encode_names(names):
    return _NAME_SEPARATOR.join(names)


def _decode_names(value):
    if not value:
        return []
    return [name for name in value.split(_NAME_SEPARATOR) if name]


class OBJECT_OT_replace_with_copy(Operator):
    bl_idname = "object.replace_with_copy"
    bl_label = "Replace With Copy"
    bl_description = "Replace selected objects with a copy of the template object"
    bl_options = {'REGISTER', 'UNDO'}

    make_unique: BoolProperty(
        name="Make Unique Data",
        description="Create new mesh/data blocks for each replacement",
        default=True,
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    template_name: StringProperty(
        name="Template Name",
        default="",
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    target_names: StringProperty(
        name="Target Names",
        default="",
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        selected = getattr(context, "selected_editable_objects", ())
        return len(selected) >= 2

    def invoke(self, context, event):
        self.template_name = ""
        self.target_names = ""
        if event:
            self.make_unique = not event.alt
        else:
            self.make_unique = True
        return self.execute(context)

    def execute(self, context):
        editable = tuple(context.selected_editable_objects)
        editable_set = set(editable)

        ordered = [obj for obj in getattr(context, "selected_objects", ()) if obj in editable_set]

        template = None
        if self.template_name:
            template_candidate = bpy.data.objects.get(self.template_name)
            if template_candidate and template_candidate in editable_set:
                template = template_candidate

        if template is None:
            if ordered:
                template = ordered[0]
            elif editable:
                template = editable[0]

        if template is None or template not in editable_set:
            self.report({'WARNING'}, "Template object must be selectable")
            return {'CANCELLED'}

        stored_targets = []
        if self.target_names:
            for name in _decode_names(self.target_names):
                obj = bpy.data.objects.get(name)
                if obj and obj in editable_set and obj != template:
                    stored_targets.append(obj)

        targets = stored_targets or [obj for obj in ordered if obj != template]
        if len(targets) < len(editable) - 1:
            targets.extend(
                obj for obj in editable
                if obj != template and obj not in targets
            )

        if not targets:
            self.report({'WARNING'}, "Select at least one target object")
            return {'CANCELLED'}

        replacement_names = []
        scene_collection = context.scene.collection

        for target in targets:
            new_obj = template.copy()
            if self.make_unique and new_obj.data:
                new_obj.data = new_obj.data.copy()

            target_matrix_world = target.matrix_world.copy()
            new_obj.parent = target.parent
            new_obj.parent_type = target.parent_type
            if target.parent_type == 'BONE':
                new_obj.parent_bone = target.parent_bone
            new_obj.matrix_parent_inverse = target.matrix_parent_inverse.copy()

            collections = target.users_collection or template.users_collection or [scene_collection]
            for coll in collections:
                if new_obj.name not in coll.objects:
                    coll.objects.link(new_obj)

            new_obj.hide_viewport = target.hide_viewport
            new_obj.hide_render = target.hide_render

            target_name = target.name
            bpy.data.objects.remove(target, do_unlink=True)
            new_obj.name = target_name
            new_obj.matrix_world = target_matrix_world
            new_obj.select_set(True)
            replacement_names.append(target_name)

        self.template_name = template.name
        self.target_names = _encode_names(replacement_names)

        template.select_set(True)
        context.view_layer.objects.active = template
        return {'FINISHED'}

    def draw(self, _context):
        layout = self.layout
        if self.make_unique:
            layout.label(text="Copies are independent (unique data).")
        else:
            layout.label(text="Copies are linked to the template data.")
        layout.label(text="Hold Alt while invoking to toggle.")


def _draw_object_menu(self, _context):
    layout = self.layout
    previous_context = layout.operator_context
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.operator(
        OBJECT_OT_replace_with_copy.bl_idname,
        text="Replace With Copy",
    )
    layout.operator_context = previous_context


classes = (OBJECT_OT_replace_with_copy,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(_draw_object_menu)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(_draw_object_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
