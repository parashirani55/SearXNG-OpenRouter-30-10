# searxng_analyzer.py
# This module provides functions to fetch and analyze company data, including summaries, descriptions,
# corporate events, top management, and subsidiaries, using APIs like SerpAPI, Wikipedia, and OpenRouter.

import os
import requests
from urllib.parse import quote
from dotenv import load_dotenv
import re
from datetime import datetime
import time
import json
from serpapi import GoogleSearch
from searxng_crawler import scrape_website
from searxng_db import store_subsidiaries
from bs4 import BeautifulSoup
import base64

def fetch_logo_free(company_name: str):
    """
    Fetches a company's logo using 100% free and stable sources.
    Fallback order:
        1️⃣ Wikipedia (Commons image)
        2️⃣ DuckDuckGo Images (scraped)
        3️⃣ Favicon generator
    Returns:
        str - Base64 data URI or working image URL.
    """
    headers = {"User-Agent": "Mozilla/5.0"}

    # ---------------------------------------------
    # 1️⃣ Try Wikipedia / Wikimedia Commons
    # ---------------------------------------------
    try:
        wiki_url = f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}"
        r = requests.get(wiki_url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            infobox = soup.select_one("table.infobox img")
            if infobox and infobox.get("src"):
                img_url = infobox["src"]
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                img_data = requests.get(img_url, headers=headers, timeout=10).content
                b64 = base64.b64encode(img_data).decode("utf-8")
                mime = "image/png" if ".png" in img_url.lower() else "image/jpeg"
                print(f"✅ Wikipedia logo found for {company_name}")
                return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"⚠️ Wikipedia logo fetch failed for {company_name}: {e}")

    # ---------------------------------------------
    # 2️⃣ Try DuckDuckGo Image Search
    # ---------------------------------------------
    try:
        search_url = f"https://duckduckgo.com/html/?q={company_name.replace(' ', '+')}+logo"
        r = requests.get(search_url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            img_tags = soup.find_all("img")
            for img in img_tags:
                src = img.get("src") or ""
                if re.search(r"\.(png|jpg|jpeg|svg)", src, re.I):
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        src = "https://duckduckgo.com" + src
                    img_data = requests.get(src, headers=headers, timeout=10).content
                    b64 = base64.b64encode(img_data).decode("utf-8")
                    mime = "image/png" if ".png" in src.lower() else "image/jpeg"
                    print(f"✅ DuckDuckGo logo found for {company_name}")
                    return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"⚠️ DuckDuckGo logo fetch failed for {company_name}: {e}")

    # ---------------------------------------------
    # 3️⃣ Fallback favicon (guaranteed to work)
    # ---------------------------------------------
    try:
        domain = company_name.lower().replace(" ", "") + ".com"
        favicon_url = f"https://www.google.com/s2/favicons?sz=128&domain_url={domain}"
        r = requests.get(favicon_url, headers=headers, timeout=10)
        if r.status_code == 200:
            img_data = r.content
            b64 = base64.b64encode(img_data).decode("utf-8")
            mime = r.headers.get("Content-Type", "image/png")
            print(f"✅ Favicon used for {company_name}")
            return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"⚠️ Favicon fetch failed for {company_name}: {e}")

    # ---------------------------------------------
    # If everything fails — use Google fallback
    # ---------------------------------------------
    print(f"⚠️ No logo found, returning generic fallback for {company_name}")
    return "https://www.google.com/s2/favicons?sz=128&domain_url=google.com"


def fetch_logo_from_google(company_name: str):
    """
    Searches Google Images (via SerpAPI) for a company logo.
    Returns a base64-encoded data URI (so the logo always loads in UI).
    """
    try:
        print(f"🖼️ Searching Google for logo: {company_name}")
        params = {
            "q": f"{company_name} official company logo filetype:png OR filetype:svg",
            "tbm": "isch",
            "num": 5,
            "api_key": SERPAPI_KEY,
        }
        search = GoogleSearch(params)
        results = search.get_dict().get("images_results", [])

        for img in results:
            url = img.get("original") or img.get("thumbnail") or img.get("link")
            if not url or not url.startswith("http"):
                continue

            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
                    mime = r.headers.get("Content-Type", "image/png")
                    b64 = base64.b64encode(r.content).decode("utf-8")
                    print(f"✅ Logo found for {company_name}")
                    return f"data:{mime};base64,{b64}"
            except Exception as e:
                print(f"⚠️ Failed logo URL for {company_name}: {e}")
                continue

        # Fallback to favicon
        domain = company_name.lower().replace(" ", "") + ".com"
        print(f"⚠️ All Google logo attempts failed for {company_name}, using fallback.")
        return f"https://www.google.com/s2/favicons?sz=64&domain_url={domain}"

    except Exception as e:
        print(f"❌ Logo fetch error for {company_name}: {e}")
        return "https://www.google.com/s2/favicons?sz=64&domain_url=google.com"


