import os
import sqlite3
from vectorstore import VectorStore
from agent.tools import extract_news_content  # reuse scraper
from dotenv import load_dotenv
from agent.tools import extract_news_content as async_extract_news_content
import asyncio

load_dotenv()

SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', os.path.join('data', 'gdelt.db'))

# Synchronous scraper wrapper using requests + BeautifulSoup (fallback when async scraper isn't convenient)
import requests
from bs4 import BeautifulSoup
import re

def sync_extract_news_content(url: str) -> str:
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return ""
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        article = soup.find('article') or soup.find(class_=re.compile(r'article|content|story|main'))
        if article:
            text = article.get_text(separator=' ', strip=True)
        else:
            text = soup.body.get_text(separator=' ', strip=True) if soup.body else ""
        text = re.sub(r'\s+', ' ', text)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        summary = ' '.join(sentences[:3])
        return summary.strip()
    except Exception:
        return ""


def get_unindexed_events(conn, limit=None):
    # Create tracking table if not exists
    conn.execute("""
    CREATE TABLE IF NOT EXISTS gdelt_vectors (
        event_id INTEGER PRIMARY KEY
    );
    """)
    # Select events not in gdelt_vectors
    q = """
    SELECT id, EventDescription, SOURCEURL
    FROM gdelt_events
    WHERE id NOT IN (SELECT event_id FROM gdelt_vectors)
    """
    if limit:
        q += f" LIMIT {int(limit)}"
    cur = conn.execute(q)
    return cur.fetchall()


def mark_indexed(conn, event_ids):
    conn.executemany("INSERT OR IGNORE INTO gdelt_vectors(event_id) VALUES (?)", [(int(i),) for i in event_ids])
    conn.commit()


def main(batch_size=512):
    conn = sqlite3.connect(SQLITE_DB_PATH)
    vs = VectorStore()

    rows = get_unindexed_events(conn)
    pairs = []
    metadata = {}
    ids_to_mark = []

    for row in rows:
        event_id, fallback_desc, source_url = row
        text = fallback_desc or ""
        # Prefer scraped text if available (best-effort, may be slower)
        scraped = ""
        # Try async scraper first if available
        try:
            # call async scraper
            scraped = asyncio.run(async_extract_news_content(source_url)) if source_url else ""
        except Exception:
            try:
                scraped = sync_extract_news_content(source_url) if source_url else ""
            except Exception:
                scraped = ""

        if scraped:
            text = scraped
        if not text or len(text) < 20:
            # skip very short items
            continue
        pairs.append((event_id, text))
        metadata[event_id] = {"source_url": source_url}
        ids_to_mark.append(event_id)

        # Bulk add in batches
        if len(pairs) >= batch_size:
            vs.bulk_add(pairs, metadatas=metadata)
            vs.save()
            mark_indexed(conn, ids_to_mark)
            pairs = []
            metadata = {}
            ids_to_mark = []

    # final batch
    if pairs:
        vs.bulk_add(pairs, metadatas=metadata)
        vs.save()
        mark_indexed(conn, ids_to_mark)

    conn.close()
    print("Vector index build complete.")


if __name__ == "__main__":
    main()
