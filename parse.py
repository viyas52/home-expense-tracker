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

CRITICAL CATEGORY MAPPING — you MUST match every item to the correct category using these keywords.
Pay very close attention to Tamil words. Do NOT guess — use the mappings below strictly.

1. Provision = rice (அரிசி, arisi), dal (பருப்பு, paruppu), spices (மசாலா, masala), bread, oil (எண்ணெய், ennai, nallennai), sugar (சர்க்கரை, sakkarai), atta, wheat flour, salt (உப்பு, uppu), tamarind (புளி, puli), turmeric (மஞ்சள், manjal), chilli powder (மிளகாய், milagai), mustard (கடுகு, kadugu), cumin (சீரகம், jeeragam), rava (ரவை), maida, jaggery (வெல்லம், vellam), idli rice, urad dal, toor dal, sambar powder, rasam powder, coconut (தேங்காய், thengai), any grocery staple
2. Vegetables = vegetables (காய்கறி, kaikari), tomato (தக்காளி, thakkali), onion (வெங்காயம், vengayam), potato (உருளைக்கிழங்கு), brinjal (கத்தரிக்காய்), ladies finger (வெண்டைக்காய்), beans, carrot, drumstick (முருங்கைக்காய்), greens (கீரை, keerai), fruits (பழம், pazham), banana (வாழைப்பழம்), apple, grapes — NEVER put meat/chicken/fish here
3. Milk & cream = milk (பால், paal), curd (தயிர், thayir), cream, paneer, butter (வெண்ணெய், vennai), ghee (நெய், nei), buttermilk (மோர், mor), cheese
4. Non-veg = chicken (கோழி, kozhi, சிக்கன், chicken), mutton (ஆட்டிறைச்சி, aattu kari, மட்டன்), fish (மீன், meen), eggs (முட்டை, muttai), prawns (இறால், iraal), meat (இறைச்சி, iraichi), crab (நண்டு, nandu), biryani meat — ANY animal protein goes here, NEVER in Vegetables
5. Snacks = chips, biscuits (பிஸ்கட்), bakery, tea snacks, sweets (இனிப்பு, inippu), murukku, mixture, cake, halwa, laddu, cool drinks, juice
6. Flower = flowers (பூ, poo, புஷ்பம், pushpam), garlands (மாலை, maalai), jasmine (மல்லிகை, mallikai, malligai, மல்லிப்பூ, mullai), rose (ரோஜா, roja), marigold, sambhangi, temple flowers, pooja flowers, flower for prayer, puja items — ANY mention of பூ or flower or maalai or mallikai goes here, NOT Miscellaneous
7. Toiletries = harpic, toilet cleaner liquid, brush, soap (சோப்பு, soap), shampoo, toothpaste (பற்பசை), toothbrush, razor, sanitary items, hand wash, face wash, hair oil
8. Detergents = dish wash (பாத்திரம் கழுவி, vim), washing powder, washing machine liquid, surf, bleach, phenol (பினாயில்), colin, cleaning liquid
9. Iron = clothes ironing (இஸ்திரி, istri, press), pressing, laundry, drycleaning, ironing man
10. Servant salary = maid (வேலைக்காரி, velaikkaari), house cleaner, toilet cleaner salary, cook salary (சமையல்காரி), watchman (காவலாளி), driver, ayah, servant pay
11. Miscellaneous = ONLY use this if the item truly does not fit any of the 10 categories above

Rules:
- You MUST use EXACTLY one of these category names: """ + ", ".join(CATEGORIES) + """
- Think carefully about each Tamil word before assigning a category. Do NOT default to Miscellaneous or Vegetables when unsure — re-read the mappings above
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
