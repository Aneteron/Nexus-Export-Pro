# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

bl_info = {
    "name": "Nexus Export Pro",
    "author": "Developer",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Nexus Export",
    "description": "Batch export with platform presets, mesh cleanup, Draco compression, and texture optimization",
    "category": "Import-Export",
}

import bpy
import bmesh
import os
import json
import math
import threading
import urllib.request
import urllib.error
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup, Operator, Panel, UIList, AddonPreferences

# -----------------------------------------------------------------------------
# GitHub Auto-Update Configuration
# -----------------------------------------------------------------------------
GITHUB_OWNER = "YOUR_USERNAME"  # TODO: Set your GitHub username before pushing
GITHUB_REPO = "nexus-export-pro"


# -----------------------------------------------------------------------------
# Property Classes
# -----------------------------------------------------------------------------

class ExportQueueItem(PropertyGroup):
    """Individual item in the export queue."""

    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        description="Object to export"
    )
    include: BoolProperty(
        name="Include",
        default=True,
        description="Include this object in export"
    )


class NexusExportSettings(PropertyGroup):
    """Main settings for Nexus Export Pro."""

    def update_platform_preset(self, context):
        """Apply platform preset settings when selection changes."""
        preset = self.platform_preset

        # Preset configurations: (export_glb, export_usdz, export_fbx, enable_draco,
        #                         texture_compression, max_texture_size, resize_textures)
        presets = {
            'APPLE_AR': {
                'export_glb': False, 'export_usdz': True, 'export_fbx': False,
                'enable_draco': False, 'texture_compression': 'JPEG',
                'max_texture_size': '2048', 'resize_textures': True,
                'usdz_optimize_via_glb': True, 'usdz_texture_compression': 'JPEG',
            },
            'ANDROID_AR': {
                'export_glb': True, 'export_usdz': False, 'export_fbx': False,
                'enable_draco': True, 'texture_compression': 'JPEG',
                'max_texture_size': '1024', 'resize_textures': True,
            },
            'WEB_DESKTOP': {
                'export_glb': True, 'export_usdz': False, 'export_fbx': False,
                'enable_draco': True, 'texture_compression': 'WEBP',
                'max_texture_size': '2048', 'resize_textures': True,
            },
            'WEB_MOBILE': {
                'export_glb': True, 'export_usdz': False, 'export_fbx': False,
                'enable_draco': True, 'texture_compression': 'WEBP',
                'max_texture_size': '1024', 'resize_textures': True,
            },
            'QUEST_VR': {
                'export_glb': True, 'export_usdz': False, 'export_fbx': False,
                'enable_draco': True, 'texture_compression': 'JPEG',
                'max_texture_size': '1024', 'resize_textures': True,
            },
            'UNITY': {
                'export_glb': False, 'export_usdz': False, 'export_fbx': True,
                'enable_draco': False, 'texture_compression': 'NONE',
                'max_texture_size': '2048', 'resize_textures': False,
                'fbx_embed_textures': False, 'fbx_apply_transform': True,
                'axis_preset': 'RCP',
            },
            'UNREAL': {
                'export_glb': False, 'export_usdz': False, 'export_fbx': True,
                'enable_draco': False, 'texture_compression': 'NONE',
                'max_texture_size': '2048', 'resize_textures': False,
                'fbx_embed_textures': False, 'fbx_apply_transform': True,
                'axis_preset': 'BLENDER',
            },
            'ECOMMERCE': {
                'export_glb': True, 'export_usdz': False, 'export_fbx': False,
                'enable_draco': True, 'texture_compression': 'JPEG',
                'max_texture_size': '2048', 'resize_textures': True,
            },
        }

        if preset != 'CUSTOM' and preset in presets:
            config = presets[preset]
            for key, value in config.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    # Platform Preset
    platform_preset: EnumProperty(
        name="Platform Preset",
        items=[
            ('CUSTOM', "Custom", "Manual settings configuration"),
            ('APPLE_AR', "Apple AR (USDZ)", "Optimized for iOS AR Quick Look - Max 100K tris, 2048px, <8MB"),
            ('ANDROID_AR', "Android AR", "Optimized for ARCore - Max 50K tris, 1024px, <5MB"),
            ('WEB_DESKTOP', "Web Desktop", "Optimized for browser 3D viewers - 2048px with Draco+WebP"),
            ('WEB_MOBILE', "Web Mobile", "Optimized for mobile browsers - 1024px, <2MB"),
            ('QUEST_VR', "Quest VR", "Optimized for Meta Quest - 1024px textures"),
            ('UNITY', "Unity", "Optimized for Unity import - FBX with 2048px"),
            ('UNREAL', "Unreal", "Optimized for Unreal Engine - FBX with 2048px"),
            ('ECOMMERCE', "E-commerce", "Optimized for product visualization - <5MB"),
        ],
        default='CUSTOM',
        update=update_platform_preset,
        description="Select a platform preset to auto-configure export settings"
    )

    # Format Settings
    export_glb: BoolProperty(
        name="GLB",
        default=True,
        description="Export as GLB (glTF Binary)"
    )
    export_usdz: BoolProperty(
        name="USDZ",
        default=False,
        description="Export as USDZ (Universal Scene Description)"
    )
    export_fbx: BoolProperty(
        name="FBX",
        default=False,
        description="Export as FBX (Filmbox)"
    )

    # Material Mode
    material_mode: EnumProperty(
        name="Material Mode",
        items=[
            ('LIT', "Lit", "Export with standard PBR materials (Principled BSDF)"),
            ('UNLIT', "Unlit", "Export as unlit/shadeless (base color only, no lighting)"),
        ],
        default='LIT',
        description="How materials are exported. Unlit uses emission to bypass lighting"
    )

    # Draco Settings
    enable_draco: BoolProperty(
        name="Enable Draco Compression",
        default=False,
        description="Use Draco mesh compression for GLB export"
    )
    draco_compression_level: IntProperty(
        name="Compression Level",
        default=6,
        min=0,
        max=10,
        description="Higher values = smaller files but slower encoding"
    )
    draco_position_quantization: IntProperty(
        name="Position Quantization",
        default=11,
        min=1,
        max=30,
        description="Lower values = smaller files but less precision for vertex positions"
    )
    draco_normal_quantization: IntProperty(
        name="Normal Quantization",
        default=10,
        min=1,
        max=30,
        description="Lower values = smaller files but less precision for normals"
    )
    draco_texcoord_quantization: IntProperty(
        name="TexCoord Quantization",
        default=10,
        min=1,
        max=30,
        description="Lower values = smaller files but less precision for UVs"
    )

    # Texture Settings (GLB)
    texture_compression: EnumProperty(
        name="Texture Compression",
        items=[
            ('NONE', "None", "No texture compression"),
            ('JPEG', "JPEG", "Lossy compression, good for photos"),
            ('WEBP', "WebP", "Modern format with good compression"),
        ],
        default='NONE',
        description="Texture compression method for GLB export"
    )
    texture_quality: IntProperty(
        name="Texture Quality",
        default=75,
        min=1,
        max=100,
        description="Quality level for lossy texture compression (higher = better quality)"
    )

    # USDZ Settings
    usdz_optimize_via_glb: BoolProperty(
        name="Optimize via GLB",
        default=True,
        description="Export to compressed GLB first, then convert to USDZ for smaller file size"
    )
    usdz_use_draco: BoolProperty(
        name="Use Draco Compression",
        default=True,
        description="Apply Draco mesh compression during GLB optimization"
    )
    usdz_texture_compression: EnumProperty(
        name="Texture Format",
        items=[
            ('JPEG', "JPEG", "Lossy compression, good balance of size and quality"),
            ('WEBP', "WebP", "Modern format with better compression"),
            ('NONE', "None", "Keep original textures"),
        ],
        default='JPEG',
        description="Texture compression for GLB optimization step"
    )
    usdz_texture_quality: IntProperty(
        name="Texture Quality",
        default=75,
        min=1,
        max=100,
        description="Quality for lossy texture compression (higher = better quality, larger file)"
    )

    # FBX Settings
    fbx_scale: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.001,
        max=1000.0,
        description="Scale factor for FBX export"
    )
    fbx_apply_transform: BoolProperty(
        name="Apply Transform",
        default=True,
        description="Apply object transforms to mesh data"
    )
    fbx_mesh_smooth_type: EnumProperty(
        name="Smoothing",
        items=[
            ('OFF', "None", "Don't export smoothing"),
            ('FACE', "Face", "Face-based smoothing"),
            ('EDGE', "Edge", "Edge-based smoothing"),
        ],
        default='OFF',
        description="Mesh smoothing export method"
    )
    fbx_embed_textures: BoolProperty(
        name="Embed Textures",
        default=False,
        description="Embed textures inside the FBX file"
    )

    # Global Texture Resize (applies to all formats)
    resize_textures: BoolProperty(
        name="Resize Textures",
        default=False,
        description="Resize textures before export (applies to all formats)"
    )
    max_texture_size: EnumProperty(
        name="Max Size",
        items=[
            ('8192', "8192px", "Maximum 8192x8192"),
            ('6144', "6144px", "Maximum 6144x6144"),
            ('4096', "4096px", "Maximum 4096x4096"),
            ('2048', "2048px", "Maximum 2048x2048"),
            ('1024', "1024px", "Maximum 1024x1024"),
            ('512', "512px", "Maximum 512x512"),
        ],
        default='2048',
        description="Maximum texture dimension (larger textures will be scaled down)"
    )

    # Axis / Orientation
    def update_axis_preset(self, context):
        """Apply axis preset values when selection changes."""
        preset = self.axis_preset
        if preset == 'RCP':
            self.export_axis_up = 'Y'
            self.export_axis_forward = '-Z'
        elif preset == 'BLENDER':
            self.export_axis_up = 'Z'
            self.export_axis_forward = 'Y'

    axis_preset: EnumProperty(
        name="Axis Preset",
        items=[
            ('RCP', "RCP (Y-Up)", "Reality Composer Pro / glTF / USD standard (Y-Up, -Z Forward)"),
            ('BLENDER', "Blender (Z-Up)", "Blender native orientation (Z-Up, Y Forward)"),
            ('CUSTOM', "Custom", "Set up and forward axes manually"),
        ],
        default='RCP',
        description="Axis orientation preset",
        update=update_axis_preset,
    )
    export_axis_up: EnumProperty(
        name="Up Axis",
        items=[
            ('Y', "Y Up", "Y axis points up (glTF/USD standard, Web)"),
            ('Z', "Z Up", "Z axis points up (Blender native, Unreal, 3ds Max)"),
        ],
        default='Y',
        description="Which axis points up in the exported file"
    )
    export_axis_forward: EnumProperty(
        name="Forward Axis",
        items=[
            ('-Z', "-Z Forward", "Negative Z forward (glTF/FBX default)"),
            ('Z', "Z Forward", "Positive Z forward"),
            ('-Y', "-Y Forward", "Negative Y forward"),
            ('Y', "Y Forward", "Positive Y forward"),
            ('X', "X Forward", "Positive X forward"),
            ('-X', "-X Forward", "Negative X forward"),
        ],
        default='-Z',
        description="Which axis points forward in the exported file"
    )
    apply_transforms: BoolProperty(
        name="Apply Transforms",
        default=False,
        description="Apply location, rotation, and scale before export (bakes transforms into mesh data)"
    )

    # Output
    output_directory: StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
        description="Directory to export files to"
    )

    # Mesh Cleanup Settings
    cleanup_mesh: BoolProperty(
        name="Cleanup Mesh",
        default=False,
        description="Apply cleanup operations to mesh before export"
    )
    cleanup_remove_doubles: BoolProperty(
        name="Remove Doubles",
        default=True,
        description="Merge vertices that are close together"
    )
    cleanup_doubles_distance: FloatProperty(
        name="Merge Distance",
        default=0.0001,
        min=0.0,
        max=1.0,
        precision=6,
        description="Maximum distance between vertices to merge"
    )
    cleanup_fix_normals: BoolProperty(
        name="Fix Normals",
        default=True,
        description="Recalculate face normals to point outward"
    )
    cleanup_delete_loose: BoolProperty(
        name="Delete Loose",
        default=False,
        description="Remove disconnected vertices, edges, and faces"
    )
    cleanup_triangulate: BoolProperty(
        name="Triangulate",
        default=False,
        description="Convert all faces to triangles before export"
    )

    # Power-of-Two Texture Settings
    force_pot_textures: BoolProperty(
        name="Force Power-of-Two",
        default=False,
        description="Resize textures to nearest power-of-two dimensions"
    )
    pot_method: EnumProperty(
        name="POT Method",
        items=[
            ('NEAREST', "Nearest", "Round to nearest power-of-two"),
            ('UP', "Round Up", "Always round up to next power-of-two"),
            ('DOWN', "Round Down", "Always round down to previous power-of-two"),
        ],
        default='NEAREST',
        description="Method for determining power-of-two size"
    )

    # Export Report Settings
    show_export_report: BoolProperty(
        name="Show Export Report",
        default=True,
        description="Display a summary report after export completes"
    )