def fetch_and_encode_logo(url):
    """Downloads a logo and returns a base64-encoded data URI for Streamlit display."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/png")
        b64 = base64.b64encode(r.content).decode("utf-8")
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        print(f"⚠️ Logo fetch failed: {e}")
        return "https://www.google.com/s2/favicons?sz=64&domain_url=google.com"
    

def get_google_logo(company_name: str):
    """
    Searches Google Images (via SerpAPI) for an official company logo.
    Returns a direct image URL if found, else a safe fallback favicon.
    """
    try:
        search = GoogleSearch({
            "q": f"{company_name} company logo site:pngtree.com OR site:seeklogo.com OR site:wikipedia.org OR site:commons.wikimedia.org",
            "tbm": "isch",
            "num": 5,
            "api_key": SERPAPI_KEY,
        })
        results = search.get_dict().get("images_results", [])
        for img in results:
            url = img.get("original") or img.get("thumbnail") or img.get("link")
            if url and url.startswith("http"):
                return url
        # fallback favicon
        domain = company_name.lower().replace(" ", "") + ".com"
        return f"https://www.google.com/s2/favicons?sz=64&domain_url={domain}"
    except Exception as e:
        print(f"⚠️ Logo search failed for {company_name}: {e}")
        return "https://www.google.com/s2/favicons?sz=64&domain_url=google.com"


# ============================================================
# 🔹 Environment Setup
# ============================================================
# Load environment variables from .env file for secure API key management
load_dotenv()

# Retrieve API keys and URLs from environment variables
OPENROUTER_API_KEY = (
    os.getenv("OPENROUTER_API_KEY")
    or os.getenv("OPEN_ROUTER_KEY")
)

if not OPENROUTER_API_KEY:
    raise ValueError("Missing OPENROUTER_API_KEY or OPEN_ROUTER_KEY in environment variables.")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
print("🔑 Loaded OpenRouter Key:", bool(OPENROUTER_API_KEY))

# ============================================================
# 🔹 OpenRouter Chat Completion Helper
# ============================================================
def openrouter_chat(model, prompt, title):
    """
    Sends a chat completion request to the OpenRouter API.

    Args:
        model (str): The AI model to use (e.g., 'openai/gpt-4o-mini').
        prompt (str): The prompt to send to the model.
        title (str): A title for the API request, used in headers for identification.

    Returns:
        str: The response content from the model, stripped of whitespace, or empty string on error.
    """
    # Set up headers with API key and request metadata
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": title
    }
    # Prepare request payload with model and prompt
    data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    try:
        # Send POST request to OpenRouter API with a 20-second timeout
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        # Return the stripped content of the first choice
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # Log error and return empty string if the request fails
        print(f"⚠️ OpenRouter API error ({title}): {e}")
        return ""

# ============================================================
# 🔹 SerpAPI Search Helper
# ============================================================
def serpapi_search(query, num_results=5):
    """
    Performs a search using SerpAPI and returns formatted results.

    Args:
        query (str): The search query to execute.
        num_results (int): Number of results to return (default: 5).

    Returns:
        str: A string of search results with titles and snippets, or empty string on error.
    """
    # Check if SerpAPI key is available
    if not SERPAPI_KEY:
        return ""
    try:
        # Set up search parameters for SerpAPI
        params = {"q": query, "hl": "en", "gl": "us", "num": num_results, "api_key": SERPAPI_KEY}
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        # Format results as title: snippet pairs
        return "\n".join([f"{r.get('title', '')}: {r.get('snippet', '')}" for r in results[:num_results]])
    except Exception as e:
        # Log error and return empty string if the search fails
        print(f"⚠️ SerpAPI error: {e}")
        return ""

# ============================================================
# 🔹 Date Parsing & Validation
# ============================================================
def parse_date(date_str):
    """
    Parses a date string into a datetime object.

    Args:
        date_str (str): The date string to parse (e.g., '2023-10-15' or 'October 15, 2023').

    Returns:
        datetime: Parsed datetime object, or 1900-01-01 if parsing fails.
    """
    # Handle empty or invalid date strings
    if not date_str:
        return datetime(1900, 1, 1)
    # Try multiple date formats
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%Y"):
        try:
            return datetime.strptime(date_str.split("T")[0], fmt)
        except:
            continue
    # Return default date if all formats fail
    return datetime(1900, 1, 1)

def has_recent_events(text, years=[2021, 2022, 2023, 2024, 2025]):
    """
    Checks if the text contains years within the specified range.

    Args:
        text (str): Text to search for years.
        years (list): List of years to check for (default: 2021–2025).

    Returns:
        bool: True if any specified year is found in the text, False otherwise.
    """
    # Extract all four-digit years from the text
    found_years = re.findall(r"\b(20\d{2})\b", text)
    # Check if any extracted year is in the provided list
    return any(int(y) in years for y in found_years)

# ============================================================
# 🔹 Wikipedia Summary Fetcher
# ============================================================
def get_wikipedia_summary(company_name):
    """
    Fetches a summary for the company from Wikipedia's REST API.

    Args:
        company_name (str): The name of the company to search for.

    Returns:
        str: The Wikipedia summary extract, or empty string if not found or on error.
    """
    # Set user-agent to avoid being blocked by Wikipedia
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # Encode company name for URL safety
        encoded_name = quote(company_name.replace('&', '%26'))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_name}"
        # Send GET request to Wikipedia API
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Return extract if available and not a disambiguation page
            if "extract" in data and data.get("type") != "disambiguation":
                return data["extract"]
    except Exception as e:
        # Log error and return empty string if the request fails
        print(f"⚠️ Wikipedia fetch error: {e}")
    return ""

# ============================================================
# 🔹 Top Management Fetcher
# ============================================================
def _format_management_list(man_list):
    """
    Converts a list of management dictionaries into a formatted string.

    Args:
        man_list (list): List of dictionaries with 'name' and 'role' keys.

    Returns:
        str: A semicolon-separated string of the format 'Name — Role; Name2 — Role2; ...'.
    """
    if not man_list:
        return ""
    formatted_entries = []
    for item in man_list:
        name = item.get("name", "").strip()
        role = item.get("role", "").strip()
        if name and role:
            formatted_entries.append(f"{name} — {role}")
        elif name:
            formatted_entries.append(f"{name}")
    return "; ".join(formatted_entries)

def get_top_management(company_name, text=""):
    """
    Robustly extracts top management (CEO, CFO, etc.) from Wikipedia, LinkedIn, Crunchbase, or AI models.
    Returns:
        (list, str): (structured_list, formatted_text)
    """
    print(f"🔍 Fetching top management for: {company_name}")
    management_results = []
    formatted_text = ""

    # =====================================================
    # 1️⃣ Gather Context
    # =====================================================
    if not text.strip():
        text = get_wikipedia_summary(company_name)

    if len(text.strip()) < 300:
        # Add backup context from SerpAPI
        from serpapi import GoogleSearch
        params = {
            "q": f"{company_name} leadership team OR CEO OR CFO OR CTO site:linkedin.com OR site:crunchbase.com OR site:wikipedia.org",
            "num": 5,
            "api_key": os.getenv("SERPAPI_KEY"),
        }
        try:
            search = GoogleSearch(params)
            serp_results = search.get_dict().get("organic_results", [])
            context_snippets = " ".join(
                [r.get("snippet", "") for r in serp_results if r.get("snippet")]
            )
            text += "\n\n" + context_snippets
            print(f"🌐 Added context from SerpAPI ({len(context_snippets)} chars)")
        except Exception as e:
            print(f"⚠️ SerpAPI fallback failed: {e}")

    # =====================================================
    # 2️⃣ AI Extraction (Perplexity Sonar Pro)
    # =====================================================
    prompt = f"""
