import json
import re

INPUT_FILE = "output_table/2025/पुणे/मावळ/कुसगांव - पवनमावळ/data.json"
OUTPUT_FILE = "indexed_data.json"

# ===== LAND PATTERNS (STRICT MATCHING) =====
LAND_PATTERNS = [
    r"(?:गट|gut)[^\d]{0,10}(\d+(?:/\d+)*)",
    r"(?:सर्व्हे|survey|सन)[^\d]{0,10}(\d+(?:/\d+)*)",
    r"(?:cts|सीटी|सिटी|citysurvey)[^\d]{0,10}(\d+(?:/\d+)*)",
    r"(?:प्लॉट|plot)[^\d]{0,10}(\d+(?:/\d+)*)",
    r"(?:भुमापन|भुमा|बुमा)[^\d]{0,10}(\d+(?:/\d+)*)",
    r"(?:मिळकत|मिक्र|मिनं)[^\d]{0,10}(\d+(?:/\d+)*)"
]

# ===== NORMALIZE NUMBER =====
def normalize_number(num):
    num = re.sub(r"[^\d/]", "", num)
    num = re.sub(r"/+", "/", num)
    return num.strip()

# ===== VALIDATION FILTER =====
def is_valid_land_number(num):
    if not num:
        return False
    if num == "00":
        return False
    if len(num) == 1:
        return False
    return True

# ===== EXTRACT LAND NUMBERS (STRICT) =====
def extract_land_numbers(text):
    results = set()

    for pattern in LAND_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)

        for num in matches:
            clean = normalize_number(num)

            if is_valid_land_number(clean):
                results.add(clean)

    return list(results)

# ===== PROCESS DATA =====
def process_data(data):
    docs = []
    doc_id = 1
    processed_hashes = set()

    meta = data.get("meta", {})
    free_text_blocks = data.get("free_text", {})

    for block in free_text_blocks.values():
        rows = block.get("rows", [])

        for row in rows:
            cols = row.get("columns", [])
            row_url = row.get("url", "")

            if len(cols) < 8:
                continue

            info_text = cols[7]

            if not info_text or len(info_text) < 10:
                continue

            # Strong Deduplication: Hash the document number and normalized text content
            # This ensures that even if URL or other minor fields differ, the same content isn't indexed twice.
            normalized_text = re.sub(r'\s+', ' ', info_text).strip()
            # We use document number + normalized text as a unique key
            doc_key = f"{cols[1]}_{normalized_text}"

            if doc_key in processed_hashes:
                continue
            processed_hashes.add(doc_key)

            land_numbers = extract_land_numbers(info_text)

            if not land_numbers:
                continue

            docs.append({
                "doc_id": doc_id,
                "serial_number": cols[0],
                "document_number": cols[1],
                "document_type": cols[2],
                "registration_office": cols[3],
                "date": cols[4],
                "seller_party": cols[5],
                "buyer_party": cols[6],
                "text": info_text,
                "land_numbers": land_numbers,
                "pdf_link": row_url,
                "village": meta.get("village_name"),
                "taluka": meta.get("tal_name"),
                "district": meta.get("dist_name")
            })

            doc_id += 1

    return docs

# ===== MAIN =====
def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    processed = process_data(data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)

    print(f"✅ Done! Created {len(processed)} indexed documents")

if __name__ == "__main__":
    main()