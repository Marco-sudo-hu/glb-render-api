from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()


class AnalyzeRenderRequest(BaseModel):
    openaiFileIdRefs: List[str]
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
    return {
        "success": True,
        "structure_name": "TEST STRUCTURE",
        "detected_type": "stub",
        "shape_summary": "Endpoint reached successfully. Real GLB analysis not implemented yet.",
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
        "notes": "Temporary placeholder response from /analyze_and_render.",
        "render_image_url": "",
        "render_preview_url": ""
    }