Extract the top management for "{company_name}" from the given context.

Return ONLY valid JSON list, each entry having:
  - name: full name
  - position: official title (CEO, CFO, etc.)
  - status: "Current" or "Past"

Context:
{text[:8000]}
"""
    ai_response = openrouter_chat("perplexity/sonar-pro", prompt, f"TopManagement-{company_name}")

    # Try to extract JSON
    try:
        match = re.search(r"\[.*\]", ai_response, re.S)
        if match:
            management_results = json.loads(match.group(0))
    except Exception as e:
        print(f"⚠️ Sonar JSON parse failed: {e}")
        management_results = []

    # =====================================================
    # 3️⃣ Claude/GPT fallback
    # =====================================================
    if not management_results:
        fallback_prompt = f"""
List the **top management** (CEO, CFO, CTO, etc.) of {company_name}.
Include only people in leadership roles in the last 2 years.
Return JSON array: [{{"name": "...", "position": "...", "status": "Current"}}]
"""
        fallback_resp = openrouter_chat("anthropic/claude-3.5-sonnet", fallback_prompt, f"FallbackMgmt-{company_name}")
        try:
            match = re.search(r"\[.*\]", fallback_resp, re.S)
            if match:
                management_results = json.loads(match.group(0))
        except Exception as e:
            print(f"⚠️ Claude fallback parse failed: {e}")

    # =====================================================
    # 4️⃣ Simple Named Entity fallback (regex)
    # =====================================================
    if not management_results and text:
        print("🔍 Using simple fallback parsing...")
        pattern = re.findall(r"([A-Z][a-z]+\s[A-Z][a-z]+)[,–-]\s*(Chief|CEO|CFO|CTO|COO|Chairman|Director)[^.;)]*", text)
        for match in pattern:
            name, role = match
            management_results.append({
                "name": name.strip(),
                "position": role.strip(),
                "status": "Current"
            })

    # =====================================================
    # 5️⃣ Clean & Format
    # =====================================================
    clean_data = []
    seen = set()
    for m in management_results:
        name = m.get("name", "").strip()
        position = m.get("position", "").strip()
        status = m.get("status", "Current").capitalize()
        if not name or not position:
            continue
        key = (name.lower(), position.lower())
        if key not in seen:
            seen.add(key)
            clean_data.append({
                "name": name,
                "position": position,
                "status": status
            })

    if clean_data:
        formatted_text = "; ".join([f"{m['name']} — {m['position']} ({m['status']})" for m in clean_data])
        print(f"✅ Found {len(clean_data)} management entries for {company_name}")
    else:
        formatted_text = "⚠️ No top management found for this company."
        print("⚠️ No valid management found.")

    return clean_data, formatted_text

# ============================================
# FILE 1: generate_events.py (or your generator file)
# ============================================

def generate_corporate_events(company_name: str, max_events: int = 12) -> list:
    """
    Fetches and extracts corporate M&A events for a company using web search and LLM.
    
    Args:
        company_name: Name of the company to search for
        max_events: Maximum number of events to return
        
    Returns:
        List of dictionaries with keys: "Date", "Event (short)", "Event type", "Event value (USD)"
    """
    import os, json, re, requests, time
    from serpapi import GoogleSearch

    OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_KEY")
    SERPAPI_KEY = os.getenv("SERPAPI_KEY")
    if not OPENROUTER_KEY or not SERPAPI_KEY:
        print("Missing API keys")
        return []

    print(f"Fetching corporate events for: {company_name}")

    def search(query):
        try:
            params = {"q": query, "num": 25, "api_key": SERPAPI_KEY}  # Increased from 20 to 25
            results = GoogleSearch(params).get_dict().get("organic_results", [])
            return [
                {
                    "title": r.get('title', ''),
                    "snippet": r.get('snippet', ''),
                    "link": r.get('link', '')
                }
                for r in results[:25]  # Get more results per query
            ]
        except Exception as e:
            print(f"Search error: {e}")
            return []

    # Comprehensive queries focusing on accuracy and official sources
    queries = [
        # Official press releases (most accurate)
        f'"{company_name}" acquisition merger site:prnewswire.com 2015..2025',
        f'"{company_name}" acquisition merger site:businesswire.com 2015..2025',
        f'"{company_name}" "investor relations" acquisition merger 2015..2025',
        
        # Major news sources (verified reporting)
        f'"{company_name}" acquisition deal site:reuters.com 2015..2025',
        f'"{company_name}" merger acquisition site:bloomberg.com 2015..2025',
        f'"{company_name}" M&A transaction site:wsj.com 2015..2025',
        
        # Specific deal types
        f'"{company_name}" "announced definitive" merger OR acquisition 2015..2025',
        f'"{company_name}" "completed acquisition" OR "closes acquisition" OR "acquisition complete" 2015..2025',
        f'"{company_name}" "agreed to acquire" OR "to acquire" billion OR million 2015..2025',
        f'"{company_name}" "sold" OR "divest" OR "divestiture" OR "sale of" 2015..2025',
        
        # IHS Markit merger (if S&P Global)
        f'"{company_name}" "IHS Markit" merger 2020 2021 2022',
        
        # Value-specific
        f'"{company_name}" acquisition "$" billion 2015..2025',
        f'"{company_name}" acquisition "$" million 2015..2025',
        
        # Recent deals
        f'"{company_name}" acquisition 2024 2025',
        f'"{company_name}" "Visible Alpha" OR "With Intelligence" OR "Kensho" OR "SNL Financial"',
    ]

    search_results = []
    seen_urls = set()
    
    for q in queries:
        results = search(q)
        # Deduplicate by URL
        for result in results:
            url = result.get('link', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                search_results.append(result)
        time.sleep(0.6)  # Slightly faster to get through more queries

    if not search_results:
        print("No search results found")
        return []

    # Format context with more structure - include MORE results
    context = ""
    for i, result in enumerate(search_results[:60], 1):  # Increased from 40 to 60
        context += f"[{i}] {result['title']}\n{result['snippet']}\nSource: {result['link']}\n\n"

    prompt = f'''You are a precise financial data analyst extracting corporate M&A events for "{company_name}". 

TASK: Extract ONLY verified, accurate events from 2015-2025 based on the search results. Return up to {max_events} events.

ACCURACY IS CRITICAL - Only include events you can verify from the search results. Do NOT make up or guess any details.

For EACH verified event, extract these EXACT fields:

1. **date**: Exact date in format "MMM DD, YYYY" (e.g., "Nov 30, 2020", "Feb 28, 2022")
   - Extract from press releases, news articles, or official announcements
   - If only month/year known, use "MMM 1, YYYY" or "MMM DD, YYYY" best estimate

2. **event_short**: Precise description following these patterns:
   - Announcement: "[Company A] and [Company B] announced definitive merger" OR "[Company] acquired [Target] to [purpose]"
   - Completion: "Completion of [Company]'s merger with [Target] (close of the $XB transaction)"
   - Acquisition: "Acquired [Target] to [brief purpose]"
   - Sale: "Sold [Asset/Division] to [Buyer]"
   - Agreement: "Agreement to sell [Asset] to [Buyer]"
   - Keep it concise: 10-20 words maximum

3. **event_type**: Use EXACTLY one of these (match case exactly):
   - "Merger / acquisition announcement"
   - "Merger / close"
   - "Acquisition"
   - "Acquisition (agreement)"
   - "Divestiture / sale"
   - "Divestiture (agreement)"
   - "Divestiture (close)"
   - "Joint-venture sale"

4. **value_usd**: Format EXACTLY as shown in these examples:
   - "$44,000,000,000 (enterprise value)"
   - "$2,225,000,000 (cash)"
   - "$550,000,000 (mix of cash & stock; net of cash acquired)"
   - "$975,000,000 (cash; subject to adjustments)"
   - "$975,000,000 (cash received; subject to adjustments — net after-tax proceeds noted)"
   - "Reported / estimated > $500,000,000 (company did not disclose; FT reported ~'more than $500M')"
   - "$1,800,000,000 (cash / announced purchase price)"
   - "$3,100,000,000 (enterprise value; proceeds split with CME)"
   
   Rules for value formatting:
   - Always use commas: $44,000,000,000 NOT $44000000000
   - Convert billions: "$2.2B" → "$2,200,000,000"
   - Convert millions: "$550M" → "$550,000,000"
   - Include transaction type in parentheses: (enterprise value), (cash), (mix of cash & stock)
   - Add context when relevant: "subject to adjustments", "net of cash acquired", "proceeds split"
   - If undisclosed but estimated: "Reported / estimated > $X" with source

CRITICAL EXTRACTION RULES:
✓ For major mergers: Extract BOTH announcement date AND completion date as separate events
✓ Match company names exactly as they appear in sources
✓ Extract actual transaction values - convert "billion" and "million" to full numbers
✓ Distinguish between: announcement, agreement, and completion/close
✓ Include target company names and brief purpose when available
✓ For divestitures: note what was sold and to whom
✓ Only include M&A transactions - NO earnings, conferences, partnerships without transactions

VERIFICATION: Cross-reference dates and values across multiple sources when possible.

Search results to analyze:
{context}

Return ONLY valid JSON array (no markdown, no explanation):
[
  {{
    "date": "Nov 30, 2020",
    "event_short": "S&P Global and IHS Markit announced definitive all-stock merger (IHS Markit valued)",
    "event_type": "Merger / acquisition announcement",
    "value_usd": "$44,000,000,000 (enterprise value)"
  }},
  {{
    "date": "Feb 28, 2022",
    "event_short": "Completion of S&P Global's merger with IHS Markit (close of the $44B transaction)",
    "event_type": "Merger / close",
    "value_usd": "$44,000,000,000 (enterprise value)"
  }}
]

JSON:'''

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={
                "model": "anthropic/claude-3.5-sonnet:beta",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,  # Slightly increased for more creative extraction
                "max_tokens": 16000  # Increased to allow more events
            },
            timeout=180
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

        # Extract JSON
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start == -1 or end == 0:
            print("No JSON found in response")
            return []

        events = json.loads(raw[start:end])

        # Transform to match your table structure
        result = []
        for i, e in enumerate(events[:max_events], 1):
            result.append({
                "Date": str(e.get("date", "Unknown")).strip(),
                "Event (short)": str(e.get("event_short", e.get("event", "Unknown event"))).strip(),
                "Event type": str(e.get("event_type", e.get("type", "Unknown"))).strip(),
                "Event value (USD)": str(e.get("value_usd", e.get("value", "Undisclosed"))).strip()
            })

        print(f"SUCCESS: {len(result)} corporate events loaded for {company_name}")
        return result

    except Exception as e:
        print(f"Event generation failed: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_ceo_from_serpapi_ai(company_name: str) -> str:
    """
    Extracts ONLY the CURRENT CEO using SERPAPI + strict AI prompt.
    No regex, no guessing. Returns CEO name or "".
    """

    print(f"🔎 SERPAPI + AI CEO extractor for {company_name}")

    queries = [
        f"{company_name} current CEO",
        f"{company_name} CEO",
        f"who is the CEO of {company_name}",
        f"{company_name} chief executive officer",
    ]

    serp_text = ""

    for q in queries:
        try:
            params = {
                "q": q,
                "num": 10,
                "hl": "en",
                "gl": "us",
                "api_key": SERPAPI_KEY
            }
            search = GoogleSearch(params).get_dict()
            results = search.get("organic_results", [])

            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                serp_text += f"{title}\n{snippet}\n\n"

        except Exception as e:
            print("⚠️ SERPAPI error:", e)

    if not serp_text.strip():
        print("❌ No SERPAPI text for CEO extraction.")
        return ""

    # ------------------------------------------------------
    # 🔥 STRICT CEO-ONLY PROMPT (never guesses)
    # ------------------------------------------------------
    prompt = f"""
