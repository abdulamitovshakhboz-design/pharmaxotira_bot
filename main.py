import os
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# Mount static directory for frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

DRUGS_FILE = "drugs_database.json"

def load_drugs():
    if os.path.exists(DRUGS_FILE):
        with open(DRUGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_drugs(data):
    with open(DRUGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def search_wikimedia_image(drug_name: str, latin_name: str = "") -> str:
    """
    Wikimedia Commons API orqali dori qadog'i yoki ampulaning ochiq litsenziyali rasmini avtomatik qidiradi.
    """
    search_queries = [
        f"{drug_name} pharmaceutical packaging",
        f"{drug_name} medicine vial box",
        f"{latin_name} injection ampoule",
        f"{drug_name} drug box"
    ]
    
    headers = {
        "User-Agent": "PharmaXotiraBot/1.0 (educational medical app; contact@fundamedical.uz)"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for query in search_queries:
            if not query.strip():
                continue
            url = "https://commons.wikimedia.org/w/api.php"
            params = {
                "action": "query",
                "generator": "search",
                "gnssrc": "haswbstatement",
                "gsearch": f"file:{query}",
                "prop": "imageinfo",
                "iiprop": "url|mime|extmetadata",
                "format": "json"
            }
            try:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    pages = data.get("query", {}).get("pages", {})
                    for page_id, page_info in pages.items():
                        image_info = page_info.get("imageinfo", [{}])[0]
                        mime = image_info.get("mime", "")
                        file_url = image_info.get("url", "")
                        
                        # Faqat rasm (JPEG/PNG) formatlarini filtrlaymiz
                        if mime.startswith("image/") and file_url:
                            return file_url
            except Exception as e:
                print(f"Wikimedia qidiruvida xatolik ({query}): {e}")
                continue
    return ""

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/app")
async def read_app():
    return FileResponse("static/index.html")

@app.get("/api/drugs")
async def get_drugs():
    drugs = load_drugs()
    updated = False

    # Rasmi bo'sh yoki 404 bergan dorilarni avtomatik Wikimedia orqali boyitish
    for drug in drugs:
        real_url = drug.get("real_image_url", "")
        # Agar rasm yo'q bo'lsa yoki Unsplash xato berayotgan bo'lsa, Wikimedia'dan izlaymiz
        if not real_url or "unsplash.com" in real_url or "via.placeholder" in real_url:
            found_url = await search_wikimedia_image(drug.get("name", ""), drug.get("latin_name", ""))
            if found_url:
                drug["real_image_url"] = found_url
                updated = True

    if updated:
        save_drugs(drugs)

    return drugs

@app.get("/api/drugs/{drug_id}/fetch-image")
async def fetch_single_drug_image(drug_id: str):
    drugs = load_drugs()
    for drug in drugs:
        if drug.get("id") == drug_id:
            found_url = await search_wikimedia_image(drug.get("name", ""), drug.get("latin_name", ""))
            if found_url:
                drug["real_image_url"] = found_url
                save_drugs(drugs)
                return {"status": "success", "url": found_url}
            return {"status": "not_found", "message": "Rasm topilmadi"}
    raise HTTPException(status_code=404, detail="Dori topilmadi")
