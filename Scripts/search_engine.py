import json
import re
import os
import argparse

# ===================================================================
# PROPERTY NUMBER EXTRACTION
# Each entry: (label, [list of regex patterns])
# The patterns are tried in order; all matches are collected.
# ===================================================================

PROPERTY_PATTERNS = [

    # ── गट / Gut Number ─────────────────────────────────────────────
    ("gut_number", [
        r"(?:गट|gut)\s*(?:क्र(?:मांक)?|नं|नंबर|number|no\.?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"ग\.\s*नं\.?\s*([\d]+(?:[/\-\.]\d+)*)",
        r"ग\s+नं\.?\s*([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── भुमापन / Bhumapan Number ────────────────────────────────────
    ("bhumapan_number", [
        r"(?:भुमापन|भूमापन|bhumapan)\s*(?:क्र(?:मांक)?|नं|नंबर|no\.?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"(?:भुमापन|भूमापन)\s*क्र\.?\s*([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── सर्व्हे / Survey Number ─────────────────────────────────────
    ("survey_number", [
        # Marathi: सर्व्हे नं, सर्वे नं, स.न., स.नं., सर्व्हे क्र
        r"(?:सर्व[्व]{0,2}हे|सर्वे|सर्वेक्षण)\s*(?:नं|नंबर|क्र(?:मांक)?|no\.?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\w+)*)",
        r"स\.?\s*न\.?\s*(?:ं)?\s*([\d]+(?:[/\-\.]\w+)*)",
        r"स\.?\s*ना\.?\s*([\d]+(?:[/\-\.]\w+)*)",
        # English: S.No, S.N, Survey No, SurveyNo
        r"[Ss](?:urvey)?\s*\.?\s*[Nn][Oo]?\.?\s*([\d]+(?:[/\-\.]\w+)*)",
        r"[Ss]\.?\s*[Nn](?:o)?\.?\s*([\d]+(?:[/\-\.]\w+)*)",
    ]),

    # ── CTS / City Survey Number ─────────────────────────────────────
    ("cts_number", [
        r"(?:CTS|cts|सिटी\s*सर्व्हे|सि\.?टी\.?\s*सर्व्हे|सि\.?\s*स\.?)\s*(?:नं|नंबर|no\.?|क्र(?:मांक)?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"(?:city\s*survey|citysurvey)\s*(?:no\.?|number)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"सि\.?\s*स\.\s*नं\.?\s*([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── प्लॉट / Plot Number ──────────────────────────────────────────
    ("plot_number", [
        r"(?:प्लॉट|plot|खाजगी\s*प्लॉट)\s*(?:नं|नंबर|no\.?|क्र(?:मांक)?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── फ्लॅट / Flat Number ──────────────────────────────────────────
    ("flat_number", [
        # Marathi variants: फ्लॅट, फ़्लॅट, फ्लेट, फ्लॅट नं, फ. नं.
        r"(?:फ[्ष़]?\s*ल[ॅए]\s*ट|flat|apartment)\s*(?:नं|नंबर|no\.?|क्र(?:मांक)?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"फ\.\s*नं\.?\s*([\d]+(?:[/\-\.]\d+)*)",
        r"Apartment/Flat\s*No[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── शॉप / Shop Number ────────────────────────────────────────────
    ("shop_number", [
        r"(?:शॉप|शाप|shop|दुकान)\s*(?:नं|नंबर|no\.?|क्र(?:मांक)?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"Shop\s*No[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── सदनिका / Sadanika Number ─────────────────────────────────────
    ("sadanika_number", [
        r"सदनिका\s*(?:नं|नंबर|क्र(?:मांक)?|no\.?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── मिळकत / Milkat Number ────────────────────────────────────────
    # Only match when an explicit number keyword immediately follows मिळकत
    # (avoids false positives from "मिळकत गट नं..." which is a gut number)
    ("milkat_number", [
        r"मिळकत\s+क्र(?:मांक)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"मिळकत\s+नं(?:बर)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\d+)*)",
        r"मिळकत\s+क्र\.\s*([\d]+(?:[/\-\.]\d+)*)",
    ]),

    # ── ब्लॉक / Block ────────────────────────────────────────────────
    ("block_number", [
        r"(?:ब्लॉक|block)\s*(?:नं|नंबर|no\.?)?[:\s\.]{0,3}([\w]+)",
    ]),

    # ── हिस्सा / Hissa Number ─────────────────────────────────────────
    ("hissa_number", [
        r"(?:हिस्सा|हिश्या|हिस्स|हिश्स|hissa)\s*(?:नं|नंबर|no\.?)?[:\s\.]{0,3}([\d]+(?:[/\-\.]\w+)*)",
        r"Hissa\s*No\.?\s*([\d]+(?:[/\-\.]\w+)*)",
    ]),
]

# ===================================================================
# VALIDATION
# ===================================================================
INVALID_VALUES = {"00", "0", "no", "n", ""}

def is_valid_value(val):
    if not val:
        return False
    val_stripped = val.strip().lower()
    if val_stripped in INVALID_VALUES:
        return False
    if len(val_stripped) == 1 and val_stripped.isdigit():
        return False
    return True

# ===================================================================
# EXTRACT ALL PROPERTY NUMBERS
# Returns a list of dicts: [{"type": "gut_number", "value": "234"}, ...]
# ===================================================================
def extract_property_numbers(text):
    results = []
    seen = set()  # avoid exact duplicates (type, value)

    for label, patterns in PROPERTY_PATTERNS:
        for pattern in patterns:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            for match in matches:
                value = match.strip()
                if not is_valid_value(value):
                    continue
                key = (label, value)
                if key not in seen:
                    seen.add(key)
                    results.append({"type": label, "value": value})

    return results

# ===================================================================
# PROCESS DATA
# ===================================================================
def process_data(data, current_doc_id):
    docs = []

    meta = data.get("meta", {})
    free_text_blocks = data.get("free_text", {})

    for block in free_text_blocks.values():
        rows = block.get("rows", [])

        for row in rows:
            cols = row.get("columns", [])
            row_url = row.get("url", "").strip()

            if len(cols) < 8:
                continue

            info_text = cols[7]

            if not info_text or len(info_text) < 10:
                continue

            property_numbers = extract_property_numbers(info_text)

            if not property_numbers:
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
                "property_numbers": property_numbers,
                "pdf_link": row_url,
                "village": meta.get("village_name"),
                "taluka": meta.get("tal_name"),
                "district": meta.get("dist_name"),
                "year": meta.get("yearsel")
            })

            current_doc_id += 1

    return docs, current_doc_id

# ===================================================================
# MAIN
# ===================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Index IGR data for all villages in a taluka across all years."
    )
    parser.add_argument("-d", "--district", required=True, help="District name (e.g. पुणे)")
    parser.add_argument("-t", "--taluka",   required=True, help="Taluka name (e.g. मावळ)")

    args = parser.parse_args()

    base_dir   = "output_table"
    output_dir = "index_output"

    os.makedirs(output_dir, exist_ok=True)

    try:
        years = sorted([
            y for y in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, y)) and y.isdigit()
        ])
    except FileNotFoundError:
        print(f"❌ Error: '{base_dir}' directory not found.")
        return

    print(f"🔍 District: {args.district} | Taluka: {args.taluka}")
    print(f"📅 Years found in output_table: {', '.join(years) if years else 'none'}")

    # 1. Collect all unique villages across all years for this district/taluka
    villages = set()
    for year in years:
        taluka_path = os.path.join(base_dir, year, args.district, args.taluka)
        if os.path.exists(taluka_path):
            try:
                v_list = [v for v in os.listdir(taluka_path) 
                         if os.path.isdir(os.path.join(taluka_path, v))]
                villages.update(v_list)
            except Exception as e:
                print(f"      ⚠️  Error reading {taluka_path}: {e}")

    if not villages:
        print(f"❌ No villages found for District: {args.district}, Taluka: {args.taluka}")
        return

    sorted_villages = sorted(list(villages))
    print(f"🏘️  Found {len(sorted_villages)} villages to process.\n")

    for village in sorted_villages:
        print(f"🚀 Processing Village: {village}")
        all_docs = []
        current_doc_id = 1

        for year in years:
            data_path = os.path.join(
                base_dir, year, args.district, args.taluka, village, "data.json"
            )

            if not os.path.exists(data_path):
                continue

            print(f"   📖 Processing Year {year} → {data_path}")
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                year_docs, current_doc_id = process_data(data, current_doc_id)
                all_docs.extend(year_docs)
                print(f"      ✔  Added {len(year_docs)} documents (village total: {len(all_docs)})")
            except json.JSONDecodeError:
                print(f"      ⚠️  Failed to parse JSON in {data_path}")
            except Exception as e:
                print(f"      ⚠️  Error processing {data_path}: {e}")

        if not all_docs:
            print(f"   ⚠️  No documents found for {village}. skipping output.")
            continue

        # Output as: index_output/<district>/<taluka>/<village>/data.json
        village_dir = os.path.join(output_dir, args.district, args.taluka, village)
        os.makedirs(village_dir, exist_ok=True)
        output_path = os.path.join(village_dir, "data.json")

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_docs, f, ensure_ascii=False, indent=2)
            print(f"   ✅ Saved {len(all_docs)} unique documents → {output_path}\n")
        except Exception as e:
            print(f"   ❌ Error saving to {output_path}: {e}")

    print(f"\n✨ All villages in {args.taluka} have been processed.")

if __name__ == "__main__":
    main()