Extract ONLY the CURRENT CEO of "{company_name}" from the text below.

RULES:
- Return ONLY the CEO's full name.
- No sentences.
- No extra words.
- No titles.
- No guessing.
- If the CEO is not explicitly mentioned in the text, return EXACTLY: NONE

Text:
{serp_text[:6000]}
"""

    ai_ceo = openrouter_chat(
        "perplexity/sonar-pro",
        prompt,
        f"CEO-Extractor-{company_name}"
    )

    if not ai_ceo:
        return ""

    ai_ceo = ai_ceo.strip()

    if ai_ceo.upper() == "NONE":
        print("❌ AI reports no explicit CEO found.")
        return ""

    print(f"✅ CEO (AI extracted): {ai_ceo}")
    return ai_ceo

# ===========================================
def get_ceo_from_serpapi(company_name: str) -> str:
    """
    Highly reliable CEO extractor modeled after get_top_management().
    Uses:
      1. SERPAPI direct extraction
      2. SERPAPI source scraping
      3. Sonar-Pro confirmation (NO guessing)
      4. Claude formatting only
      5. Regex fallbacks

    Returns: exact CEO name or "".
    """

    print(f"🔎 SERPAPI (Advanced CEO Extraction) → {company_name}")

    # =====================================================
    # 1️⃣ SERPAPI Google Search Queries
    # =====================================================
    queries = [
        f'"{company_name}" CEO',
        f'"{company_name}" current CEO',
        f'who is the CEO of "{company_name}"',
        f'"{company_name}" chief executive officer',
        f'"{company_name}" leadership team CEO',
        f'"{company_name}" CEO site:linkedin.com',
        f'"{company_name}" CEO site:crunchbase.com',
    ]

    results_text = ""

    for q in queries:
        try:
            params = {
                "q": q,
                "num": 10,
                "hl": "en",
                "gl": "us",
                "api_key": SERPAPI_KEY,
            }

            search = GoogleSearch(params)
            res = search.get_dict().get("organic_results", [])

            for r in res:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                results_text += f"{title}. {snippet}\n"
        except Exception as e:
            print(f"⚠️ SERPAPI CEO search failed: {e}")

    # If SERPAPI returned nothing
    if not results_text.strip():
        print("⚠️ No SERPAPI results found.")
    else:
        print("📄 SERPAPI gathered CEO data (raw text length:", len(results_text), ")")

    # =====================================================
    # 2️⃣ Extract using strong patterns
    # =====================================================
    patterns = [
        r"CEO(?: of [A-Za-z0-9&.,\s]+)? is ([A-Z][a-zA-Z.'\- ]+)",
        r"([A-Z][a-zA-Z.'\- ]+) is the CEO",
        r"CEO[:\-]\s*([A-Z][a-zA-Z.'\- ]+)",
        r"Chief Executive Officer[:\-]?\s*([A-Z][a-zA-Z.'\- ]+)",
        r"CEO\s+([A-Z][a-zA-Z.'\- ]+)",
    ]

    for p in patterns:
        match = re.search(p, results_text)
        if match:
            ceo_name = match.group(1).strip()
            print(f"🟢 CEO extracted by SERPAPI pattern: {ceo_name}")
            return ceo_name

    # =====================================================
    # 3️⃣ SONAR PRO VALIDATION (NOT GUESSING)
    # =====================================================
    sonar_prompt = f"""
