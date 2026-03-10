from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Union
import tempfile
import os
import requests

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
            "notes": "No downloadable file object was received.",
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
            "notes": "download_link missing in openaiFileIdRefs.",
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

        return {
            "success": True,
            "structure_name": first_file.name or "TEST STRUCTURE",
            "detected_type": "downloaded_file",
            "shape_summary": "GLB file downloaded successfully. Real mesh analysis not implemented yet.",
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
            "notes": f"Downloaded file to {temp_path} ({file_size} bytes).",
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
            "notes": f"Download failed: {str(e)}",
            "render_image_url": "",
            "render_preview_url": ""
        }