# -----------------------------------------------------------------------------
# UIList
# -----------------------------------------------------------------------------

def is_object_visible(obj):
    """Check if an object is visible (not hidden in viewport and not disabled in view layer)."""
    if obj.hide_viewport:
        return False
    if obj.hide_get():
        return False
    return True


def get_all_descendants(obj, visible_only=False):
    """Recursively get all descendant objects of the given object."""
    descendants = []
    for child in obj.children:
        if visible_only and not is_object_visible(child):
            continue
        descendants.append(child)
        descendants.extend(get_all_descendants(child, visible_only=visible_only))
    return descendants


def get_type_icon(obj):
    """Return an appropriate icon for the object type."""
    icons = {
        'MESH': 'OUTLINER_OB_MESH',
        'EMPTY': 'EMPTY_AXIS',
        'CURVE': 'OUTLINER_OB_CURVE',
        'ARMATURE': 'OUTLINER_OB_ARMATURE',
        'LIGHT': 'OUTLINER_OB_LIGHT',
        'CAMERA': 'OUTLINER_OB_CAMERA',
    }
    return icons.get(obj.type, 'OBJECT_DATA')


class NEXUS_UL_export_queue(UIList):
    """UIList for displaying export queue items."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            if item.obj:
                row.prop(item, "include", text="")
                row.label(text=item.obj.name, icon=get_type_icon(item.obj))
                # Show visible child count badge for objects with children
                children = get_all_descendants(item.obj, visible_only=True)
                if children:
                    mesh_count = sum(1 for c in children if c.type == 'MESH')
                    row.label(text=f"[{mesh_count}]")
            else:
                row.label(text="(Missing Object)", icon='ERROR')

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            obj_icon = get_type_icon(item.obj) if item.obj else 'OBJECT_DATA'
            layout.label(text="", icon=obj_icon)


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------

class NEXUS_OT_add_selected(Operator):
    """Add selected objects to the export queue"""
    bl_idname = "nexus.add_selected"
    bl_label = "Add Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def is_ancestor_in_set(self, obj, obj_set):
        """Check if any ancestor of obj is in the given set."""
        parent = obj.parent
        while parent:
            if parent in obj_set:
                return True
            parent = parent.parent
        return False

    def has_mesh_descendants(self, obj):
        """Check if object has any visible mesh descendants."""
        for child in obj.children:
            if not is_object_visible(child):
                continue
            if child.type == 'MESH':
                return True
            if self.has_mesh_descendants(child):
                return True
        return False

    def execute(self, context):
        queue = context.scene.nexus_queue
        existing_objects = {item.obj for item in queue if item.obj}

        # Collect all objects being added this batch
        candidates = []
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj not in existing_objects:
                candidates.append(obj)
            elif obj.type == 'EMPTY' and obj not in existing_objects:
                if self.has_mesh_descendants(obj):
                    candidates.append(obj)

        # Filter out objects whose ancestor is already in the queue or being added
        candidates_set = set(candidates)
        all_parents = existing_objects | candidates_set
        added_count = 0
        for obj in candidates:
            if not self.is_ancestor_in_set(obj, all_parents):
                item = queue.add()
                item.obj = obj
                item.include = True
                added_count += 1

        if added_count > 0:
            self.report({'INFO'}, f"Added {added_count} object(s) to queue")
        else:
            self.report({'WARNING'}, "No new exportable objects to add (select meshes or empties with mesh children)")

        return {'FINISHED'}


class NEXUS_OT_remove_item(Operator):
    """Remove item from the export queue"""
    bl_idname = "nexus.remove_item"
    bl_label = "Remove"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        queue = context.scene.nexus_queue

        if 0 <= self.index < len(queue):
            queue.remove(self.index)
            context.scene.nexus_queue_index = min(
                context.scene.nexus_queue_index,
                len(queue) - 1
            )

        return {'FINISHED'}


class NEXUS_OT_clear_queue(Operator):
    """Clear all items from the export queue"""
    bl_idname = "nexus.clear_queue"
    bl_label = "Clear Queue"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.nexus_queue.clear()
        context.scene.nexus_queue_index = 0
        self.report({'INFO'}, "Queue cleared")
        return {'FINISHED'}


class NEXUS_OT_toggle_all(Operator):
    """Toggle include state for all items"""
    bl_idname = "nexus.toggle_all"
    bl_label = "Toggle All"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        queue = context.scene.nexus_queue

        if len(queue) == 0:
            return {'CANCELLED'}

        # If any are enabled, disable all. Otherwise enable all.
        any_enabled = any(item.include for item in queue)
        new_state = not any_enabled

        for item in queue:
            item.include = new_state

        state_text = "included" if new_state else "excluded"
        self.report({'INFO'}, f"All items {state_text}")

        return {'FINISHED'}


# Global storage for export report data
_export_report_data = {
    'items': [],
    'total_files': 0,
    'total_size': 0,
    'errors': 0,
}


class NEXUS_OT_show_report(Operator):
    """Display the export report"""
    bl_idname = "nexus.show_report"
    bl_label = "Export Report"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        report = _export_report_data

        if not report['items']:
            layout.label(text="No export data available", icon='INFO')
            return

        # Summary header
        box = layout.box()
        row = box.row()
        row.label(text="Export Summary", icon='EXPORT')

        col = box.column(align=True)
        col.label(text=f"Total Files: {report['total_files']}")
        col.label(text=f"Total Size: {self.format_size(report['total_size'])}")
        if report['errors'] > 0:
            col.label(text=f"Errors: {report['errors']}", icon='ERROR')

        # Individual items
        layout.separator()

        for item in report['items']:
            box = layout.box()
            col = box.column(align=True)

            # Object name and status
            status_icon = 'CHECKMARK' if item['success'] else 'ERROR'
            col.label(text=item['object_name'], icon='OBJECT_DATA')

            # Stats row
            row = col.row()
            row.label(text=f"Triangles: {item['triangles']:,}")
            row.label(text=f"Size: {self.format_size(item['file_size'])}")

            # Format and texture info
            row = col.row()
            row.label(text=f"Format: {item['format']}")
            if item['textures']:
                row.label(text=f"Textures: {item['textures']}")

            if not item['success'] and item.get('error'):
                col.label(text=f"Error: {item['error']}", icon='ERROR')

    def format_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"


class NEXUS_OT_copy_report(Operator):
    """Copy export report to clipboard"""
    bl_idname = "nexus.copy_report"
    bl_label = "Copy Report"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        report = _export_report_data
        lines = ["=== Nexus Export Report ===", ""]

        for item in report['items']:
            status = "OK" if item['success'] else "FAILED"
            lines.append(f"Object: {item['object_name']} [{status}]")
            lines.append(f"  - Triangles: {item['triangles']:,}")
            lines.append(f"  - File Size: {self.format_size(item['file_size'])}")
            lines.append(f"  - Format: {item['format']}")
            if item['textures']:
                lines.append(f"  - Textures: {item['textures']}")
            if not item['success'] and item.get('error'):
                lines.append(f"  - Error: {item['error']}")
            lines.append("")

        lines.append(f"Total Files: {report['total_files']}")
        lines.append(f"Total Size: {self.format_size(report['total_size'])}")
        if report['errors'] > 0:
            lines.append(f"Errors: {report['errors']}")

        text = "\n".join(lines)
        context.window_manager.clipboard = text
        self.report({'INFO'}, "Report copied to clipboard")
        return {'FINISHED'}

    def format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"


class NEXUS_OT_process_export(Operator):
    """Process and export all included objects"""
    bl_idname = "nexus.process_export"
    bl_label = "Process & Export"
    bl_options = {'REGISTER'}

    def get_object_textures(self, obj):
        """Get all image textures used by an object's materials."""
        images = set()
        if obj.type != 'MESH':
            return images

        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        images.add(node.image)
        return images

    def get_hierarchy_textures(self, obj):
        """Get all textures from object and all visible descendants."""
        images = self.get_object_textures(obj)
        for child in get_all_descendants(obj, visible_only=True):
            images.update(self.get_object_textures(child))
        return images

    def get_hierarchy_triangle_count(self, obj):
        """Get triangle count for object and all visible descendants."""
        total = self.get_triangle_count(obj)
        for child in get_all_descendants(obj, visible_only=True):
            total += self.get_triangle_count(child)
        return total

    def get_triangle_count(self, obj):
        """Get triangle count for a mesh object."""
        if obj.type != 'MESH':
            return 0
        # Create temporary mesh with modifiers applied
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        # Calculate triangles (each polygon with n verts = n-2 triangles)
        tri_count = sum(len(p.vertices) - 2 for p in mesh.polygons)
        obj_eval.to_mesh_clear()
        return tri_count

    def nearest_pot(self, value, method='NEAREST'):
        """Calculate nearest power-of-two for a given value."""
        if value <= 0:
            return 1
        # Calculate log2 to find the power
        log_val = math.log2(value)
        if method == 'UP':
            return int(2 ** math.ceil(log_val))
        elif method == 'DOWN':
            return int(2 ** math.floor(log_val))
        else:  # NEAREST
            lower = int(2 ** math.floor(log_val))
            upper = int(2 ** math.ceil(log_val))
            if value - lower < upper - value:
                return lower
            return upper

    def apply_mesh_cleanup(self, obj, settings):
        """Apply mesh cleanup operations using bmesh."""
        if obj.type != 'MESH':
            return

        # Get the mesh data
        mesh = obj.data

        # Create bmesh from mesh
        bm = bmesh.new()
        bm.from_mesh(mesh)

        # Remove doubles (merge by distance)
        if settings.cleanup_remove_doubles:
            bmesh.ops.remove_doubles(
                bm,
                verts=bm.verts,
                dist=settings.cleanup_doubles_distance
            )

        # Delete loose geometry
        if settings.cleanup_delete_loose:
            # Find loose verts (not connected to any edges)
            loose_verts = [v for v in bm.verts if not v.link_edges]
            bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')

            # Find loose edges (not connected to any faces)
            loose_edges = [e for e in bm.edges if not e.link_faces]
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')

        # Recalculate normals
        if settings.cleanup_fix_normals:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        # Triangulate
        if settings.cleanup_triangulate:
            bmesh.ops.triangulate(bm, faces=bm.faces)

        # Write back to mesh
        bm.to_mesh(mesh)
        bm.free()

        # Update mesh
        mesh.update()

    def apply_pot_resize(self, images, settings):
        """Apply power-of-two resizing to images."""
        original_sizes = {}
        for img in images:
            if img.size[0] <= 0 or img.size[1] <= 0:
                continue

            new_width = self.nearest_pot(img.size[0], settings.pot_method)
            new_height = self.nearest_pot(img.size[1], settings.pot_method)

            # Only resize if dimensions changed
            if new_width != img.size[0] or new_height != img.size[1]:
                original_sizes[img.name] = (img.size[0], img.size[1])
                img.scale(new_width, new_height)

        return original_sizes

    def convert_materials_unlit(self, all_objects):
        """Convert all materials on objects to unlit (emission-based) for export.
        Returns restore data to undo the conversion."""
        restore_data = []

        processed_mats = set()
        for obj in all_objects:
            if obj.type != 'MESH':
                continue
            for mat_slot in obj.material_slots:
                mat = mat_slot.material
                if not mat or not mat.use_nodes or mat.name in processed_mats:
                    continue
                processed_mats.add(mat.name)

                tree = mat.node_tree
                nodes = tree.nodes
                links = tree.links

                # Find the Material Output node
                output_node = None
                for node in nodes:
                    if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
                        output_node = node
                        break
                if not output_node:
                    continue

                # Find what's connected to the Surface input
                surface_input = output_node.inputs.get('Surface')
                if not surface_input or not surface_input.links:
                    continue

                original_link = surface_input.links[0]
                original_socket = original_link.from_socket
                original_node = original_link.from_node

                # Get the base color source from Principled BSDF
                base_color_source = None
                base_color_value = None
                if original_node.type == 'BSDF_PRINCIPLED':
                    bc_input = original_node.inputs.get('Base Color')
                    if bc_input:
                        if bc_input.links:
                            base_color_source = bc_input.links[0].from_socket
                        else:
                            base_color_value = bc_input.default_value[:]

                # Create Emission node
                emit_node = nodes.new('ShaderNodeEmission')
                emit_node.name = '_nexus_temp_emission'
                emit_node.location = (output_node.location.x - 200, output_node.location.y)
                emit_node.inputs['Strength'].default_value = 1.0

                # Connect base color to emission color
                if base_color_source:
                    links.new(base_color_source, emit_node.inputs['Color'])
                elif base_color_value:
                    emit_node.inputs['Color'].default_value = base_color_value

                # Connect emission to material output
                links.new(emit_node.outputs['Emission'], surface_input)

                restore_data.append({
                    'material': mat,
                    'original_socket': original_socket,
                    'surface_input': surface_input,
                    'emit_node': emit_node,
                })

        return restore_data

    def restore_materials_from_unlit(self, restore_data):
        """Restore materials back to their original lit state."""
        for entry in restore_data:
            mat = entry['material']
            tree = mat.node_tree

            # Reconnect original shader to surface
            tree.links.new(entry['original_socket'], entry['surface_input'])

            # Remove temp emission node
            tree.nodes.remove(entry['emit_node'])

    def execute(self, context):
        global _export_report_data
        settings = context.scene.nexus_export
        queue = context.scene.nexus_queue

        # Reset export report
        _export_report_data = {
            'items': [],
            'total_files': 0,
            'total_size': 0,
            'errors': 0,
        }

        # Validation
        output_dir = bpy.path.abspath(settings.output_directory)
        if not output_dir or not os.path.isdir(output_dir):
            self.report({'ERROR'}, "Please set a valid output directory")
            return {'CANCELLED'}

        if not any([settings.export_glb, settings.export_usdz, settings.export_fbx]):
            self.report({'ERROR'}, "Please select at least one export format")
            return {'CANCELLED'}

        included_items = [item for item in queue if item.include and item.obj]
        if not included_items:
            self.report({'ERROR'}, "No objects selected for export")
            return {'CANCELLED'}

        # Store original selection
        original_selected = context.selected_objects[:]
        original_active = context.view_layer.objects.active

        success_count = 0
        error_count = 0

        for item in included_items:
            obj = item.obj

            # Get all visible descendants (children, grandchildren, etc.)
            descendants = get_all_descendants(obj, visible_only=True)
            all_objects = [obj] + descendants

            # Select object and all its descendants
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            for child in descendants:
                child.select_set(True)
            context.view_layer.objects.active = obj

            base_name = obj.name

            # Apply transforms if enabled (store originals for restoration)
            original_transforms = {}
            if settings.apply_transforms:
                for t_obj in all_objects:
                    original_transforms[t_obj.name] = {
                        'location': t_obj.location.copy(),
                        'rotation': t_obj.rotation_euler.copy(),
                        'scale': t_obj.scale.copy(),
                    }
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            # Store original mesh data for cleanup restoration (for all mesh objects)
            original_mesh_data = {}
            if settings.cleanup_mesh:
                for mesh_obj in all_objects:
                    if mesh_obj.type == 'MESH':
                        # Create a copy of the original mesh data
                        original_mesh_data[mesh_obj.name] = mesh_obj.data.copy()
                        # Apply cleanup operations
                        self.apply_mesh_cleanup(mesh_obj, settings)

            # Convert materials to unlit if needed
            unlit_restore_data = []
            if settings.material_mode == 'UNLIT':
                unlit_restore_data = self.convert_materials_unlit(all_objects)

            # Get triangle count for report (after cleanup if applied) - includes children
            triangle_count = self.get_hierarchy_triangle_count(obj)

            # Get textures for this object and all children
            images = self.get_hierarchy_textures(obj)
            texture_info = f"{len(images)} texture(s)" if images else ""

            # Global texture resizing (applies to all formats)
            original_sizes = {}
            if settings.resize_textures:
                max_size = int(settings.max_texture_size)
                for img in images:
                    if img.size[0] > max_size or img.size[1] > max_size:
                        original_sizes[img.name] = (img.size[0], img.size[1])
                        ratio = min(max_size / img.size[0], max_size / img.size[1])
                        new_width = int(img.size[0] * ratio)
                        new_height = int(img.size[1] * ratio)
                        img.scale(new_width, new_height)

            # Power-of-two texture resize
            pot_original_sizes = {}
            if settings.force_pot_textures:
                pot_original_sizes = self.apply_pot_resize(images, settings)

            # Export GLB
            if settings.export_glb:
                filepath = os.path.join(output_dir, f"{base_name}.glb")
                try:
                    export_kwargs = {
                        'filepath': filepath,
                        'export_format': 'GLB',
                        'use_selection': True,
                        'export_apply': True,
                        'export_yup': settings.export_axis_up == 'Y',
                    }

                    # Draco settings
                    if settings.enable_draco:
                        export_kwargs['export_draco_mesh_compression_enable'] = True
                        export_kwargs['export_draco_mesh_compression_level'] = settings.draco_compression_level
                        export_kwargs['export_draco_position_quantization'] = settings.draco_position_quantization
                        export_kwargs['export_draco_normal_quantization'] = settings.draco_normal_quantization
                        export_kwargs['export_draco_texcoord_quantization'] = settings.draco_texcoord_quantization
                    else:
                        export_kwargs['export_draco_mesh_compression_enable'] = False

                    # Texture settings
                    if settings.texture_compression == 'JPEG':
                        export_kwargs['export_image_format'] = 'JPEG'
                        export_kwargs['export_jpeg_quality'] = settings.texture_quality
                    elif settings.texture_compression == 'WEBP':
                        export_kwargs['export_image_format'] = 'WEBP'
                    else:
                        export_kwargs['export_image_format'] = 'AUTO'

                    bpy.ops.export_scene.gltf(**export_kwargs)
                    success_count += 1
                except Exception as e:
                    self.report({'WARNING'}, f"GLB export failed for {base_name}: {str(e)}")
                    error_count += 1

            # Export USDZ
            if settings.export_usdz:
                filepath = os.path.join(output_dir, f"{base_name}.usdz")

                if settings.usdz_optimize_via_glb:
                    # Optimize via GLB pipeline
                    try:
                        import tempfile

                        # Create temp GLB path
                        temp_dir = tempfile.gettempdir()
                        temp_glb = os.path.join(temp_dir, f"_nexus_temp_{base_name}.glb")

                        # Export compressed GLB
                        glb_kwargs = {
                            'filepath': temp_glb,
                            'export_format': 'GLB',
                            'use_selection': True,
                            'export_apply': True,
                            'export_yup': settings.export_axis_up == 'Y',
                        }

                        # Draco compression
                        if settings.usdz_use_draco:
                            glb_kwargs['export_draco_mesh_compression_enable'] = True
                            glb_kwargs['export_draco_mesh_compression_level'] = settings.draco_compression_level
                            glb_kwargs['export_draco_position_quantization'] = settings.draco_position_quantization
                            glb_kwargs['export_draco_normal_quantization'] = settings.draco_normal_quantization
                            glb_kwargs['export_draco_texcoord_quantization'] = settings.draco_texcoord_quantization
                        else:
                            glb_kwargs['export_draco_mesh_compression_enable'] = False

                        # Texture compression
                        if settings.usdz_texture_compression == 'JPEG':
                            glb_kwargs['export_image_format'] = 'JPEG'
                            glb_kwargs['export_jpeg_quality'] = settings.usdz_texture_quality
                        elif settings.usdz_texture_compression == 'WEBP':
                            glb_kwargs['export_image_format'] = 'WEBP'
                        else:
                            glb_kwargs['export_image_format'] = 'AUTO'

                        bpy.ops.export_scene.gltf(**glb_kwargs)

                        # Track objects before import
                        objects_before = set(bpy.data.objects)

                        # Import the compressed GLB
                        bpy.ops.import_scene.gltf(filepath=temp_glb)

                        # Find newly imported objects
                        imported_objects = set(bpy.data.objects) - objects_before

                        # Select only imported objects
                        bpy.ops.object.select_all(action='DESELECT')
                        for imp_obj in imported_objects:
                            imp_obj.select_set(True)
                            context.view_layer.objects.active = imp_obj

                        # Export USDZ from imported objects
                        bpy.ops.wm.usd_export(
                            filepath=filepath,
                            selected_objects_only=True,
                        )

                        # Cleanup: delete imported objects and their data
                        bpy.ops.object.delete()

                        # Remove orphan meshes and materials from import
                        for block in bpy.data.meshes:
                            if block.users == 0:
                                bpy.data.meshes.remove(block)
                        for block in bpy.data.materials:
                            if block.users == 0:
                                bpy.data.materials.remove(block)
                        for block in bpy.data.images:
                            if block.users == 0:
                                bpy.data.images.remove(block)

                        # Delete temp GLB file
                        if os.path.exists(temp_glb):
                            os.remove(temp_glb)

                        success_count += 1

                    except Exception as e:
                        self.report({'WARNING'}, f"USDZ export failed for {base_name}: {str(e)}")
                        error_count += 1
                        # Cleanup temp file on error
                        if 'temp_glb' in locals() and os.path.exists(temp_glb):
                            os.remove(temp_glb)
                else:
                    # Direct USDZ export (no optimization)
                    try:
                        bpy.ops.wm.usd_export(
                            filepath=filepath,
                            selected_objects_only=True,
                        )
                        success_count += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"USDZ export failed for {base_name}: {str(e)}")
                        error_count += 1

            # Export FBX
            if settings.export_fbx:
                filepath = os.path.join(output_dir, f"{base_name}.fbx")
                try:
                    bpy.ops.export_scene.fbx(
                        filepath=filepath,
                        use_selection=True,
                        global_scale=settings.fbx_scale,
                        apply_unit_scale=True,
                        apply_scale_options='FBX_SCALE_ALL',
                        axis_forward=settings.export_axis_forward,
                        axis_up=settings.export_axis_up,
                        use_mesh_modifiers=True,
                        mesh_smooth_type=settings.fbx_mesh_smooth_type,
                        embed_textures=settings.fbx_embed_textures,
                        bake_space_transform=settings.fbx_apply_transform,
                    )
                    success_count += 1
                except Exception as e:
                    self.report({'WARNING'}, f"FBX export failed for {base_name}: {str(e)}")
                    error_count += 1

            # Collect file sizes and report data for this object
            exported_formats = []
            total_file_size = 0

            if settings.export_glb:
                glb_path = os.path.join(output_dir, f"{base_name}.glb")
                if os.path.exists(glb_path):
                    size = os.path.getsize(glb_path)
                    total_file_size += size
                    exported_formats.append('GLB')

            if settings.export_usdz:
                usdz_path = os.path.join(output_dir, f"{base_name}.usdz")
                if os.path.exists(usdz_path):
                    size = os.path.getsize(usdz_path)
                    total_file_size += size
                    exported_formats.append('USDZ')

            if settings.export_fbx:
                fbx_path = os.path.join(output_dir, f"{base_name}.fbx")
                if os.path.exists(fbx_path):
                    size = os.path.getsize(fbx_path)
                    total_file_size += size
                    exported_formats.append('FBX')

            # Add to report data
            _export_report_data['items'].append({
                'object_name': base_name,
                'triangles': triangle_count,
                'file_size': total_file_size,
                'format': ', '.join(exported_formats),
                'textures': texture_info,
                'success': len(exported_formats) > 0,
                'error': None,
            })
            _export_report_data['total_size'] += total_file_size
            _export_report_data['total_files'] += len(exported_formats)

            # Restore original texture sizes after all exports for this object
            if original_sizes:
                for img_name, (orig_w, orig_h) in original_sizes.items():
                    img = bpy.data.images.get(img_name)
                    if img:
                        img.scale(orig_w, orig_h)

            # Restore POT texture sizes
            if pot_original_sizes:
                for img_name, (orig_w, orig_h) in pot_original_sizes.items():
                    img = bpy.data.images.get(img_name)
                    if img:
                        img.scale(orig_w, orig_h)

            # Restore original mesh data after cleanup (for all mesh objects)
            if original_mesh_data:
                for mesh_obj in all_objects:
                    if mesh_obj.name in original_mesh_data:
                        old_mesh = mesh_obj.data
                        mesh_obj.data = original_mesh_data[mesh_obj.name]
                        bpy.data.meshes.remove(old_mesh)

            # Restore original transforms
            if original_transforms:
                for t_obj in all_objects:
                    if t_obj.name in original_transforms:
                        t = original_transforms[t_obj.name]
                        t_obj.location = t['location']
                        t_obj.rotation_euler = t['rotation']
                        t_obj.scale = t['scale']

            # Restore materials from unlit
            if unlit_restore_data:
                self.restore_materials_from_unlit(unlit_restore_data)

        # Update error count in report
        _export_report_data['errors'] = error_count

        # Restore original selection
        bpy.ops.object.select_all(action='DESELECT')
        for obj in original_selected:
            if obj:
                obj.select_set(True)
        if original_active:
            context.view_layer.objects.active = original_active

        if error_count == 0:
            self.report({'INFO'}, f"Successfully exported {success_count} file(s)")
        else:
            self.report({'WARNING'}, f"Exported {success_count} file(s), {error_count} failed")

        # Show export report if enabled
        if settings.show_export_report and _export_report_data['items']:
            bpy.ops.nexus.show_report('INVOKE_DEFAULT')

        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Auto-Update System