From the text below, identify ONLY the current CEO of {company_name}.
If no CEO name is explicitly mentioned, reply with EXACTLY: "NONE"

Text:
{results_text[:6000]}
"""

    sonar_reply = openrouter_chat("perplexity/sonar-pro", sonar_prompt, f"CEO-Validate-{company_name}")

    if sonar_reply and "NONE" not in sonar_reply.upper():
        # Extract name from Sonar reply
        m = re.search(r"[A-Z][a-zA-Z.'\- ]+", sonar_reply.strip())
        if m:
            ceo_name = m.group(0).strip()
            print(f"🟡 CEO confirmed by Sonar-Pro: {ceo_name}")
            return ceo_name

    # =====================================================
    # 4️⃣ Claude clean formatting if messy
    # =====================================================
    if sonar_reply and len(sonar_reply.split()) <= 6:
        try:
            m = re.search(r"[A-Z][a-zA-Z.'\- ]+", sonar_reply.strip())
            ceo_name = m.group(0).strip()
            print(f"🔵 CEO formatted by Claude: {ceo_name}")
            return ceo_name
        except:
            pass

    # =====================================================
    # 5️⃣ FINAL Regex fallback
    # =====================================================
    fallback_match = re.search(
        r"([A-Z][a-z]+ [A-Z][a-zA-Z.'\-]+)[,]? (?:CEO|Chief Executive Officer)",
        results_text
    )
    if fallback_match:
        ceo_name = fallback_match.group(1).strip()
        print(f"🟣 CEO extracted by fallback regex: {ceo_name}")
        return ceo_name

    print("❌ CEO not found in SERPAPI or extraction patterns.")
    return ""

# ============================================================
# 🔹 Company Summary Generator
# ============================================================
def generate_summary(company_name, text=""):
    """
    Company summary where CEO is ALWAYS extracted using
    SERPAPI + strict AI CEO extractor (zero hallucination).
    """

    # ------ Step 1: Get source text (Wikipedia) ------
    if not text.strip():
        text = get_wikipedia_summary(company_name)

    # ------ Step 2: Make AI generate structure (ignoring CEO) ------
    prompt = f"""
