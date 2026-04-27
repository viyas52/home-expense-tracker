import os
import base64
import json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from anthropic import Anthropic

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

CATEGORIES = [
    "Provision",
    "Vegetables",
    "Milk & cream",
    "Non-veg",
    "Snacks",
    "Flower",
    "Toiletries",
    "Detergents",
    "Iron",
    "Servant salary",
    "Miscellaneous",
]

SYSTEM_PROMPT = """You are a helpful assistant that reads handwritten household expense notebooks.
The notebook entries are written in a mix of Tamil and English (Tanglish).
Entries follow a date-wise format, for example:
  14 Apr - milk 60, rice 200
  அரிசி 180, காய்கறி 95

Your job is to extract every expense entry and return structured JSON.

Category mapping guide:
- Provision = rice, dal, spices, bread, oil, sugar, atta, staples
- Vegetables = all vegetables and fruits
- Milk & cream = milk, curd, cream, paneer, butter
- Non-veg = chicken, mutton, fish, eggs, prawns
- Snacks = chips, biscuits, bakery items, tea snacks, sweets
- Flower = pooja flowers, garlands, malligai
- Toiletries = harpic, brush, soap, shampoo, toothpaste
- Detergents = dish wash, washing machine liquid, vim, surf
- Iron = clothes ironing, pressing, laundry
- Servant salary = maid, house cleaner, toilet cleaner, cook salary
- Miscellaneous = anything that doesn't fit above

Rules:
- Map each item to the closest category from this list: """ + ", ".join(CATEGORIES) + """
- If an item does not fit any category clearly, use "Miscellaneous"
- Amount is always a number in Indian Rupees
- Date format in output: YYYY-MM-DD. If year is missing, assume current year.
- If a date is missing for some entries, use the last known date in the page
- Return ONLY valid JSON, no explanation, no markdown, no backticks

Output format:
{
  "entries": [
    {
      "date": "2026-04-14",
      "category": "Milk & cream",
      "note": "milk",
      "amount": 60
    }
  ],
  "raw_text": "the full text you read from the image, as-is"
}"""


@app.post("/parse")
async def parse_image(file: UploadFile = File(...)):
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/heic"]:
        raise HTTPException(status_code=400, detail="Only image files are accepted (JPEG, PNG, WEBP, HEIC)")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Keep it under 10MB.")

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    media_type = file.content_type
    if media_type == "image/heic":
        media_type = "image/jpeg"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Please read all the expense entries from this notebook page and return the structured JSON.",
                        },
                    ],
                }
            ],
        )

        raw_output = response.content[0].text.strip()

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                raise HTTPException(status_code=500, detail="Claude returned unparseable output. Try a clearer photo.")

        entries = parsed.get("entries", [])
        for e in entries:
            if e.get("category") not in CATEGORIES:
                e["category"] = "Miscellaneous"
            e["amount"] = float(e.get("amount", 0))

        return {
            "entries": entries,
            "raw_text": parsed.get("raw_text", ""),
            "entry_count": len(entries),
        }

    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(ex)}")


@app.get("/health")
def health():
    return {"status": "ok"}