# -----------------------------------------------------------------------------

# Module-level state for update check (avoids addon preference race conditions)
_update_state = {
    "checked": False,
    "checking": False,
    "update_available": False,
    "latest_version": "",
    "download_url": "",
    "error": "",
}


def _version_tuple(tag: str):
    """Parse a version tag like 'v1.2.0' or '1.2.0' into a tuple of ints."""
    tag = tag.lstrip("vV")
    parts = tag.split(".")
    return tuple(int(p) for p in parts[:3])


def _check_github_release():
    """Background thread target: fetch the latest release from GitHub."""
    global _update_state
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        tag = data.get("tag_name", "")
        latest = _version_tuple(tag)
        current = bl_info["version"]
        if latest > current:
            # Look for the .py asset in release assets
            download_url = ""
            for asset in data.get("assets", []):
                if asset["name"].endswith(".py"):
                    download_url = asset["browser_download_url"]
                    break
            # Fallback to zipball if no .py asset
            if not download_url:
                download_url = data.get("zipball_url", "")
            _update_state["update_available"] = True
            _update_state["latest_version"] = tag
            _update_state["download_url"] = download_url
        else:
            _update_state["update_available"] = False
            _update_state["latest_version"] = tag
    except Exception as e:
        _update_state["error"] = str(e)
    finally:
        _update_state["checking"] = False
        _update_state["checked"] = True