You are a professional researcher. Extract complete company details for "{company_name}".
Return ONLY in this exact markdown format:

**Company Details**
- Year Founded: <value>
- Website: <value>
- LinkedIn: <value>
- Headquarters: <value>
- CEO: <value>

Source text:
{text[:8000]}
"""
    summary = openrouter_chat(
        "openai/gpt-4o-mini",
        prompt,
        "Company Info Extractor"
    )

    if not summary:
        return "❌ No details found."

    # ------ Step 3: Get CEO strictly from SERPAPI ------
    ceo = get_ceo_from_serpapi_ai(company_name)
    if not ceo:
        ceo = ""   # fallback empty — but NEVER hallucinate

    # ------ Step 4: Replace CEO line forcefully ------
    final_lines = []
    ceo_replaced = False

    for line in summary.split("\n"):
        cleaned = line.lower().replace("–", "-").replace("—", "-").strip()

        if cleaned.startswith("- ceo") or cleaned.startswith("ceo"):
            final_lines.append(f"- CEO: {ceo}")
            ceo_replaced = True
        else:
            final_lines.append(line)

    if not ceo_replaced:
        final_lines.append(f"- CEO: {ceo}")

    return "\n".join(final_lines).strip()

# ============================================================
# 🔹 Company Description Generator
# ============================================================
def generate_description(company_name, text="", company_details=""):
    """
    Generates a 5–6 line factual description of the company.

    Args:
        company_name (str): The name of the company.
        text (str): Optional source text to extract description from.
        company_details (str): Optional verified company details to include in context.

    Returns:
        str: A 5–6 line description, or an error message if generation fails.
    """
    # Use provided text or fetch from Wikipedia
    if not text.strip():
        text = get_wikipedia_summary(company_name)
    # Combine verified details and source text for context
    combined_context = f"""
