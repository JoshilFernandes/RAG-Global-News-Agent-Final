import aiohttp
import aiofiles
import os
from datetime import datetime, timedelta

GDELT_BASE_URL = "http://data.gdeltproject.org/events/"
DOWNLOAD_DIR = "data"

async def get_latest_gdelt_url():
    # GDELT filenames are like: 20240517.export.CSV.zip
    today = datetime.utcnow()
    for i in range(7):  # Try up to 7 days back
        date_str = (today - timedelta(days=i)).strftime("%Y%m%d")
        filename = f"{date_str}.export.CSV.zip"
        url = GDELT_BASE_URL + filename
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                if resp.status == 200:
                    # Validate the date is not in the future
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    if file_date > today:
                        print(f"Warning: Skipping future-dated file {filename}")
                        continue
                    return url, filename
    raise Exception("No recent GDELT file found in the last 7 days.")

async def download_gdelt_file():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    url, filename = await get_latest_gdelt_url()
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    # Remove any existing files
    for old_file in os.listdir(DOWNLOAD_DIR):
        if old_file.endswith('.zip') or old_file.endswith('.CSV'):
            try:
                os.remove(os.path.join(DOWNLOAD_DIR, old_file))
            except Exception as e:
                print(f"Error removing old file {old_file}: {e}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(filepath, mode='wb')
                await f.write(await resp.read())
                await f.close()
                print(f"Downloaded: {filename}")
                return filepath
            else:
                raise Exception(f"Failed to download {url}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(download_gdelt_file()) 