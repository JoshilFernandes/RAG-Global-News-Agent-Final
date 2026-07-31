import os
from openai import AsyncOpenAI
import json
from datetime import datetime, timedelta
from . import tools
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables
load_dotenv()

# Initialize Groq client (free, online, OpenAI-compatible API — no local model needed)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
        "and add it to your .env file."
    )

client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
    timeout=300.0  # Increased timeout to 300 seconds
)

# Free Groq model. See https://console.groq.com/docs/models for current options.
LLM_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# GDELT Event Code Descriptions
EVENT_CODES = {
    "01": "MAKE PUBLIC STATEMENT",
    "02": "APPEAL",
    "03": "EXPRESS INTENT TO COOPERATE",
    "04": "CONSULT",
    "05": "ENGAGE IN DIPLOMATIC COOPERATION",
    "06": "ENGAGE IN MATERIAL COOPERATION",
    "07": "PROVIDE AID",
    "08": "YIELD",
    "09": "INVESTIGATE",
    "10": "DEMAND",
    "11": "DISAPPROVE",
    "12": "REJECT",
    "13": "THREATEN",
    "14": "PROTEST",
    "15": "EXHIBIT FORCE POSTURE",
    "16": "REDUCE RELATIONS",
    "17": "COERCE",
    "18": "ASSAULT",
    "19": "FIGHT",
    "20": "USE UNCONVENTIONAL MASS VIOLENCE"
}

# Event categories with specific event codes
EVENT_CATEGORIES = {
    # Political and Government
    "political": {"01", "02", "03", "04", "05", "10", "11", "12"},  # Public statements, appeals, consultations
    "government": {"01", "02", "03", "04", "05", "10", "11", "12"},  # Government actions and statements
    "election": {"01", "02", "03", "04", "05"},  # Election-related events
    "legislation": {"01", "02", "03", "04", "05", "10", "11", "12"},  # Law-making and policy
    
    # Sports and Entertainment
    "sports": {"01", "02", "03", "04", "05", "06", "07"},  # Sports events and announcements
    "entertainment": {"01", "02", "03", "04", "05"},  # Entertainment news
    "athletics": {"01", "02", "03", "04", "05", "06", "07"},  # Sports competitions
    "games": {"01", "02", "03", "04", "05", "06", "07"},  # Sports and games
    
    # International Relations
    "diplomatic": {"03", "04", "05", "06"},  # Diplomatic relations
    "geopolitical": {"01", "02", "03", "04", "05", "06", "10", "11", "12", "13", "14", "15", "16", "17"},
    "international": {"01", "02", "03", "04", "05", "06", "10", "11", "12", "13", "14", "15", "16", "17"},
    "foreign_relations": {"03", "04", "05", "06", "10", "11", "12"},
    
    # Conflict and Security
    "war": {"18", "19", "20"},  # Direct military conflict
    "conflict": {"13", "14", "15", "16", "17"},  # Tensions and conflicts
    "military": {"15", "16", "17", "18", "19", "20"},  # Military actions
    "security": {"13", "14", "15", "16", "17", "18", "19", "20"},
    "terrorism": {"18", "19", "20"},  # Terrorist activities
    
    # Social and Humanitarian
    "humanitarian": {"02", "07"},  # Aid and assistance
    "social": {"01", "02", "03", "04", "05", "07"},  # Social issues
    "protest": {"14"},  # Protests and demonstrations
    "civil_rights": {"01", "02", "03", "04", "05", "14"},
    "refugee": {"02", "07"},  # Refugee-related events
    
    # Economic
    "economic": {"01", "02", "03", "04", "05", "06", "07"},  # Economic events
    "trade": {"03", "04", "05", "06"},  # Trade relations
    "business": {"01", "02", "03", "04", "05", "06", "07"},
    "finance": {"01", "02", "03", "04", "05", "06", "07"},
    
    # Environmental and Natural Events
    "disaster": {"07", "08", "09"},  # Natural disasters
    "environmental": {"01", "02", "03", "04", "05", "07"},
    "climate": {"01", "02", "03", "04", "05", "07"},
    "natural_disaster": {"07", "08", "09"},
    
    # Legal and Justice
    "legal": {"01", "02", "03", "04", "05", "09", "10", "11", "12"},
    "judicial": {"01", "02", "03", "04", "05", "09", "10", "11", "12"},
    "crime": {"09", "18", "19", "20"},
    "investigation": {"09"},
    
    # Health and Science
    "health": {"01", "02", "03", "04", "05", "07"},
    "medical": {"01", "02", "03", "04", "05", "07"},
    "science": {"01", "02", "03", "04", "05"},
    "technology": {"01", "02", "03", "04", "05"},
    
    # Education and Culture
    "education": {"01", "02", "03", "04", "05"},
    "cultural": {"01", "02", "03", "04", "05"},
    
    # Infrastructure and Development
    "infrastructure": {"01", "02", "03", "04", "05", "06", "07"},
    "development": {"01", "02", "03", "04", "05", "06", "07"},
    "transportation": {"01", "02", "03", "04", "05", "06", "07"},
    "construction": {"01", "02", "03", "04", "05", "06", "07"},
    
    # General News Categories
    "breaking": {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"},
    "latest": {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"},
    "major": {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"},
    "significant": {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"}
}

SYSTEM_PROMPT = """
You are a professional news editor who reports events from the database. Your task is to:
1. ONLY report the exact events provided - DO NOT make up or infer additional details
2. If events are provided, you MUST report them - do not say "no events found" if events are given
3. Only say "No events found in the database" if the input explicitly states "No events found in the database"
4. Keep responses clear and factual
5. If you see dates in 2025, these are valid dates - do not filter them out
6. ALWAYS report the events that are provided to you
7. DO NOT add any information that is not explicitly stated in the events
8. Rephrase each event into exactly 2 clear, professional sentences that:
   - Keep all facts, numbers, dates, and names exactly the same
   - Remove any UI elements, social media buttons, or unnecessary text
   - Make the language more natural and flowing
   - Do not add or remove any information
   - Do not make assumptions about implications
9. DO NOT make assumptions about the meaning or implications of events
10. DO NOT generate generic or repetitive content
11. DO NOT add any content that wasn't in the original text

Example format for found events:
"Latest News from [Country]:

• [Date]
  [First sentence with key facts and context]
  [Second sentence with additional details ]
  [Source URL]"

Example for no events:
If the input is "No events found in the database", respond with:
"No events found in the database"

Important: If you see any events in the input, you MUST report them, even if they are from 2025.
DO NOT say "no events found" if events are provided to you.
DO NOT add any information that is not explicitly stated in the events.
DO NOT generate generic or repetitive content."""

# Tool schema for OpenAI function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_by_keyword",
            "description": "Searches news headlines by a given keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Keyword to search for in news headlines."}
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_country",
            "description": "Searches news using an ISO2 country code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country_code": {"type": "string", "description": "ISO2 country code (e.g., 'IN', 'US')."}
                },
                "required": ["country_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_date_range",
            "description": "Fetches news between two dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)."},
                    "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)."}
                },
                "required": ["start_date", "end_date"]
            }
        }
    }
]