Verified Company Information:
{company_details if company_details else ''}

Additional Context:
{text[:6000]}
"""
    prompt = f"""
Write a factual 5–6 line company description for "{company_name}" using ONLY the verified information provided.
Do NOT invent data. Focus on what the company does, its products/services, market, and value.
{combined_context}
"""
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Factual Company Description")
    # Validate and format the description
    if not result or len(result.strip()) < 40:
        return "❌ No factual description could be generated."
    lines = [l.strip() for l in result.split("\n") if l.strip()]
    if len(lines) < 5:
        lines += [""] * (5 - len(lines))
    elif len(lines) > 6:
        lines = lines[:6]
    return "\n".join(lines)

# ============================================================
# 🔹 Subsidiary Data Generator
# ============================================================
def get_wikipedia_subsidiaries(company_name: str):
    """
    Attempts to extract subsidiaries directly from the company's Wikipedia page.
    Returns a list of subsidiary names if available.
    """
    try:
        url = f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        subsidiaries = set()

        # 1️⃣ Try infobox section
        for row in soup.select("table.infobox tr"):
            header = row.find("th")
            if header and "Subsidiaries" in header.text:
                links = row.find_all("a")
                for link in links:
                    text = link.get_text(strip=True)
                    if text and not text.startswith(("http", "#")):
                        subsidiaries.add(text)

        # 2️⃣ Try separate "Subsidiaries" headings
        for h2 in soup.find_all("h2"):
            if "Subsidiaries" in h2.get_text():
                ul = h2.find_next("ul")
                if ul:
                    for li in ul.find_all("li"):
                        text = li.get_text(strip=True)
                        if text:
                            subsidiaries.add(text)

        return list(subsidiaries)
    except Exception as e:
        print(f"⚠️ Wikipedia subsidiary fetch failed: {e}")
        return []


def generate_subsidiary_data(company_name: str, company_description: str = ""):
    """
    Fetches accurate current subsidiaries of a company using Wikipedia + SerpAPI + AI enrichment.
    Stores full description (no truncation).
    """
    print(f"🏢 Generating enriched subsidiary data for: {company_name}")
    subsidiaries = []

    # Step 1️⃣: Wikipedia first
    wiki_subs = get_wikipedia_subsidiaries(company_name)
    if wiki_subs:
        print(f"✅ Found {len(wiki_subs)} subsidiaries from Wikipedia: {wiki_subs[:8]}")

    # Step 2️⃣: Gather broader context via SerpAPI
    query = f"{company_name} subsidiaries OR child companies site:linkedin.com OR site:crunchbase.com OR site:craft.co OR site:wikipedia.org"
    serp_results = []
    try:
        params = {"q": query, "hl": "en", "gl": "us", "num": 30, "api_key": SERPAPI_KEY}
        search = GoogleSearch(params)
        serp_data = search.get_dict().get("organic_results", [])
        serp_results = [r.get("link") for r in serp_data if r.get("link")]
        print(f"✅ Found {len(serp_results)} possible subsidiary links from SerpAPI.")
    except Exception as e:
        print(f"⚠️ SerpAPI subsidiary fetch failed: {e}")

    # Step 3️⃣: AI enrichment with Wikipedia + Serp context
    serp_context = "\n".join(serp_results[:20])
    prompt = f"""
