from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
import sys, os
sys.path.append(os.path.dirname(__file__))  # 👈 tilføj backend til sys.path
from logic import evaluate_from_bools, evaluate_basic_flow, evaluate_complete_flow, evaluate_krav, generate_explanation
from br18_data import get_category_info

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

@app.post("/evaluate")
async def evaluate(req: Request):
    data = await req.json()
    bools = {
        "overnatning": data.get("overnatning"),
        "selvhjulpen": data.get("selvhjulpen"),
        "kendskab_flugtveje": data.get("kendskab_flugtveje"),
        "maks50personer": data.get("maks50personer")
    }
    res = evaluate_from_bools(bools)
    info = get_category_info(res["kategori"]) if res["kategori"] else None
    return {
        "kategori": res["kategori"],
        "rule_description": res["description"],
        "info": info
    }

@app.post("/evaluate-complete")
async def evaluate_complete(req: Request):
    """Complete BR18 evaluation: Anvendelseskategori -> Risikoklasse -> Brandklasse"""
    data = await req.json()
    result = evaluate_complete_flow(data)
    return result


@app.post("/evaluate-basic")
async def evaluate_basic(req: Request):
    """Basic BR18 evaluation: Anvendelseskategori -> Risikoklasse -> Relevant bilag"""
    data = await req.json()
    result = evaluate_basic_flow(data)
    return result

@app.post("/evaluate-krav")
async def evaluate_krav_endpoint(req: Request):
    """Evaluate all requirements (Krav) based on brandklasse and relevant bilag"""
    data = await req.json()
    result = evaluate_krav(data)
    return result


@app.post("/generate-explanation")
async def generate_explanation_endpoint(req: Request):
    """Generate human-readable explanations for how anvendelseskategori, risikoklasse, and brandklasse were determined"""
    data = await req.json()
    inputs = data.get("inputs", {})
    results = data.get("results", {})
    
    # If results not provided, evaluate first
    if not results or not results.get("success"):
        results = evaluate_complete_flow(inputs)
    
    explanation = generate_explanation(inputs, results)
    return {
        "success": True,
        "explanation": explanation
    }


# Serve input1.json from project root so frontend can load the example
ROOT_DIR = Path(__file__).resolve().parent.parent

@app.get("/input1.json")
def get_input_json():
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    # Serve input1.json
    input_path = ROOT_DIR / "input1.json"
    
    input_path = input_path.resolve()
    # Ensure the resolved path stays within ROOT_DIR
    if ROOT_DIR in input_path.parents and input_path.exists():
        return FileResponse(str(input_path), media_type="application/json", headers=no_cache_headers)
    return JSONResponse({"error": "input1.json not found"}, status_code=404)


@app.get("/inputB1.json")
def get_input_b1_json():
    """Serve inputB1.json from project root so frontend can load bilag 1 template."""
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    input_path = (ROOT_DIR / "inputB1.json").resolve()
    if ROOT_DIR in input_path.parents and input_path.exists():
        return FileResponse(str(input_path), media_type="application/json", headers=no_cache_headers)
    return JSONResponse({"error": "inputB1.json not found"}, status_code=404)


@app.get("/inputB11.json")
def get_input_b11_json():
    """Serve inputB11.json from project root so frontend can load bilag 1.1 template."""
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    input_path = (ROOT_DIR / "inputB11.json").resolve()
    if ROOT_DIR in input_path.parents and input_path.exists():
        return FileResponse(str(input_path), media_type="application/json", headers=no_cache_headers)
    return JSONResponse({"error": "inputB11.json not found"}, status_code=404)


@app.get("/Brandklasse_Bestemmelse.json")
def get_brandklasse_model_json():
    """Serve Brandklasse_Bestemmelse.json from project root so frontend can load bygningstype options."""
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    model_path = (ROOT_DIR / "Brandklasse_Bestemmelse.json").resolve()
    if ROOT_DIR in model_path.parents and model_path.exists():
        return FileResponse(str(model_path), media_type="application/json", headers=no_cache_headers)
    return JSONResponse({"error": "Brandklasse_Bestemmelse.json not found"}, status_code=404)


@app.get("/manual")
async def serve_manual():
    """Serve the manual (guided) BR18 wizard."""
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    html_path = ROOT_DIR / "frontend" / "br18_full.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html", headers=no_cache_headers)
    return JSONResponse({"error": "Manual frontend not found"}, status_code=404)


@app.get("/br18_full.html")
async def serve_manual_html():
    """Serve manual wizard by filename for static-like navigation."""
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    html_path = ROOT_DIR / "frontend" / "br18_full.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html", headers=no_cache_headers)
    return JSONResponse({"error": "br18_full.html not found"}, status_code=404)

@app.get("/style.css")
async def serve_css():
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    css_path = ROOT_DIR / "frontend" / "style.css"
    if css_path.exists():
        return FileResponse(str(css_path), media_type="text/css", headers=no_cache_headers)
    return JSONResponse({"error": "CSS not found"}, status_code=404)


@app.get("/assets/{asset_path:path}")
async def serve_assets(asset_path: str):
    """Serve static assets from frontend/assets (figures, tables, images)."""
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    assets_dir = (ROOT_DIR / "frontend" / "assets").resolve()
    requested = (assets_dir / asset_path).resolve()

    # Ensure requested path stays within assets_dir
    if assets_dir not in requested.parents and requested != assets_dir:
        return JSONResponse({"error": "Invalid asset path"}, status_code=400)

    if requested.exists() and requested.is_file():
        # Let browser infer type; FileResponse will set content-type based on filename when possible.
        return FileResponse(str(requested), headers=no_cache_headers)

    return JSONResponse({"error": "Asset not found"}, status_code=404)


@app.get("/bilag/{bilag_id}.html")
async def serve_bilag_template(bilag_id: str):
    """Serve bilag-specific HTML templates (frontend/bilag/<id>.html)."""
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    # Basic safety: only allow digits
    if not bilag_id.isdigit():
        return JSONResponse({"error": "Invalid bilag id"}, status_code=400)
    html_path = ROOT_DIR / "frontend" / "bilag" / f"{bilag_id}.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html", headers=no_cache_headers)
    return JSONResponse({"error": "Bilag template not found"}, status_code=404)

@app.get("/Krav.json")
async def serve_krav():
    json_path = ROOT_DIR / "Krav.json"
    if json_path.exists():
        return FileResponse(str(json_path), media_type="application/json")
    return JSONResponse({"error": "Krav.json not found"}, status_code=404)

@app.get("/favicon.ico")
async def serve_favicon():
    # Return a simple empty response for favicon to avoid 404 errors
    return JSONResponse({"status": "no favicon"}, status_code=204)

@app.get("/api")
def api_root():
    return {"msg": "BR18 evaluator API - now with complete flow support!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
