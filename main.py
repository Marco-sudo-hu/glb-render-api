from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Union
import tempfile
import os
import requests
import json

app = FastAPI()


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


@app.get("/root")
def root():
    return {"status": "ok", "service": "glb-render-api"}


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
                import trimesh

        scene_or_mesh = trimesh.load(temp_path, force="scene")

        if hasattr(scene_or_mesh, "geometry") and scene_or_mesh.geometry:
            geometries = list(scene_or_mesh.geometry.values())

            bounds_list = []
            for geom in geometries:
                if hasattr(geom, "bounds") and geom.bounds is not None:
                    bounds_list.append(geom.bounds)

            if not bounds_list:
                raise ValueError("No valid mesh bounds found in GLB.")

            import numpy as np
            mins = np.min([b[0] for b in bounds_list], axis=0)
            maxs = np.max([b[1] for b in bounds_list], axis=0)
        else:
            if not hasattr(scene_or_mesh, "bounds") or scene_or_mesh.bounds is None:
                raise ValueError("No valid bounds found in GLB.")
            mins, maxs = scene_or_mesh.bounds

        size = maxs - mins

        length = float(size[0])
        depth = float(size[1])
        height = float(size[2])

        return {
            "success": True,
            "structure_name": first_file.name or "TEST STRUCTURE",
            "detected_type": "downloaded_file",
            "shape_summary": "GLB file downloaded and mesh bounds calculated successfully.",
            "components": [],
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
            "notes": f"Downloaded file to {temp_path} ({file_size} bytes). Raw openaiFileIdRefs: {json.dumps(raw_refs, ensure_ascii=False)}",
            "render_image_url": "",
            "render_preview_url": ""
        }

    except Exception as e:
        return {
            "success": False,
            "structure_name": first_file.name or "TEST STRUCTURE",
            "detected_type": "download_error",
            "shape_summary": "The file reference was received, but download failed.",
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
            "notes": f"Download failed: {str(e)}. Raw openaiFileIdRefs: {json.dumps(raw_refs, ensure_ascii=False)}",
            "render_image_url": "",
            "render_preview_url": ""
        }