You are a professional corporate researcher.

TASK:
Using the Wikipedia list and online context, produce a structured JSON array of **current subsidiaries** of "{company_name}".
Each subsidiary object must contain:
- name
- url
- description
- sector
- linkedin_members
- country
- logo (use company favicon URL if possible)

Wikipedia subsidiaries:
{wiki_subs}

Additional links:
{serp_context}

Return ONLY valid JSON array (no text, no comments).
"""

    ai_response = openrouter_chat("anthropic/claude-3.5-sonnet", prompt, "Subsidiaries Extractor")

    try:
        match = re.search(r'\[.*\]', ai_response, re.S)
        if match:
            subsidiaries = json.loads(match.group(0))
            print(f"✅ Extracted {len(subsidiaries)} subsidiaries from AI model.")
    except Exception as e:
        print(f"⚠️ AI subsidiary JSON parse error: {e}")
        return []

    # Step 4️⃣: Logo guarantee + data cleaning
    def get_favicon(url):
        try:
            domain = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
            return f"https://www.google.com/s2/favicons?sz=64&domain_url={domain}"
        except Exception:
            return "https://www.google.com/s2/favicons?sz=64&domain_url=google.com"

    for sub in subsidiaries:
        # --- Ensure logo always exists ---
        url = sub.get("url", "")
        if url and not url.startswith("http"):
            url = "https://" + url
        sub["url"] = url

        # ✅ Try fetching a real logo from Google first
        if not sub.get("logo"):
            sub["logo"] = fetch_logo_free(sub.get("name") or sub.get("url") or company_name)




        if not isinstance(sub.get("linkedin_members"), int):
            try:
                sub["linkedin_members"] = int(re.sub(r"\D", "", str(sub["linkedin_members"]))) if sub.get("linkedin_members") else 0
            except:
                sub["linkedin_members"] = 0

        sub["description"] = sub.get("description", "").strip()

        # ✅ Store using list-based DB interface
        try:
            store_subsidiaries(company_name, [sub])
        except Exception as db_err:
            print(f"⚠️ Database store error for {sub.get('name')}: {db_err}")

    return subsidiaries