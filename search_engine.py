import json
import re
import os
import argparse

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
def process_data(data, processed_hashes, current_doc_id):
    docs = []
    
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
            normalized_text = re.sub(r'\s+', ' ', info_text).strip()
            doc_key = f"{cols[1]}_{normalized_text}"

            if doc_key in processed_hashes:
                continue
            processed_hashes.add(doc_key)

            land_numbers = extract_land_numbers(info_text)

            if not land_numbers:
                continue

            docs.append({
                "doc_id": current_doc_id,
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
                "district": meta.get("dist_name"),
                "year": meta.get("yearsel")
            })

            current_doc_id += 1

    return docs, current_doc_id

# ===== MAIN =====
def main():
    parser = argparse.ArgumentParser(description="Index IGR data for a specific village across all years.")
    parser.add_argument("-d", "--district", required=True, help="District name")
    parser.add_argument("-t", "--taluka", required=True, help="Taluka name")
    parser.add_argument("-v", "--village", required=True, help="Village name")
    
    args = parser.parse_args()
    
    base_dir = "output_table"
    output_dir = "index_output"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    all_docs = []
    processed_hashes = set()
    current_doc_id = 1
    
    # Get all years available in the output_table directory
    try:
        years = [y for y in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, y))]
    except FileNotFoundError:
        print(f"❌ Error: {base_dir} directory not found.")
        return

    print(f"🔍 Searching for data for Village: {args.village}, Taluka: {args.taluka}, District: {args.district}")
    
    for year in sorted(years):
        data_path = os.path.join(base_dir, year, args.district, args.taluka, args.village, "data.json")
        
        if os.path.exists(data_path):
            print(f"📖 Processing Year {year}...")
            with open(data_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    processed_year_docs, next_id = process_data(data, processed_hashes, current_doc_id)
                    all_docs.extend(processed_year_docs)
                    current_doc_id = next_id
                except json.JSONDecodeError:
                    print(f"⚠️ Error: Failed to parse JSON in {data_path}")
        else:
            # You might want to skip or log missing years
            pass

    if not all_docs:
        print("❌ No data found for the specified location.")
        return

    # Create output filename
    # Sanitize names for filename (replace spaces with underscores if needed, or keep as is)
    filename = f"{args.district}_{args.taluka}_{args.village}.json".replace("/", "-")
    output_path = os.path.join(output_dir, filename)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    print(f"✅ Done! Created index with {len(all_docs)} unique documents at: {output_path}")

if __name__ == "__main__":
    main()