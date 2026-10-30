import os
import json
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# Static papka tayyor bo'lsa ulash
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

DRUGS_FILE = "drugs_database.json"

def load_drugs():
    if os.path.exists(DRUGS_FILE):
        try:
            with open(DRUGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON o'qishda xatolik: {e}")
    return []

def save_drugs(data):
    try:
        with open(DRUGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"JSON saqlashda xatolik: {e}")

async def search_wikimedia_image(drug_name: str, latin_name: str = "") -> str:
    """
    Wikimedia Commons API orqali dori qadog'i, ampulasi yoki flakoni rasmini qidiradi.
    """
    # Lotincha nomdan qavslarni va ortiqcha so'zlarni tozalaymiz
    clean_latin = latin_name.split("(")[0].strip() if latin_name else ""
    
    search_queries = [
        f"{clean_latin} pharmaceutical packaging",
        f"{drug_name} medicine vial box",
        f"{clean_latin} injection ampoule",
        f"{clean_latin} drug box"
    ]
    
    headers = {
        "User-Agent": "PharmaXotiraBot/1.0 (educational medical app; contact@fundamedical.uz)"
    }

    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
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
                    "iiprop": "url|mime",
                    "format": "json"
                }
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    pages = data.get("query", {}).get("pages", {})
                    for page_id, page_info in pages.items():
                        image_info = page_info.get("imageinfo", [{}])[0]
                        mime = image_info.get("mime", "")
                        file_url = image_info.get("url", "")
                        
                        # Faqat haqiqiy rasm formatlarini filtrlaymiz
                        if mime.startswith("image/") and file_url:
                            return file_url
    except Exception as e:
        print(f"Wikimedia API xatosi ({drug_name}): {e}")
    return ""

async def background_update_images():
    """Foydalanuvchi kutib qolmasligi uchun fonda rasmlarni izlab bazaga kiritish"""
    drugs = load_drugs()
    updated = False
    for drug in drugs:
        real_url = drug.get("real_image_url", "")
        # Unsplash yoki bo'sh havolalarni Wikimedia orqali almashtiramiz
        if not real_url or "unsplash.com" in real_url or "via.placeholder" in real_url:
            found_url = await search_wikimedia_image(drug.get("name", ""), drug.get("latin_name", ""))
            if found_url:
                drug["real_image_url"] = found_url
                updated = True
    if updated:
        save_drugs(drugs)

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/app")
async def read_app():
    return FileResponse("static/index.html")

@app.get("/api/drugs")
async def get_drugs(background_tasks: BackgroundTasks):
    drugs = load_drugs()
    # Ma'lumotlarni zudlik bilan qaytarib, rasmlarni yangilashni fon vazifasiga beramiz
    background_tasks.add_task(background_update_images)
    return drugs
