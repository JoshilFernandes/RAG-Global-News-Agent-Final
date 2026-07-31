import os
import zipfile
import csv
import sqlite3
from glob import glob
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', os.path.join('data', 'gdelt.db'))
DATA_DIR = 'data'

# GDELT 1.0 event export columns of interest (0-based index).
# Note: raw GDELT files do NOT contain a real "description" field — only
# SOURCEURL (57). We build a human-readable fallback description ourselves
# from the actor/event codes; the app also tries to scrape the real article
# text from SOURCEURL at query time (see agent/tools.py).
COLUMNS = {
    'GLOBALEVENTID': 0,
    'SQLDATE': 1,
    'Actor1Name': 6,
    'Actor2Name': 16,
    'EventCode': 26,
    'EventBaseCode': 27,
    'EventRootCode': 28,
    'ActionGeo_CountryCode': 51,
    'ActionGeo_Lat': 53,
    'ActionGeo_Long': 54,
    'SOURCEURL': 57,
}

# CAMEO event root code -> plain-English verb, used to build a fallback description
EVENT_ROOT_VERBS = {
    "01": "made a public statement about",
    "02": "appealed to",
    "03": "expressed intent to cooperate with",
    "04": "consulted with",
    "05": "engaged in diplomatic cooperation with",
    "06": "engaged in material cooperation with",
    "07": "provided aid to",
    "08": "yielded to",
    "09": "was investigated in relation to",
    "10": "made a demand of",
    "11": "disapproved of",
    "12": "rejected",
    "13": "threatened",
    "14": "was involved in a protest against",
    "15": "exhibited force posture toward",
    "16": "reduced relations with",
    "17": "coerced",
    "18": "assaulted",
    "19": "fought with",
    "20": "used unconventional mass violence against",
}


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS gdelt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    GLOBALEVENTID TEXT,
    SQLDATE TEXT,
    Actor1Name TEXT,
    Actor2Name TEXT,
    EventCode TEXT,
    EventBaseCode TEXT,
    EventRootCode TEXT,
    EventDescription TEXT,
    ActionGeo_CountryCode TEXT,
    ActionGeo_Lat REAL,
    ActionGeo_Long REAL,
    SOURCEURL TEXT
);
"""


def unzip_latest_file():
    zips = sorted(glob(os.path.join(DATA_DIR, '*.zip')), reverse=True)
    if not zips:
        raise FileNotFoundError('No GDELT zip files found. Run downloader.py first.')
    zip_path = zips[0]
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(DATA_DIR)
    csv_name = os.path.basename(zip_path).replace('.zip', '')
    csv_path = os.path.join(DATA_DIR, csv_name)
    print(f"Extracted CSV path: {csv_path}")
    print(f"CSV file size: {os.path.getsize(csv_path)} bytes")
    return csv_path


def build_fallback_description(actor1: str, actor2: str, event_root_code: str) -> str:
    verb = EVENT_ROOT_VERBS.get(event_root_code, "was involved in an event with")
    a1 = actor1 or "An unnamed party"
    a2 = actor2 or "an unnamed party"
    return f"{a1} {verb} {a2}."


def insert_events(csv_path):
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.execute("DELETE FROM gdelt_events")  # clear existing data (SQLite equivalent of TRUNCATE)
    conn.commit()
    print("Cleared existing data from gdelt_events table")

    count = 0
    skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        first_row = next(reader)
        print(f"Number of columns in CSV: {len(first_row)}")
        print(f"First row sample: {first_row[:5]}")

        batch = []
        for row in reader:
            if len(row) < max(COLUMNS.values()) + 1:
                skipped += 1
                continue
            try:
                vals = {k: (row[idx] if row[idx] else None) for k, idx in COLUMNS.items()}

                # Format date YYYYMMDD -> YYYY-MM-DD
                sqldate = vals['SQLDATE']
                if sqldate:
                    sqldate = f"{sqldate[:4]}-{sqldate[4:6]}-{sqldate[6:]}"

                # Country code straight from GDELT (FIPS 10-4 standard).
                # No allowlist filter here — we keep events from every country,
                # since restricting to a small hardcoded list only threw away data.
                country_code = vals['ActionGeo_CountryCode']

                # Validate date is not in the future
                if sqldate:
                    event_date = datetime.strptime(sqldate, "%Y-%m-%d")
                    if event_date > datetime.now():
                        skipped += 1
                        continue

                description = build_fallback_description(
                    vals['Actor1Name'], vals['Actor2Name'], vals['EventRootCode']
                )

                batch.append((
                    vals['GLOBALEVENTID'], sqldate, vals['Actor1Name'], vals['Actor2Name'],
                    vals['EventCode'], vals['EventBaseCode'], vals['EventRootCode'],
                    description, country_code, vals['ActionGeo_Lat'], vals['ActionGeo_Long'],
                    vals['SOURCEURL'],
                ))
                count += 1
                if count % 1000 == 0:
                    print(f"Processed {count} rows...")
                    cur.executemany(
                        """INSERT INTO gdelt_events
                           (GLOBALEVENTID, SQLDATE, Actor1Name, Actor2Name, EventCode,
                            EventBaseCode, EventRootCode, EventDescription,
                            ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long, SOURCEURL)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        batch
                    )
                    conn.commit()
                    batch = []
            except Exception as e:
                print(f"Error processing row: {e}")
                print(f"Problematic row: {row[:5]}")
                skipped += 1

        if batch:
            cur.executemany(
                """INSERT INTO gdelt_events
                   (GLOBALEVENTID, SQLDATE, Actor1Name, Actor2Name, EventCode,
                    EventBaseCode, EventRootCode, EventDescription,
                    ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long, SOURCEURL)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch
            )
            conn.commit()

    conn.close()
    print(f"Total rows inserted: {count}")
    print(f"Total rows skipped: {skipped}")


if __name__ == "__main__":
    csv_path = unzip_latest_file()
    insert_events(csv_path)
