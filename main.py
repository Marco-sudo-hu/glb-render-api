from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Union
import tempfile
import os
import json
import uuid
import requests
import trimesh
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

app = FastAPI()

RENDERS_DIR = "/tmp/renders"
os.makedirs(RENDERS_DIR, exist_ok=True)


class OpenAIFileRef(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    mime_type: Optional[str] = None
    download_link: Optional[str] = None


class AnalyzeRenderRequest(BaseModel):
    openaiFileIdRefs: List[Union[str, OpenAIFileRef]]
    view: Optional[str] = "three_quarter"
    background: Optional[str] = "white"
    material_style: Optional[str] = "gray_technical"
    include_dimensions: Optional[bool] = True
    include_title: Optional[bool] = True
    unit_preference: Optional[str] = "mm"


@app.get("/")
def health():
    return {"status": "ok", "service": "glb-render-api"}


@app.get("/root")
def root():
    return {"status": "ok", "service": "glb-render-api"}


@app.get("/renders/{filename}")
def get_render(filename: str):
    file_path = os.path.join(RENDERS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Render not found")
    return FileResponse(file_path, media_type="image/png")


def scene_to_single_mesh(scene_or_mesh) -> tuple[trimesh.Trimesh, int]:
    if hasattr(scene_or_mesh, "geometry") and scene_or_mesh.geometry:
        meshes = []
        for geom in scene_or_mesh.geometry.values():
            if isinstance(geom, trimesh.Trimesh) and len(geom.vertices) > 0 and len(geom.faces) > 0:
                meshes.append(geom)

        if not meshes:
            raise ValueError("No valid mesh geometries found in GLB.")

        merged = trimesh.util.concatenate(meshes)
        return merged, len(meshes)

    if isinstance(scene_or_mesh, trimesh.Trimesh):
        if len(scene_or_mesh.vertices) == 0 or len(scene_or_mesh.faces) == 0:
            raise ValueError("Mesh has no valid geometry.")
        return scene_or_mesh, 1

    raise ValueError("Unsupported GLB content.")


def render_technical_png(
    mesh: trimesh.Trimesh,
    output_path: str,
    title: str,
    length: float,
    depth: float,
    height: float,
    unit: str,
    transparent: bool = False
) -> None:
    vertices = mesh.vertices
    faces = mesh.faces

    if len(vertices) == 0 or len(faces) == 0:
        raise ValueError("Cannot render empty mesh.")

    fig = plt.figure(figsize=(12, 7), dpi=200)
    fig.patch.set_alpha(0 if transparent else 1)
    fig.patch.set_facecolor((1, 1, 1, 0) if transparent else "white")

    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor((1, 1, 1, 0) if transparent else "white")

    center = vertices.mean(axis=0)
    v = vertices - center

    ax.plot_trisurf(
        v[:, 0],
        v[:, 1],
        v[:, 2],
        triangles=faces,
        color="lightgray",
        edgecolor="none",
        linewidth=0,
        antialiased=True,
        shade=False
    )

    mins = v.min(axis=0)
    maxs = v.max(axis=0)
    spans = maxs - mins
    max_range = spans.max() / 2.0
    mid = (mins + maxs) / 2.0

    ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
    ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
    ax.set_zlim(mid[2] - max_range, mid[2] + max_range)

    ax.view_init(elev=20, azim=55)
    ax.set_axis_off()

    if not transparent:
        fig.text(
            0.03,
            0.95,
            title.upper(),
            ha="left",
            va="top",
            fontsize=18,
            color="black",
            family="sans-serif",
            weight="bold"
        )

        dims_text = (
            f"L: {length:.2f} {unit}\n"
            f"P: {depth:.2f} {unit}\n"
            f"H: {height:.2f} {unit}"
        )
        fig.text(
            0.03,
            0.08,
            dims_text,
            ha="left",
            va="bottom",
            fontsize=12,
            color="black",
            family="sans-serif"
        )

    plt.subplots_adjust(left=0.00, right=1.00, top=0.92, bottom=0.02)
    plt.savefig(
        output_path,
        bbox_inches="tight",
        pad_inches=0.05,
        transparent=transparent,
        facecolor=(1, 1, 1, 0) if transparent else "white"
    )
    plt.close(fig)


@app.post("/analyze_and_render")
def analyze_and_render(payload: AnalyzeRenderRequest):
    first_file = payload.openaiFileIdRefs[0] if payload.openaiFileIdRefs else None

    raw_refs = []
    for item in payload.openaiFileIdRefs:
        if isinstance(item, str):
            raw_refs.append({"type": "string", "value": item})
        else:
            raw_refs.append(item.model_dump())

    if isinstance(first_file, str):
        return {
            "success": False,
            "structure_name": "TEST STRUCTURE",
            "detected_type": "stub",
            "shape_summary": "Only a string file reference was received.",
            "components": [],
            "materials": [],
            "dimensions": {
                "length": 0,
                "depth": 0,
                "height": 0,
                "unit": payload.unit_preference
            },
            "thickness": {
                "value": 0,
                "unit": payload.unit_preference,
                "reliable": False
            },
            "notes": f"Raw openaiFileIdRefs: {json.dumps(raw_refs, ensure_ascii=False)}",
            "render_image_url": "",
            "render_preview_url": ""
        }

    if first_file is None or not first_file.download_link:
        return {
            "success": False,
            "structure_name": "TEST STRUCTURE",
            "detected_type": "stub",
            "shape_summary": "No downloadable file was received.",
            "components": [],
            "materials": [],
            "dimensions": {
                "length": 0,
                "depth": 0,
                "height": 0,
                "unit": payload.unit_preference
            },
            "thickness": {
                "value": 0,
                "unit": payload.unit_preference,
                "reliable": False
            },
            "notes": f"download_link missing. Raw openaiFileIdRefs: {json.dumps(raw_refs, ensure_ascii=False)}",
            "render_image_url": "",
            "render_preview_url": ""
        }

    suffix = ".glb"
    if first_file.name and "." in first_file.name:
        suffix = os.path.splitext(first_file.name)[1] or ".glb"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        temp_path = tmp_file.name

    try:
        response = requests.get(first_file.download_link, timeout=60)
        response.raise_for_status()

        with open(temp_path, "wb") as f:
            f.write(response.content)

        file_size = os.path.getsize(temp_path)

        scene_or_mesh = trimesh.load(temp_path, force="scene")
        mesh, component_count = scene_to_single_mesh(scene_or_mesh)

                mins, maxs = mesh.bounds
        size = maxs - mins

        length = float(size[0])
        depth = float(size[1])
        height = float(size[2])

        render_filename = f"{uuid.uuid4().hex}.png"
        render_path = os.path.join(RENDERS_DIR, render_filename)
        render_url = f"https://render.marcoepiscopo.com/renders/{render_filename}"

        alpha_filename = f"{uuid.uuid4().hex}_alpha.png"
        alpha_path = os.path.join(RENDERS_DIR, alpha_filename)
        alpha_url = f"https://render.marcoepiscopo.com/renders/{alpha_filename}"

        structure_name = first_file.name or "TEST STRUCTURE"

        render_technical_png(
            mesh=mesh,
            output_path=render_path,
            title=structure_name,
            length=length,
            depth=depth,
            height=height,
            unit=payload.unit_preference,
            transparent=False
        )

        render_technical_png(
            mesh=mesh,
            output_path=alpha_path,
            title=structure_name,
            length=length,
            depth=depth,
            height=height,
            unit=payload.unit_preference,
            transparent=True
        )

        return {
            "success": True,
            "structure_name": structure_name,
            "detected_type": "downloaded_file",
            "shape_summary": "GLB file downloaded, mesh bounds calculated, and technical PNG generated successfully.",
            "components": [f"Detected geometries: {component_count}"],
            "materials": [],
            "dimensions": {
                "length": length,
                "depth": depth,
                "height": height,
                "unit": payload.unit_preference
            },
            "thickness": {
                "value": 0,
                "unit": payload.unit_preference,
                "reliable": False
            },
            "notes": f"Downloaded file to {temp_path} ({file_size} bytes). Render saved to {render_path}. Alpha saved to {alpha_path}. Raw openaiFileIdRefs: {json.dumps(raw_refs, ensure_ascii=False)}",
            "render_image_url": render_url,
            "render_preview_url": render_url,
            "render_alpha_url": alpha_url
        }
        return {
            "success": False,
            "structure_name": first_file.name or "TEST STRUCTURE",
            "detected_type": "analysis_error",
            "shape_summary": "The file was received, but analysis or PNG generation failed.",
            "components": [],
            "materials": [],
            "dimensions": {
                "length": 0,
                "depth": 0,
                "height": 0,
                "unit": payload.unit_preference
            },
            "thickness": {
                "value": 0,
                "unit": payload.unit_preference,
                "reliable": False
            },
            "notes": f"Analysis/render failed: {str(e)}. Raw openaiFileIdRefs: {json.dumps(raw_refs, ensure_ascii=False)}",
            "render_image_url": "",
            "render_preview_url": ""
        }
