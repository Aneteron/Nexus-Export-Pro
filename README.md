<p align="center">
  <img src="https://img.shields.io/badge/Blender-4.0%2B-orange?style=for-the-badge&logo=blender&logoColor=white" alt="Blender 4.0+">
  <img src="https://img.shields.io/github/v/release/Aneteron/Nexus-Export-Pro?style=for-the-badge&color=blue" alt="Latest Release">
  <img src="https://img.shields.io/github/license/Aneteron/Nexus-Export-Pro?style=for-the-badge&color=green" alt="License">
</p>

<h1 align="center">Nexus Export Pro</h1>

<p align="center">
  <b>Batch 3D asset export for Blender — optimized for games, AR, web, and e-commerce.</b>
</p>

<p align="center">
  Export multiple objects at once with platform-specific presets, mesh cleanup,<br>
  texture optimization, and Draco compression. One addon, every format.
</p>

---

## Features

### Export Formats
- **GLB** — with Draco mesh compression and texture compression (JPEG/WebP)
- **USDZ** — with GLB-based optimization pipeline
- **FBX** — with configurable axis, scale, and embed options

### Platform Presets
One-click configuration for your target platform:

| Preset | Format | Compression | Texture Size |
|--------|--------|-------------|--------------|
| Apple AR | USDZ | — | 2048 |
| Android AR | GLB | Draco | 1024 |
| Web Desktop | GLB | Draco + WebP | 2048 |
| Web Mobile | GLB | Draco + WebP | 1024 |
| Quest VR | GLB | Draco | 1024 |
| Unity | FBX | — | 2048 |
| Unreal | FBX | — | 2048 |
| E-commerce | GLB | Draco | 2048 |

### Optimization
- **Mesh Cleanup** — Remove doubles, fix normals, delete loose geometry, triangulate (non-destructive, bmesh-based)
- **Texture Compression** — JPEG or WebP compression on export
- **Global Texture Resizing** — Cap textures to a max resolution
- **Power-of-Two Textures** — Force POT dimensions (nearest, up, or down)
- **Apply Transforms** — Bake location, rotation, and/or scale individually before export

### Workflow
- **Batch Export Queue** — Add objects, toggle inclusion, export all at once
- **Export Selected** — One-click export of selected objects, bypasses the queue
- **Add All in Scene** — Instantly queue every mesh object in the scene
- **Filename Prefix/Suffix** — Custom naming conventions (e.g. `MyProject_Chair_low`)
- **Export Progress** — Visual progress bar with per-object status
- **Export Report** — Per-object stats (triangles, file size, textures) with copy to clipboard
- **Open Output Folder** — Jump to your export directory in one click
- **Child Mesh Support** — Parents automatically export with all descendants

### Auto-Updater
- Checks for new versions from GitHub Releases on startup
- One-click update + restart from within Blender
- No dependencies — uses Python stdlib only

---

## Installation

1. Download `nexus_export_pro.py` from the [latest release](https://github.com/Aneteron/Nexus-Export-Pro/releases/latest)
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Select the downloaded `.py` file
4. Enable **"Nexus Export Pro"**
5. Find it in **View3D → Sidebar → Nexus Export** tab

Future updates are delivered automatically — you'll see an update button in the panel when a new version is available.

---

## Quick Start

1. Select objects in your scene
2. Click **Add Selected** (or **Add All in Scene** for everything)
3. Pick a **Platform Preset** or configure formats manually
4. Set your **Output Directory**
5. Hit **Process & Export**

---

## Requirements

- **Blender 4.0** or newer
- No external dependencies

---

## License

[Polyform Noncommercial 1.0.0](LICENSE) — Free to use, modify, and share. Not for commercial use or resale.
