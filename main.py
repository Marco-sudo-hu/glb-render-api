from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Union

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


@app.get("/")
def root():
    return {"status": "ok", "service": "glb-render-api"}


@app.post("/analyze_and_render")
def analyze_and_render(payload: AnalyzeRenderRequest):
    first_file = payload.openaiFileIdRefs[0] if payload.openaiFileIdRefs else None

    if isinstance(first_file, str):
        file_info = {
            "id": first_file,
            "name": None,
            "mime_type": None,
            "download_link": None,
        }
    elif first_file is not None:
        file_info = {
            "id": first_file.id,
            "name": first_file.name,
            "mime_type": first_file.mime_type,
            "download_link": first_file.download_link,
        }
    else:
        file_info = {
            "id": None,
            "name": None,
            "mime_type": None,
            "download_link": None,
        }

    return {
        "success": True,
        "structure_name": "TEST STRUCTURE",
        "detected_type": "stub",
        "shape_summary": "File reference received successfully. Real GLB analysis not implemented yet.",
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
        "notes": f"First file received: {file_info}",
        "render_image_url": "",
        "render_preview_url": ""
    }
