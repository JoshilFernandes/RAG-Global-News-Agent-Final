"""
Fastest possible version: builds the semantic index using ONLY the
descriptions already stored in SQLite (no web scraping, no network calls).

This is instant even for tens of thousands of rows, and is enough to get
semantic search working right now. You can layer in real scraped article
text later (with build_vector_index_fast.py) to improve quality further --
re-running it won't duplicate anything already indexed.

Usage:
    python build_vector_index_instant.py
"""
import os
import sqlite3
from dotenv import load_dotenv

from vectorstore import VectorStore

load_dotenv()

SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', os.path.join('data', 'gdelt.db'))


def main():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gdelt_vectors (
            event_id INTEGER PRIMARY KEY
        );
    """)
    conn.commit()

    rows = conn.execute("""
        SELECT id, EventDescription, SOURCEURL
        FROM gdelt_events
        WHERE id NOT IN (SELECT event_id FROM gdelt_vectors)
    """).fetchall()

    print(f"Found {len(rows)} unindexed events. Embedding descriptions (no scraping)...")

    if not rows:
        print("Nothing new to index. Done.")
        conn.close()
        return

    vs = VectorStore()
    pairs = []
    metadata = {}
    for event_id, description, source_url in rows:
        text = description or ""
        if len(text) < 10:
            continue
        pairs.append((event_id, text))
        metadata[event_id] = {"source_url": source_url}

    vs.bulk_add(pairs, metadatas=metadata)
    vs.save()

    conn.executemany(
        "INSERT OR IGNORE INTO gdelt_vectors(event_id) VALUES (?)",
        [(int(r[0]),) for r in rows],
    )
    conn.commit()
    conn.close()

    print(f"Done. Indexed {len(pairs)} events (skipped {len(rows) - len(pairs)} with empty/too-short text).")
    print("You can improve quality later by running build_vector_index_fast.py to layer in real scraped article text.")


if __name__ == "__main__":
    main()
