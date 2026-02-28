# Nexus Export Pro - Project Context

## Overview
Blender addon for batch exporting 3D assets with optimization features. Supports GLB, USDZ, and FBX formats.

**Current Version:** 1.1.0
**Blender Compatibility:** 4.0+
**Main File:** `nexus_export_pro.py`

## Features Implemented

### Core (v1.0.0)
- Batch export queue with UIList
- GLB export with Draco mesh compression
- USDZ export with GLB optimization pipeline
- FBX export with configurable settings
- Texture compression (JPEG/WebP)
- Global texture resizing

### Phase 1 (v1.1.0)
- **Platform Presets:** Apple AR, Android AR, Web Desktop, Web Mobile, Quest VR, Unity, Unreal, E-commerce
- **Mesh Cleanup:** Remove doubles, fix normals, delete loose, triangulate (bmesh-based, non-destructive)
- **Power-of-Two Textures:** Force POT dimensions with nearest/up/down methods
- **Export Report:** Popup with per-object stats (triangles, file size, textures), copy to clipboard
- **Child Mesh Support:** Exports parent with all descendants

## Architecture

### Property Classes
- `ExportQueueItem` - Individual queue item with object pointer
- `NexusExportSettings` - All addon settings as PropertyGroup

### Key Operators
- `NEXUS_OT_process_export` - Main export logic
- `NEXUS_OT_show_report` / `NEXUS_OT_copy_report` - Export report handling
- `NEXUS_OT_add_selected`, `remove_item`, `clear_queue`, `toggle_all` - Queue management

### UI Panels (in order)
1. Main Panel (header)
2. Object Queue
3. Platform Preset
4. Export Formats
5. Draco Compression
6. Texture Settings
7. USDZ Optimization
8. FBX Settings
9. Mesh Cleanup
10. Texture Resize
11. Output

## Planned Features (from enhancement plan)

### Phase 2 - Core Optimization
- Decimate before export (polygon reduction)
- LOD generation (multiple detail levels)
- Pre-export validation (triangle/texture limits)
- OBJ/STL format support

### Phase 3 - Advanced
- Texture channel packing (ORM maps)
- Collision mesh generation
- Texture atlasing
- Material baking

## Code Patterns

### Mesh Operations
Uses bmesh for non-destructive cleanup:
```python
bm = bmesh.new()
bm.from_mesh(mesh)
# operations...
bm.to_mesh(mesh)
bm.free()
```

### Hierarchy Handling
Export includes all descendants:
```python
descendants = self.get_all_descendants(obj)
all_objects = [obj] + descendants
for child in descendants:
    child.select_set(True)
```

### Texture Restoration
Original textures restored after export to avoid permanent changes.

## Testing Notes
- Test platform presets set correct values
- Test mesh cleanup doesn't corrupt geometry
- Test child objects export with parents
- Test texture restoration after export
- Verify in target platforms (AR Quick Look, model-viewer, Unity, Unreal)