class NexusExportPreferences(AddonPreferences):
    """Addon preferences for Nexus Export Pro (stores persistent settings)."""
    bl_idname = __name__

    auto_check_updates: BoolProperty(
        name="Check for Updates on Startup",
        default=True,
        description="Automatically check for updates when the panel is first drawn"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "auto_check_updates")

        version_str = ".".join(str(v) for v in bl_info["version"])
        layout.label(text=f"Installed Version: v{version_str}")

        if _update_state["update_available"]:
            box = layout.box()
            box.alert = True
            box.label(text=f"Update available: {_update_state['latest_version']}", icon='INFO')
            box.operator("nexus.install_update", icon='IMPORT')
        elif _update_state["checked"]:
            layout.label(text="You are up to date.", icon='CHECKMARK')

        layout.operator("nexus.check_update", icon='URL')


class NEXUS_OT_check_update(Operator):
    """Check GitHub for a newer version of Nexus Export Pro"""
    bl_idname = "nexus.check_update"
    bl_label = "Check for Updates"

    def execute(self, context):
        global _update_state
        if _update_state["checking"]:
            self.report({'INFO'}, "Update check already in progress...")
            return {'CANCELLED'}

        _update_state["checking"] = True
        _update_state["error"] = ""
        thread = threading.Thread(target=_check_github_release, daemon=True)
        thread.start()
        self.report({'INFO'}, "Checking for updates...")
        return {'FINISHED'}


