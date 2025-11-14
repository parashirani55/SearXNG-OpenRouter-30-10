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
OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")
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

# ============================================================
# 🔹 Corporate Events Generator
# ============================================================
def generate_corporate_events(company_name, text=""):
    """
    Generates a list of corporate events (M&A, IPOs, etc.) for a company from 2021–2025.

    Args:
        company_name (str): The name of the company.
        text (str): Optional source text to extract events from.

    Returns:
        str: Formatted string of events, or an error message if no events are found.
    """
    print(f"🚀 Extracting corporate events for {company_name}")
    all_events = []

    # Step 1: Extract events from provided text or Wikipedia
    if text.strip():
        wiki_prompt = f"""
You are a professional business analyst.

TASK:
Extract ONLY verifiable corporate events for {company_name} from the years **2021–2025**.
Corporate events include: Mergers & Acquisitions, IPOs, Investments/Fundings, Spin-offs, and Partnerships.

OUTPUT RULES:
- Output ONLY valid JSON.
- JSON must be a single array of event objects.
- Each object must have these exact fields:
  description, date (YYYY-MM-DD), type, value
- If any field is unknown, leave it empty (e.g. "").
- Do NOT include explanations, markdown, or extra text outside the JSON.
- Do NOT include events before 2021.

EXAMPLE FORMAT:
[
  {{
    "description": "Apple acquired Beats Electronics",
    "date": "2014-05-28",
    "type": "Acquisition",
    "value": "$3 billion"
  }}
]

SOURCE TEXT:
{text[:4000]}
"""
        wiki_events = openrouter_chat("perplexity/sonar-pro", wiki_prompt, "Corporate Events Wikipedia")
        try:
            events = json.loads(wiki_events)
            if isinstance(events, list):
                all_events.extend(events)
                print("✅ Added events from Wikipedia/text")
        except Exception:
            print("⚠️ Failed to parse Wikipedia events")

    # Step 2: Fallback to GPT for additional events
    chatgpt_prompt = f"""
You are a structured data extractor.

TASK:
List all major corporate events (M&A, IPOs, investments, spin-offs, or partnerships) involving {company_name}
that occurred from **2021 to 2025**.

OUTPUT RULES:
- Return ONLY a valid JSON array.
- Each array element must contain:
  description, date (YYYY-MM-DD), type, value
- No explanations, headers, markdown, or commentary.
- Only include events within the 2021–2025 range.

EXAMPLE OUTPUT:
[
  {{
    "description": "Tesla announced a 3-for-1 stock split",
    "date": "2022-08-25",
    "type": "Corporate Action",
    "value": ""
  }}
]
"""
    chatgpt_events = openrouter_chat("anthropic/claude-3.5-sonnet", chatgpt_prompt, "Corporate Events GPT")
    try:
        events = json.loads(chatgpt_events)
        if isinstance(events, list):
            all_events.extend(events)
            print("✅ Added GPT events")
    except Exception:
        print("⚠️ Failed to parse GPT events")

    # Step 3: Extract events from website/press via OpenRouter
    site_events_prompt = f"""
You are a corporate intelligence model.

TASK:
Based on online reports and reliable news coverage, list notable {company_name} events from 2021–2025.
Include M&A, IPOs, investments, spin-offs, or large partnerships.

OUTPUT RULES:
- Return ONLY valid JSON.
- JSON must be a single array of objects.
- Each object fields: description, date (YYYY-MM-DD), type, value
- No commentary or text outside JSON.

EXAMPLE:
[
  {{
    "description": "Google acquired Fitbit",
    "date": "2021-01-14",
    "type": "Acquisition",
    "value": "$2.1 billion"
  }}
]
"""
    site_events = openrouter_chat("perplexity/sonar-pro", site_events_prompt, "Corporate Events Website")
    try:
        events = json.loads(site_events)
        if isinstance(events, list):
            all_events.extend(events)
            print("✅ Added website/press events")
    except Exception:
        print("⚠️ Failed to parse website/press events")

    # Step 4: Clean up and format events
    if not all_events:
        return f"⚠️ No corporate events found for {company_name}"

    # Deduplicate events by description and date
    unique_events = {}
    for e in all_events:
        desc = e.get("description", f"{company_name} Unknown Event")
        date = e.get("date", "N/A")
        typ = e.get("type", "Corporate Event")
        val = e.get("value", "")
        key = (desc.lower(), date)
        unique_events[key] = {"description": desc, "date": date, "type": typ, "value": val}

    # Sort events by date in descending order
    sorted_events = sorted(unique_events.values(), key=lambda x: parse_date(x["date"]), reverse=True)

    # Format events into a readable string
    output_lines = [
        f"- Event Description: {e['description']}\n  Date: {e['date']}\n  Type: {e['type']}\n  Value: {e['value']}"
        for e in sorted_events
    ]
    return "\n\n".join(output_lines)

# ============================================================
# 🔹 Company Summary Generator
# ============================================================
def generate_summary(company_name, text=""):
    """
    Generates a structured summary of company details.

    Args:
        company_name (str): The name of the company.
        text (str): Optional source text to extract details from.

    Returns:
        str: Markdown-formatted company details, or an error message if no details are found.
    """
    # Use provided text or fetch from Wikipedia
    if not text.strip():
        text = get_wikipedia_summary(company_name)

    prompt = f"""
You are a professional researcher. Extract complete company details for "{company_name}".
Return ONLY in this markdown format:

**Company Details**
- Year Founded: <value>
- Website: <value>
- LinkedIn: <value>
- Headquarters: <value>
- CEO: <value>

Source text:
{text[:8000]}
"""
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Company Info Extractor")
    return result or "❌ No details found."

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