# Map tool names to actual Python functions
TOOL_MAP = {
    "search_by_keyword": tools.search_events_by_keyword,
    "search_by_country": tools.search_events_by_country,
    "search_by_date_range": tools.search_events_by_date,
}

def get_date_range(days: int = 30) -> tuple[str, str]:
    """Get start and end dates for a given number of days."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

def extract_url(text: str) -> str:
    """Extract URL from text."""
    import re
    # Look for URLs in the text
    urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)
    if urls:
        # Clean up the URL
        url = urls[0].strip('., ')
        # Remove any trailing punctuation
        url = re.sub(r'[.,;:!?]+$', '', url)
        return url
    return ""

def clean_description(desc: str) -> str:
    """Clean up the description text."""
    if not desc:
        return ""
        
    # Remove URLs from the text
    desc = ' '.join(word for word in desc.split() if not word.startswith('http'))
    
    # Remove UI elements and social media buttons
    ui_elements = ['Copy', 'link', 'Email', 'Facebook', 'Twitter', 'Telegram', 
                  'LinkedIn', 'WhatsApp', 'Reddit', 'READ', 'LATER', 'Remove', 
                  'SEE', 'ALL', 'PRINT', 'Share', 'Tweet', 'Updated', 'Posted',
                  'MOMENT', 'VIEW PHOTOS', 'Prev', 'Next', 'By:', 'Staff',
                  'Anchor/Reporter', 'copyShortcut', 'Sign in', 'Welcome!',
                  'Log into your account', 'your username', 'your password',
                  'Forgot your password?', 'Get help', 'Create an account',
                  'Listen to article', 'Join our Whatsapp channel', 'Published',
                  'PID', '1x', '1.2x', '1.5x', 'Share', 'Facebook', 'Twitter',
                  'Email', 'Pinterest', 'LinkedIn', 'Tumblr', 'VKontakte', 'WhatsApp']
    
    for element in ui_elements:
        desc = desc.replace(element, '')
    
    # Remove timestamps and dates in various formats
    import re
    desc = re.sub(r'\d{1,2}:\d{2}\s*(?:AM|PM|CDT|IST)?', '', desc)
    desc = re.sub(r'Updated:?\s*', '', desc)
    desc = re.sub(r'Posted:?\s*', '', desc)
    desc = re.sub(r'Published\s*-\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM|CDT|IST)?', '', desc)
    
    # Remove author names and bylines
    desc = re.sub(r'By\s+[A-Za-z\s]+', '', desc)
    desc = re.sub(r'[A-Za-z\s]+\s+By', '', desc)
    
    # Remove premium tags and other UI text
    desc = desc.replace('Premium', '')
    desc = desc.replace('Advertisement', '')
    
    # Clean up extra whitespace and punctuation
    desc = ' '.join(desc.split())
    desc = desc.strip('., ')
    
    return desc

def format_events(events: List[Dict], event_type: str = None, year: int = None) -> str:
    """Format events into a readable string."""
    if not events:
        return "No events found in the database"
    
    # Filter events by type if specified
    if event_type and event_type in EVENT_CATEGORIES:
        filtered_events = []
        for event in events:
            event_code = event.get('event_code', '')[:2]
            if event_code in EVENT_CATEGORIES[event_type]:
                filtered_events.append(event)
        events = filtered_events
    
    # Filter events by year if specified
    if year:
        events = [e for e in events if e.get('date', '').startswith(str(year))]
    
    # Remove duplicates. GDELT frequently logs the same news article as several
    # rows with different actor pairings — if two events point at the exact
    # same article URL, they're the same story, so dedupe on that first.
    unique_events = {}
    for event in events:
        url = event.get('source_url')
        key = url if url else (
            event.get('date'),
            event.get('actor1') if event.get('actor1') != 'Unknown' else '',
            event.get('actor2') if event.get('actor2') != 'Unknown' else '',
            event.get('event_code'),
            event.get('country'),
        )
        if key not in unique_events:
            unique_events[key] = event
    
    events = list(unique_events.values())
    
    # Sort events by date (most recent first) and take only the first 5
    events.sort(key=lambda x: x.get('date', ''), reverse=True)
    events = events[:5]  # Limit to 5 most recent events
    
    # Format the output
    result = []
    
    for event in events:
        # Skip less relevant events
        if event.get('actor1') in ['HOSPITAL', 'AIRLINE', 'COMPANY']:
            continue

        # Format timestamp
        timestamp = event.get('date', '')
        if not timestamp:
            continue

        # Get and clean description
        desc = clean_description(event.get('description', ''))

        # Skip if no meaningful description
        if not desc or len(desc) < 10:
            continue

        # Get source URL
        source_url = event.get('source_url', '')
        if not source_url:
            continue

        # Add the formatted event
        result.append(f"• {timestamp}")
        result.append(f"  {desc}")
        result.append(f"  {source_url}")
        result.append("")
    
    return "\n".join(result)

async def process_with_llm(content: str, max_chunk_size: int = 6000) -> str:
    """Process content with LLM in chunks if needed."""
    try:
        # If content is small enough, process it directly
        if len(content) <= max_chunk_size:
            response = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            return response.choices[0].message.content.strip()
        
        # Split content into chunks
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in content.split('\n'):
            line_size = len(line)
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        # Process each chunk
        processed_chunks = []
        for chunk in chunks:
            try:
                response = await client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": chunk}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                processed_chunks.append(response.choices[0].message.content.strip())
            except Exception as e:
                print(f"Error processing chunk: {str(e)}")
                processed_chunks.append(chunk)  # Keep original if processing fails
        
        return '\n\n'.join(processed_chunks)
    
    except Exception as e:
        print(f"Error in process_with_llm: {str(e)}")
        return content  # Return original content if processing fails

async def agent_chat(user_query: str) -> str:
    try:
        print("Starting agent chat...")
        
        # Determine which tool to use based on the query
        tool_name = None
        tool_args = {}
        requested_type = None
        requested_count = None
        requested_year = None
        
        # Check for specific event type requests
        for event_type in EVENT_CATEGORIES.keys():
            if event_type in user_query.lower():
                requested_type = event_type
                break
        
        # Check for specific count requests
        import re
        count_match = re.search(r'(\d+)\s+(?:of\s+)?(?:the\s+)?(?:most\s+)?(?:recent\s+)?(?:events|news)', user_query.lower())
        if count_match:
            requested_count = int(count_match.group(1))
        else:
            requested_count = 5  # Default to 5 events if no count specified
        
        # Check for year requests
        year_match = re.search(r'(?:in|from|during|for)\s+(\d{4})', user_query.lower())
        if year_match:
            requested_year = year_match.group(1)
        
        # Extract country code if mentioned.
        # IMPORTANT: GDELT's ActionGeo_CountryCode field uses FIPS 10-4 codes,
        # NOT the more common ISO 3166-1 codes. Several countries differ between
        # the two standards (e.g. Germany is "GM" in FIPS, not "DE").
        country_mapping = {
            "india": "IN",
            "us": "US",
            "united states": "US",
            "uk": "UK",
            "united kingdom": "UK",
            "china": "CH",
            "russia": "RS",
            "france": "FR",
            "germany": "GM",
            "japan": "JA",
            "australia": "AS",
            "canada": "CA",
            "brazil": "BR"
        }
        
        # Check for country mentions (exact match first)
        country_code = None
        for country, code in country_mapping.items():
            if country in user_query.lower():
                country_code = code
                break

        # Fall back to typo-tolerant matching (e.g. "Germnay" -> "Germany")
        if not country_code:
            import difflib
            words = re.findall(r'[a-zA-Z]+', user_query.lower())
            country_names = list(country_mapping.keys())
            for word in words:
                if len(word) < 4:
                    continue  # skip short words like "in", "us" to avoid false matches
                close = difflib.get_close_matches(word, country_names, n=1, cutoff=0.75)
                if close:
                    country_code = country_mapping[close[0]]
                    print(f"Typo-corrected '{word}' -> '{close[0]}' ({country_code})")
                    break
        
        if country_code:
            print(f"Using search_by_country for {country_code}...")
            tool_name = "search_by_country"
            tool_args = {"country_code": country_code}
        elif "recent" in user_query.lower() or "latest" in user_query.lower():
            print("Using search_by_date_range for recent events...")
            tool_name = "search_by_date_range"
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Last 7 days instead of 30
            tool_args = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }
        else:
            # Use keyword search with the event type if specified
            keyword = requested_type if requested_type else "news"
            print(f"Using search_by_keyword with '{keyword}'...")
            tool_name = "search_by_keyword"
            tool_args = {"keyword": keyword}
        
        print(f"Selected tool: {tool_name}")
        print(f"Tool arguments: {tool_args}")
        
        # Execute the tool
        if tool_name in TOOL_MAP:
            print(f"Executing {tool_name}...")
            if tool_name == "search_by_keyword":
                tool_result = await TOOL_MAP[tool_name](tool_args["keyword"])
            elif tool_name == "search_by_country":
                tool_result = await TOOL_MAP[tool_name](tool_args["country_code"])
            elif tool_name == "search_by_date_range":
                tool_result = await TOOL_MAP[tool_name](
                    tool_args["start_date"], 
                    tool_args["end_date"]
                )
            
            print(f"Tool execution completed. Got {len(tool_result)} results.")
            
            if not tool_result:
                return "No events found in the database"
            
            # Format the results
            formatted_results = format_events(
                tool_result, 
                requested_type,
                requested_year
            )
            
            if formatted_results == "No events found in the database":
                return formatted_results
            
            # Use LLM to rephrase the news while keeping the same meaning
            try:
                print("\n=== Starting LLM Rephrasing Process ===")
                rephrased_text = await process_with_llm(formatted_results)
                print("\n=== LLM Rephrasing Completed Successfully ===")
                print(f"Final output:\n{rephrased_text}")
                return rephrased_text
                
            except Exception as e:
                print(f"\n=== Error in LLM Rephrasing ===")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                return formatted_results  # Return original format if rephrasing fails
        
        return "No events found in the database"
        
    except Exception as e:
        print(f"Error in agent_chat: {str(e)}")
        return "No events found in the database"

# Test LLM connection
async def test_llm_connection():
    try:
        print("Testing LLM connection...")
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you working?"}
            ],
            temperature=0.3,
            max_tokens=50
        )
        print("LLM connection test successful!")
        print(f"Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"LLM connection test failed: {str(e)}")
        return False

# Remove the automatic test call at startup
# asyncio.create_task(test_llm_connection()) 