class NEXUS_OT_install_update(Operator):
    """Download and install the latest version from GitHub"""
    bl_idname = "nexus.install_update"
    bl_label = "Install Update"
    bl_description = "Download and install the latest version. Blender restart required"

    def execute(self, context):
        global _update_state
        download_url = _update_state.get("download_url", "")
        if not download_url:
            self.report({'ERROR'}, "No download URL available")
            return {'CANCELLED'}

        if not download_url.endswith(".py"):
            self.report({'ERROR'}, "Release has no .py asset. Download manually from GitHub.")
            return {'CANCELLED'}

        # Determine the installed addon file path
        addon_path = os.path.realpath(__file__)

        try:
            req = urllib.request.Request(download_url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                new_code = resp.read()

            # Basic validation: check it looks like our addon
            if b"bl_info" not in new_code or b"Nexus Export Pro" not in new_code:
                self.report({'ERROR'}, "Downloaded file doesn't appear to be Nexus Export Pro")
                return {'CANCELLED'}

            # Write the update
            with open(addon_path, "wb") as f:
                f.write(new_code)

            _update_state["update_available"] = False
            _update_state["checked"] = False

            self.report({'INFO'},
                        f"Updated to {_update_state['latest_version']}! "
                        "Please restart Blender to apply.")

        except Exception as e:
            self.report({'ERROR'}, f"Update failed: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


# -----------------------------------------------------------------------------
# Panels
# -----------------------------------------------------------------------------

class NEXUS_PT_main_panel(Panel):
    """Main panel for Nexus Export Pro"""
    bl_label = "Nexus Export Pro v" + ".".join(str(v) for v in bl_info["version"])
    bl_idname = "NEXUS_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"

    def draw(self, context):
        layout = self.layout

        # Trigger auto-check on first panel draw
        prefs = context.preferences.addons.get(__name__)
        if prefs and prefs.preferences.auto_check_updates:
            if not _update_state["checked"] and not _update_state["checking"]:
                bpy.ops.nexus.check_update()

        # Update indicator row
        if _update_state["checking"]:
            row = layout.row(align=True)
            row.label(text="Checking for updates...", icon='SORTTIME')
        elif _update_state["update_available"]:
            row = layout.row(align=True)
            row.alert = True
            row.operator(
                "nexus.install_update",
                text=f"Update to {_update_state['latest_version']}",
                icon='IMPORT',
            )
        else:
            row = layout.row(align=True)
            row.operator("nexus.check_update", text="Check for Updates", icon='URL')


class NEXUS_PT_object_queue(Panel):
    """Object queue subpanel"""
    bl_label = "Object Queue"
    bl_idname = "NEXUS_PT_object_queue"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.template_list(
            "NEXUS_UL_export_queue",
            "",
            scene,
            "nexus_queue",
            scene,
            "nexus_queue_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("nexus.add_selected", icon='ADD', text="")
        col.operator("nexus.remove_item", icon='REMOVE', text="").index = scene.nexus_queue_index
        col.separator()
        col.operator("nexus.clear_queue", icon='X', text="")

        row = layout.row(align=True)
        row.operator("nexus.toggle_all", text="Toggle All")

        queue = scene.nexus_queue
        included = sum(1 for item in queue if item.include and item.obj)
        layout.label(text=f"{included} of {len(queue)} objects included")

        # Children preview for the selected queue item
        if queue and 0 <= scene.nexus_queue_index < len(queue):
            active_item = queue[scene.nexus_queue_index]
            if active_item.obj and active_item.obj.children:
                visible_descendants = get_all_descendants(active_item.obj, visible_only=True)
                if visible_descendants:
                    box = layout.box()
                    header_row = box.row()
                    header_row.label(text="Export Contents:", icon='OUTLINER')

                    self.draw_children_tree(box, active_item.obj, depth=0)

                    mesh_count = sum(1 for c in visible_descendants if c.type == 'MESH')
                    total_count = len(visible_descendants)
                    box.label(text=f"{mesh_count} mesh(es), {total_count} object(s) total")

                    # Warn about hidden objects that will be skipped
                    all_descendants = get_all_descendants(active_item.obj, visible_only=False)
                    hidden_count = len(all_descendants) - len(visible_descendants)
                    if hidden_count > 0:
                        row = box.row()
                        row.alert = True
                        row.label(text=f"{hidden_count} hidden object(s) excluded", icon='HIDE_ON')

    def draw_children_tree(self, layout, obj, depth):
        """Recursively draw a tree of visible child objects."""
        for child in obj.children:
            if not is_object_visible(child):
                continue
            row = layout.row(align=True)
            # Indent with empty space based on depth
            if depth > 0:
                row.label(text="", icon='BLANK1')
            for i in range(depth):
                row.label(text="", icon='BLANK1')
            row.label(text=child.name, icon=get_type_icon(child))
            if child.children:
                self.draw_children_tree(layout, child, depth + 1)


class NEXUS_PT_platform_preset(Panel):
    """Platform preset selection subpanel"""
    bl_label = "Platform Preset"
    bl_idname = "NEXUS_PT_platform_preset"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.prop(settings, "platform_preset", text="")

        # Show info about selected preset
        preset = settings.platform_preset
        if preset != 'CUSTOM':
            box = layout.box()
            col = box.column(align=True)

            preset_info = {
                'APPLE_AR': ("USDZ", "2048px", "100K tris", "<8 MB"),
                'ANDROID_AR': ("GLB+Draco", "1024px", "50K tris", "<5 MB"),
                'WEB_DESKTOP': ("GLB+Draco+WebP", "2048px", "100K tris", "<5 MB"),
                'WEB_MOBILE': ("GLB+Draco+WebP", "1024px", "50K tris", "<2 MB"),
                'QUEST_VR': ("GLB+Draco", "1024px", "100K tris", "-"),
                'UNITY': ("FBX", "2048px", "-", "-"),
                'UNREAL': ("FBX", "2048px", "-", "-"),
                'ECOMMERCE': ("GLB+Draco", "2048px", "50K tris", "<5 MB"),
            }

            if preset in preset_info:
                info = preset_info[preset]
                col.label(text=f"Format: {info[0]}", icon='FILE_3D')
                col.label(text=f"Textures: {info[1]}", icon='TEXTURE')
                if info[2] != "-":
                    col.label(text=f"Max Tris: {info[2]}", icon='MESH_DATA')
                if info[3] != "-":
                    col.label(text=f"Target Size: {info[3]}", icon='FILE')


class NEXUS_PT_format_settings(Panel):
    """Format selection subpanel"""
    bl_label = "Export Formats"
    bl_idname = "NEXUS_PT_format_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        col.prop(settings, "export_glb", text="GLB (glTF Binary)")
        col.prop(settings, "export_usdz", text="USDZ")
        col.prop(settings, "export_fbx", text="FBX")

        col.separator()
        col.prop(settings, "material_mode")


class NEXUS_PT_draco_settings(Panel):
    """Draco compression settings subpanel"""
    bl_label = "Draco Compression"
    bl_idname = "NEXUS_PT_draco_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.nexus_export.export_glb

    def draw_header(self, context):
        settings = context.scene.nexus_export
        self.layout.prop(settings, "enable_draco", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.active = settings.enable_draco

        col = layout.column()
        col.prop(settings, "draco_compression_level")

        col.separator()
        col.label(text="Quantization (lower = smaller file):")
        col.prop(settings, "draco_position_quantization", text="Position")
        col.prop(settings, "draco_normal_quantization", text="Normal")
        col.prop(settings, "draco_texcoord_quantization", text="TexCoord")


class NEXUS_PT_texture_settings(Panel):
    """Texture compression settings subpanel"""
    bl_label = "Texture Settings"
    bl_idname = "NEXUS_PT_texture_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.nexus_export.export_glb

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.prop(settings, "texture_compression")

        if settings.texture_compression in {'JPEG', 'WEBP'}:
            col.prop(settings, "texture_quality")


class NEXUS_PT_usdz_settings(Panel):
    """USDZ export settings subpanel"""
    bl_label = "USDZ Optimization"
    bl_idname = "NEXUS_PT_usdz_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.nexus_export.export_usdz

    def draw_header(self, context):
        settings = context.scene.nexus_export
        self.layout.prop(settings, "usdz_optimize_via_glb", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.active = settings.usdz_optimize_via_glb

        col = layout.column()
        col.prop(settings, "usdz_use_draco")
        col.separator()
        col.prop(settings, "usdz_texture_compression")
        if settings.usdz_texture_compression in {'JPEG', 'WEBP'}:
            col.prop(settings, "usdz_texture_quality")


class NEXUS_PT_fbx_settings(Panel):
    """FBX export settings subpanel"""
    bl_label = "FBX Settings"
    bl_idname = "NEXUS_PT_fbx_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.nexus_export.export_fbx

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.prop(settings, "fbx_scale")
        col.prop(settings, "fbx_apply_transform")
        col.prop(settings, "fbx_mesh_smooth_type")
        col.prop(settings, "fbx_embed_textures")


class NEXUS_PT_mesh_cleanup(Panel):
    """Mesh cleanup settings subpanel"""
    bl_label = "Mesh Cleanup"
    bl_idname = "NEXUS_PT_mesh_cleanup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        settings = context.scene.nexus_export
        self.layout.prop(settings, "cleanup_mesh", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.active = settings.cleanup_mesh

        col = layout.column()
        col.prop(settings, "cleanup_remove_doubles")

        # Show merge distance only if remove doubles is enabled
        if settings.cleanup_remove_doubles:
            row = col.row()
            row.prop(settings, "cleanup_doubles_distance")

        col.separator()
        col.prop(settings, "cleanup_fix_normals")
        col.prop(settings, "cleanup_delete_loose")
        col.prop(settings, "cleanup_triangulate")

        col.separator()
        col.label(text="Applied to copy, original preserved", icon='INFO')


class NEXUS_PT_texture_resize(Panel):
    """Global texture resize settings subpanel"""
    bl_label = "Texture Resize"
    bl_idname = "NEXUS_PT_texture_resize"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        settings = context.scene.nexus_export
        self.layout.prop(settings, "resize_textures", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False

        # Max texture size section
        col = layout.column()
        col.active = settings.resize_textures
        col.prop(settings, "max_texture_size")

        # Power-of-Two section
        layout.separator()
        col = layout.column()
        col.prop(settings, "force_pot_textures")

        if settings.force_pot_textures:
            col.prop(settings, "pot_method")

        layout.separator()
        layout.label(text="Applies to all export formats", icon='INFO')


class NEXUS_PT_output(Panel):
    """Output settings and export button subpanel"""
    bl_label = "Output"
    bl_idname = "NEXUS_PT_output"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Nexus Export"
    bl_parent_id = "NEXUS_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nexus_export

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.prop(settings, "output_directory", text="Directory")

        col.separator()
        col.prop(settings, "axis_preset")
        if settings.axis_preset == 'CUSTOM':
            row = col.row(align=True)
            row.prop(settings, "export_axis_up", text="Up")
            row = col.row(align=True)
            row.prop(settings, "export_axis_forward", text="Forward")
        col.prop(settings, "apply_transforms")

        col.separator()
        col.prop(settings, "show_export_report")

        col.separator()

        row = layout.row()
        row.scale_y = 2.0
        row.operator("nexus.process_export", icon='EXPORT')

        # Show report buttons if there's report data
        if _export_report_data['items']:
            row = layout.row(align=True)
            row.operator("nexus.show_report", text="View Report", icon='FILE_TEXT')
            row.operator("nexus.copy_report", text="Copy", icon='COPYDOWN')


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

classes = (
    ExportQueueItem,
    NexusExportSettings,
    NexusExportPreferences,
    NEXUS_UL_export_queue,
    NEXUS_OT_add_selected,
    NEXUS_OT_remove_item,
    NEXUS_OT_clear_queue,
    NEXUS_OT_toggle_all,
    NEXUS_OT_show_report,
    NEXUS_OT_copy_report,
    NEXUS_OT_process_export,
    NEXUS_OT_check_update,
    NEXUS_OT_install_update,
    NEXUS_PT_main_panel,
    NEXUS_PT_object_queue,
    NEXUS_PT_platform_preset,
    NEXUS_PT_format_settings,
    NEXUS_PT_draco_settings,
    NEXUS_PT_texture_settings,
    NEXUS_PT_usdz_settings,
    NEXUS_PT_fbx_settings,
    NEXUS_PT_mesh_cleanup,
    NEXUS_PT_texture_resize,
    NEXUS_PT_output,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.nexus_export = PointerProperty(type=NexusExportSettings)
    bpy.types.Scene.nexus_queue = CollectionProperty(type=ExportQueueItem)
    bpy.types.Scene.nexus_queue_index = IntProperty(name="Active Queue Index", default=0)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.nexus_export
    del bpy.types.Scene.nexus_queue
    del bpy.types.Scene.nexus_queue_index


if __name__ == "__main__":
    register()
