import aiosqlite
import os
from datetime import datetime, timedelta
import aiohttp
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv
from vectorstore import VectorStore

# Load environment variables
load_dotenv()

# SQLite database path (no server to install/run — just a local file)
SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', os.path.join('data', 'gdelt.db'))

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


async def get_connection():
    """Open (and lazily initialize) the SQLite database."""
    os.makedirs(os.path.dirname(SQLITE_DB_PATH) or '.', exist_ok=True)
    conn = await aiosqlite.connect(SQLITE_DB_PATH)
    await conn.execute(CREATE_TABLE_SQL)
    await conn.commit()
    return conn


async def extract_news_content(url: str) -> str:
    """Extract meaningful content from a news article URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return ""

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Remove unwanted elements
                for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    element.decompose()

                # Try to find the main article content
                article = soup.find('article') or soup.find(class_=re.compile(r'article|content|story|main'))
                if article:
                    text = article.get_text(separator=' ', strip=True)
                else:
                    # Fallback to body text if no article found
                    text = soup.body.get_text(separator=' ', strip=True) if soup.body else ""

                # Clean up the text
                text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space

                # Extract first few sentences (up to 3)
                sentences = re.split(r'(?<=[.!?])\s+', text)
                summary = ' '.join(sentences[:3])

                return summary.strip()

    except Exception as e:
        print(f"Error extracting content from {url}: {str(e)}")
        return ""


def _row_to_dict(row: tuple) -> dict:
    """Map a raw SELECT row to the event dict shape the rest of the app expects.

    Row order: SQLDATE, Actor1Name, Actor2Name, EventCode, EventBaseCode,
    EventRootCode, ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long,
    SOURCEURL, EventDescription
    """
    date_val = row[0]
    if isinstance(date_val, datetime):
        date_str = date_val.strftime("%Y-%m-%d")
    else:
        date_str = str(date_val) if date_val else ""

    return dict(
        date=date_str,
        actor1=row[1] or "Unknown",
        actor2=row[2] or "Unknown",
        event_code=row[3],
        event_base_code=row[4],
        event_root_code=row[5],
        country=row[6],
        latitude=row[7],
        longitude=row[8],
        source_url=row[9],
        db_description=row[10] or "",
    )


async def _enrich_with_scraped_content(results: list) -> list:
    """For each event, try to fetch a real description from the source URL.
    Falls back to the description already stored in the DB if scraping fails."""
    for event in results:
        url = event.get("source_url")
        scraped = await extract_news_content(url) if url else ""
        fallback = event.pop("db_description", "")
        event["description"] = scraped or fallback or ""
    return results


SELECT_COLUMNS = """
    SQLDATE, Actor1Name, Actor2Name, EventCode, EventBaseCode, EventRootCode,
    ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long, SOURCEURL, EventDescription
"""


async def search_events_by_country(country_code: str, limit: int = 20):
    print(f"Searching events for country: {country_code}")  # Debug print
    query = f"""
        SELECT {SELECT_COLUMNS}
        FROM gdelt_events
        WHERE ActionGeo_CountryCode = ?
        ORDER BY SQLDATE DESC
        LIMIT ?
    """
    results = []
    conn = await get_connection()
    try:
        async with conn.execute(query, (country_code, limit)) as cur:
            rows = await cur.fetchall()
            print(f"Found {len(rows)} rows")  # Debug print
            for row in rows:
                results.append(_row_to_dict(row))
        return await _enrich_with_scraped_content(results)
    except Exception as e:
        print(f"Error in search_events_by_country: {str(e)}")  # Debug print
        raise
    finally:
        await conn.close()


async def search_events_by_keyword(keyword: str, limit: int = 20):
    print(f"Searching events for keyword: {keyword}")  # Debug print
    query = f"""
        SELECT {SELECT_COLUMNS}
        FROM gdelt_events
        WHERE Actor1Name LIKE ? OR Actor2Name LIKE ? OR EventCode LIKE ? OR EventDescription LIKE ?
        ORDER BY SQLDATE DESC
        LIMIT ?
    """
    kw = f"%{keyword}%"
    results = []
    conn = await get_connection()
    try:
        async with conn.execute(query, (kw, kw, kw, kw, limit)) as cur:
            rows = await cur.fetchall()
            print(f"Found {len(rows)} rows")  # Debug print
            for row in rows:
                results.append(_row_to_dict(row))
        return await _enrich_with_scraped_content(results)
    except Exception as e:
        print(f"Error in search_events_by_keyword: {str(e)}")  # Debug print
        raise
    finally:
        await conn.close()


async def search_events_by_date(start_date: str, end_date: str, limit: int = 20):
    print(f"Searching events from {start_date} to {end_date}")  # Debug print
    query = f"""
        SELECT {SELECT_COLUMNS}
        FROM gdelt_events
        WHERE SQLDATE BETWEEN ? AND ?
        ORDER BY SQLDATE DESC
        LIMIT ?
    """
    results = []
    conn = await get_connection()
    try:
        async with conn.execute(query, (start_date, end_date, limit)) as cur:
            rows = await cur.fetchall()
            print(f"Found {len(rows)} rows")  # Debug print
            for row in rows:
                results.append(_row_to_dict(row))
        return await _enrich_with_scraped_content(results)
    except Exception as e:
        print(f"Error in search_events_by_date: {str(e)}")  # Debug print
        raise
    finally:
        await conn.close()


async def search_events_by_semantic(query: str, top_k: int = 5):
    """Return top_k events semantically matching query using FAISS + S-BERT."""
    try:
        vs = VectorStore()
        hits = vs.search(query, top_k)
        if not hits:
            return []
        ids = [h[0] for h in hits]

        # Query SQLite for the rows with these ids
        conn = await get_connection()
        placeholders = ",".join("?" for _ in ids)
        q = f"""
            SELECT {SELECT_COLUMNS}, id
            FROM gdelt_events
            WHERE id IN ({placeholders})
        """
        try:
            async with conn.execute(q, ids) as cur:
                rows = await cur.fetchall()
                results = []
                for row in rows:
                    # row = (SQLDATE, Actor1Name, ..., EventDescription, id)
                    ev = _row_to_dict(row[:-1])
                    ev['id'] = row[-1]
                    results.append(ev)

            # Preserve FAISS ranking order
            id_to_event = {ev['id']: ev for ev in results}
            ordered = [id_to_event[i] for i in ids if i in id_to_event]

            return await _enrich_with_scraped_content(ordered)
        finally:
            await conn.close()
    except Exception as e:
        print(f"Error in semantic search: {str(e)}")
        return []
