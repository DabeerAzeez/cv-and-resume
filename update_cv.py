#!/usr/bin/env python3
"""
CV Generator - Generate cv.tex from Notion using Jinja2

This module provides functionality to automatically generate a LaTeX CV from a Notion
database. It fetches data from Notion, processes it, and renders it using Jinja2
templating to create a professional CV document.

The system supports:
- Dynamic content generation from Notion database
- Automatic LaTeX formatting and escaping
- Caching to reduce API calls
- Support for multiple content types (Experience, Education, Projects, etc.)
- Rich text processing from Notion blocks
- Date formatting and sorting

Requirements:
    pip install notion-client python-dotenv Jinja2

Environment Variables:
    NOTION_TOKEN: Your Notion integration token
    DATA_SOURCE_ID: The ID of your Notion database
    TEMPLATE_FILE: LaTeX template file (default: cv_template.tex)
    OUT_FILE: Output LaTeX file (default: cv.tex)

Usage:
    python update_cv.py [--refresh]

Author:
    Dabeer Ahmad Abdul Azeez

License:
    MIT License - Based on original work by Jitin Nair (2021)
"""

from __future__ import annotations
import os
import sys
import time
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from notion_client import Client
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# ------------------------------
# LaTeX helpers
# ------------------------------

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "%": r"\%",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

def latex_escape(text: str) -> str:
    """
    Escape LaTeX special characters conservatively.
    
    This function converts characters that have special meaning in LaTeX
    to their escaped equivalents to prevent LaTeX compilation errors.
    
    Args:
        text (str): The text to escape
        
    Returns:
        str: The text with LaTeX special characters escaped
        
    Example:
        >>> latex_escape("Hello & World")
        "Hello \\& World"
    """
    if not text:
        return ""
    out = []
    for ch in text:
        out.append(LATEX_SPECIALS.get(ch, ch))
    return "".join(out)

# ------------------------------
# Notion rich-text → LaTeX
# ------------------------------

def rt_to_latex(rich_text: List[Dict[str, Any]]) -> str:
    """
    Render a list of Notion rich_text objects to LaTeX with annotations preserved.
    
    Converts Notion's rich text format to LaTeX, preserving formatting like
    bold, italic, underline, strikethrough, code, and links.
    
    Args:
        rich_text (List[Dict[str, Any]]): List of Notion rich text objects
        
    Returns:
        str: LaTeX formatted text with annotations
        
    Example:
        >>> rt_to_latex([{"plain_text": "Hello", "annotations": {"bold": True}}])
        "\\textbf{Hello}"
    """
    parts: List[str] = []
    for rt in rich_text or []:
        t = rt.get("plain_text", "")
        t = latex_escape(t)
        ann = (rt.get("annotations") or {})
        # link first (outermost), then text styles (nest inside link)
        if rt.get("href"):
            t = f"\\href{{{rt['href']}}}{{{t}}}"
        if ann.get("code"):
            t = f"\\texttt{{{t}}}"
        if ann.get("bold"):
            t = f"\\textbf{{{t}}}"
        if ann.get("italic"):
            t = f"\\textit{{{t}}}"
        if ann.get("underline"):
            t = f"\\uline{{{t}}}"
        if ann.get("strikethrough"):
            t = f"\\sout{{{t}}}"
        parts.append(t)
    return "".join(parts)

# ------------------------------
# Notion blocks → LaTeX body
# ------------------------------

def list_children(notion: Client, block_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all child blocks from a Notion page.
    
    Notion's API paginates results, so this function handles pagination
    to retrieve all child blocks from a given page.
    
    Args:
        notion (Client): Authenticated Notion client
        block_id (str): The ID of the Notion page/block
        
    Returns:
        List[Dict[str, Any]]: List of all child blocks
        
    Raises:
        Exception: If there's an error accessing the Notion API
    """
    all_blocks: List[Dict[str, Any]] = []
    start_cursor: Optional[str] = None
    while True:
        resp = notion.blocks.children.list(block_id=block_id, start_cursor=start_cursor)
        all_blocks.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")
    return all_blocks


def heading_text(block: Dict[str, Any]) -> str:
    """
    Extract plain text from a heading block.
    
    Args:
        block (Dict[str, Any]): Notion block object
        
    Returns:
        str: Plain text content of the heading
    """
    t = block.get(block["type"], {}).get("rich_text", [])
    return (rt_to_latex(t) or "").strip()


def filter_for_resume_region(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return only blocks located after H1 'For Resume' and before H1 'Not For Resume'.
    
    This function implements the content filtering system where each Notion page
    can have sections marked for inclusion or exclusion from the CV.
    
    Args:
        blocks (List[Dict[str, Any]]): List of Notion blocks to filter
        
    Returns:
        List[Dict[str, Any]]: Filtered blocks that should appear on the CV
        
    Note:
        - If no 'For Resume' header is found, includes all content
        - If no 'Not For Resume' header is found, includes everything after 'For Resume'
        - This allows for flexible content organization in Notion
    """
    in_resume = True  # Start with True - include all content by default
    found_for_resume = False
    filtered: List[Dict[str, Any]] = []
    
    for b in blocks:
        tp = b.get("type")
        if tp == "heading_1":
            text_plain = (b[tp].get("rich_text", [{}])[0].get("plain_text", "").strip() if b[tp].get("rich_text") else "")
            if text_plain.lower() == "for resume":
                in_resume = True
                found_for_resume = True
                continue
            if text_plain.lower() == "not for resume":
                in_resume = False
                break  # everything after is ignored
        
        # Include content if:
        # 1. We never found a "For Resume" header (include all content), OR
        # 2. We found a "For Resume" header and we're currently in the resume section
        if not found_for_resume or in_resume:
            filtered.append(b)
    
    return filtered


def _render_list_block_item(notion: Client, block: Dict[str, Any], list_type: str, mode: str, level: int) -> str:
    """
    Render a single list item block to LaTeX.
    
    Handles both bulleted and numbered list items, including nested lists
    and mixed content within list items.
    
    Args:
        notion (Client): Authenticated Notion client
        block (Dict[str, Any]): The list item block to render
        list_type (str): Type of list ('bulleted_list_item' or 'numbered_list_item')
        mode (str): Rendering mode ('items' or 'paragraphs')
        level (int): Nesting level for indentation
        
    Returns:
        str: LaTeX formatted list item
    """
    payload = block[list_type]
    text = rt_to_latex(payload.get("rich_text", []))
    body = f"\\item {text}" if mode == "items" else f"\\item {text}"
    # children (nested list)
    if block.get("has_children"):
        children = list_children(notion, block["id"])
        if children:
            # Determine child list type by inspecting first child that is a list item
            child_items = [c for c in children if c.get("type") in ("bulleted_list_item", "numbered_list_item")]
            if child_items:
                lt = child_items[0]["type"]
                env = "itemize" if lt == "bulleted_list_item" else "enumerate"
                inner = []
                inner.append(f"\\begin{{{env}}}")
                for c in child_items:
                    inner.append(_render_list_block_item(notion, c, c["type"], mode, level + 1))
                inner.append(f"\\end{{{env}}}")
                body += "\n" + "\n".join(inner)
            else:
                # Non-list children under a list item → render as paragraph block(s)
                para = convert_blocks_to_latex(notion, children, mode=("paragraphs" if mode == "items" else mode))
                if para.strip():
                    if mode == "items":
                        body += "\n" + para
                    else:
                        body += "\n" + para
    return body


def convert_blocks_to_latex(notion: Client, blocks: List[Dict[str, Any]], mode: str) -> str:
    """
    Convert Notion blocks into LaTeX.
    
    This is the main function for converting Notion content to LaTeX format.
    It handles various block types including paragraphs, lists, quotes, code,
    and equations.
    
    Args:
        notion (Client): Authenticated Notion client
        blocks (List[Dict[str, Any]]): List of Notion blocks to convert
        mode (str): Rendering mode
            - 'items' → produce top-level "\item ..." lines only (for joblong environment)
            - 'paragraphs' → produce paragraphs; lists become full itemize/enumerate environments
            
    Returns:
        str: LaTeX formatted content
        
    Note:
        This function processes blocks sequentially and handles list runs
        (consecutive list items) as single environments for better formatting.
    """
    out: List[str] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        tp = b.get("type")
        if tp in ("paragraph", "quote", "equation", "code"):
            # Paragraph-like
            if tp == "paragraph":
                text = rt_to_latex(b[tp].get("rich_text", []))
            elif tp == "quote":
                inner = rt_to_latex(b[tp].get("rich_text", []))
                text = f"\\begin{{quote}}{inner}\\end{{quote}}"
            elif tp == "equation":
                expr = b[tp].get("expression", "")
                text = f"$ {latex_escape(expr)} $"
            elif tp == "code":
                content = b[tp].get("rich_text", [])
                inner = rt_to_latex(content)
                text = f"\\begin{{verbatim}}\n{inner}\n\\end{{verbatim}}"

            if text.strip():
                if mode == "items":
                    out.append(f"\\item {text}")
                else:
                    out.append(text)
            i += 1
            continue

        # List runs (bulleted/numbered)
        if tp in ("bulleted_list_item", "numbered_list_item"):
            run_type = tp
            run: List[Dict[str, Any]] = [b]
            j = i + 1
            while j < len(blocks) and blocks[j].get("type") == run_type:
                run.append(blocks[j])
                j += 1
            if mode == "items":
                # Flatten at top-level as \item ...; keep nested children as nested lists
                for item in run:
                    out.append(_render_list_block_item(notion, item, run_type, mode="items", level=0))
            else:
                env = "itemize" if run_type == "bulleted_list_item" else "enumerate"
                out.append(f"\\begin{{{env}}}")
                for item in run:
                    out.append(_render_list_block_item(notion, item, run_type, mode="paragraphs", level=0))
                out.append(f"\\end{{{env}}}")
            i = j
            continue

        # Headings inside the body (rare for your use) — ignore
        if tp.startswith("heading_"):
            i += 1
            continue

        # Other/unsupported block types → skip
        i += 1

    return "\n".join(out)

# ------------------------------
# Database → cv_data
# ------------------------------

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def fmt_date(d: Optional[str]) -> Optional[str]:
    """
    Format a date string to a readable format.
    
    Converts Notion date strings (ISO format) to "Month YYYY" format
    for display in the CV.
    
    Args:
        d (Optional[str]): Date string from Notion (ISO format or YYYY-MM-DD)
        
    Returns:
        Optional[str]: Formatted date string or original string if parsing fails
        
    Example:
        >>> fmt_date("2023-06-15")
        "Jun 2023"
        >>> fmt_date("2023-06-15T10:30:00Z")
        "Jun 2023"
    """
    if not d:
        return None
    try:
        # Notion date may be YYYY-MM-DD or full ISO timestamp
        if "T" in d:
            dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(d)
        return f"{MONTHS[dt.month-1]} {dt.year}"
    except Exception:
        return d  # fallback as-is

TYPES_LONG = {"Work Experience", "Leadership and Other Experience", "Projects"}
TYPES_SHORT = {"Education", "Awards", "Publications"}


def get_prop_text(props: Dict[str, Any], name: str) -> str:
    """
    Extract text content from a Notion property.
    
    Handles different Notion property types and extracts the plain text
    content for use in the CV.
    
    Args:
        props (Dict[str, Any]): Notion page properties
        name (str): Name of the property to extract
        
    Returns:
        str: Plain text content of the property
        
    Note:
        Supports title, rich_text, select, and checkbox property types.
    """
    p = props.get(name)
    if not p:
        return ""
    if p["type"] == "title":
        return "".join([t.get("plain_text", "") for t in p["title"]])
    if p["type"] == "rich_text":
        return "".join([t.get("plain_text", "") for t in p["rich_text"]])
    if p["type"] == "select":
        return (p["select"] or {}).get("name", "")
    if p["type"] == "checkbox":
        return "true" if p.get("checkbox") else "false"
    return ""


def get_date_range(props: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract start and end dates from Notion properties.
    
    Supports both regular date fields and date override field for complex date ranges.
    
    Args:
        props (Dict[str, Any]): Notion page properties
        
    Returns:
        Tuple[Optional[str], Optional[str], Optional[str]]: (start_date, end_date, date_display) formatted strings
    """
    # Check for date override first
    date_override = props.get("Date Override")
    if date_override and date_override.get("type") in ("text", "rich_text"):
        if date_override.get("type") == "text":
            override_text = date_override.get("text", {}).get("content", "")
        else:  # rich_text
            override_text = "".join([text.get("plain_text", "") for text in date_override.get("rich_text", [])])
        
        if override_text.strip():
            # Parse date override format: "Jan 2020 -- Dec 2021, Jan 2023 -- Present"
            # or "Jan 2020 -- Dec 2021" or "Jan 2020 -- Present"
            start_d, end_d = parse_date_override(override_text.strip())
            return start_d, end_d, override_text.strip()
    
    # Fall back to regular date fields
    sd = props.get("Start Date")
    ed = props.get("End Date")
    s = fmt_date(sd.get("date", {}).get("start")) if sd and sd.get("type") == "date" and sd.get("date") else None
    e = fmt_date(ed.get("date", {}).get("start")) if ed and ed.get("type") == "date" and ed.get("date") else None
    return s, e, None


def parse_date_override(override_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse date override text into start and end dates.
    
    Supports formats like:
    - "Jan 2020 -- Dec 2021, Jan 2023 -- Present"
    - "Jan 2020 -- Dec 2021" 
    - "Jan 2020 -- Present"
    - "Jan 2020 -- Dec 2021, Jan 2023 -- Dec 2024"
    
    Args:
        override_text (str): Date override text from Notion
        
    Returns:
        Tuple[Optional[str], Optional[str]]: (start_date, end_date) formatted strings
    """
    # Normalize different dash types to standard format
    normalized_text = override_text.replace("—", "--").replace("–", "--")
    
    # Handle multiple date ranges (e.g., "Jan 2020 -- Dec 2021, Jan 2023 -- Present")
    if "," in normalized_text:
        # For multiple ranges, use the earliest start and latest end
        ranges = [r.strip() for r in normalized_text.split(",")]
        start_dates = []
        end_dates = []
        
        for range_str in ranges:
            if " -- " in range_str:
                start_part, end_part = range_str.split(" -- ", 1)
                start_dates.append(start_part.strip())
                end_dates.append(end_part.strip())
        
        if start_dates and end_dates:
            # Find earliest start date
            earliest_start = min(start_dates, key=lambda x: parse_date_for_sorting(x))
            # Find latest end date (excluding "Present")
            end_dates_no_present = [d for d in end_dates if d.lower() != "present"]
            if end_dates_no_present:
                latest_end = max(end_dates_no_present, key=lambda x: parse_date_for_sorting(x))
            else:
                latest_end = "Present"
            return earliest_start, latest_end
    
    # Handle single date range
    if " -- " in normalized_text:
        start_part, end_part = normalized_text.split(" -- ", 1)
        return start_part.strip(), end_part.strip()
    
    # If no range separator, treat as start date only
    return normalized_text.strip(), None


def parse_date_for_sorting(date_str: str) -> Tuple[int, int]:
    """
    Parse a date string for sorting purposes.
    
    Args:
        date_str (str): Date string like "Jan 2020" or "Present"
        
    Returns:
        Tuple[int, int]: (year, month) for sorting
    """
    if not date_str or date_str.lower() == "present":
        return (9999, 12)  # Put "Present" at the end
    
    try:
        parts = date_str.split()
        if len(parts) == 2:
            month_name, year_str = parts
            year = int(year_str)
            month = MONTHS.index(month_name) + 1 if month_name in MONTHS else 0
            return (year, month)
    except (ValueError, IndexError):
        pass
    
    return (0, 0)  # Fallback for unparseable dates


def sort_entries_by_date(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort entries by date (newest first).
    
    Uses end_date if available, otherwise start_date. For date overrides,
    extracts the latest end date from the override string.
    
    Args:
        entries (List[Dict[str, Any]]): List of CV entries to sort
        
    Returns:
        List[Dict[str, Any]]: Sorted entries with newest first
    """
    def get_sort_date(entry: Dict[str, Any]) -> Tuple[int, int]:
        # For date overrides, extract the latest end date from the override string
        if entry.get("date_display"):
            return get_latest_end_date_from_override(entry["date_display"])
        
        # Use end_date if available, otherwise start_date
        date_str = entry.get("end_date") or entry.get("start_date")
        if not date_str:
            return (0, 0)  # Put entries without dates at the end
        
        return parse_date_for_sorting(date_str)
    
    return sorted(entries, key=get_sort_date, reverse=True)


def get_latest_end_date_from_override(override_text: str) -> Tuple[int, int]:
    """
    Extract the latest end date from a date override string for sorting.
    
    Args:
        override_text (str): Date override string like "Jan 2020 -- Dec 2021, Jan 2023 -- Present"
        
    Returns:
        Tuple[int, int]: (year, month) for sorting
    """
    if not override_text:
        return (0, 0)
    
    # Normalize different dash types to standard format
    normalized_text = override_text.replace("—", "--").replace("–", "--")
    
    # Handle multiple date ranges (e.g., "Jan 2020 -- Dec 2021, Jan 2023 -- Present")
    if "," in normalized_text:
        ranges = [r.strip() for r in normalized_text.split(",")]
        end_dates = []
        
        for range_str in ranges:
            if " -- " in range_str:
                start_part, end_part = range_str.split(" -- ", 1)
                end_dates.append(end_part.strip())
        
        if end_dates:
            # Find the latest end date (excluding "Present")
            end_dates_no_present = [d for d in end_dates if d.lower() != "present"]
            if end_dates_no_present:
                latest_end = max(end_dates_no_present, key=lambda x: parse_date_for_sorting(x))
                return parse_date_for_sorting(latest_end)
            else:
                return (9999, 12)  # All ranges end with "Present"
    
    # Handle single date range
    if " -- " in normalized_text:
        start_part, end_part = normalized_text.split(" -- ", 1)
        return parse_date_for_sorting(end_part.strip())
    
    # If no range separator, treat as start date only
    return parse_date_for_sorting(normalized_text.strip())


def fetch_notion_data(notion: Client, database_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch raw CV data from Notion database without sorting.
    
    Fetches all entries from the Notion database where "Show on CV?" is True,
    processes the content, and organizes it by section type. Does NOT sort entries.
    
    Args:
        notion (Client): Authenticated Notion client
        database_id (str): ID of the Notion database
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: Raw CV data organized by section type (unsorted)
        
    Note:
        This function handles pagination to retrieve all database entries
        and processes each entry's content from Notion blocks.
    """
    cv_data: Dict[str, List[Dict[str, Any]]] = {}
    start_cursor: Optional[str] = None

    while True:
        # Query the Notion Data Source directly (newer API): use data_sources.query
        resp = notion.data_sources.query(
            **{
                "data_source_id": database_id,
                "start_cursor": start_cursor,
                "filter": {
                    "property": "Show on CV?",
                    "checkbox": {"equals": True},
                },
            }
        )
        for page in resp.get("results", []):
            props = page.get("properties", {})
            page_id = page["id"]
            
            type_name = get_prop_text(props, "Type") or "Other"
            name = get_prop_text(props, "Title") or ""
            org = get_prop_text(props, "Organization")
            loc = get_prop_text(props, "Location")
            start_d, end_d, date_display = get_date_range(props)

            # Fetch and render the body from block children between the two H1s
            children = list_children(notion, page_id)
            filtered = filter_for_resume_region(children)
            mode = "items" if type_name in TYPES_LONG else "paragraphs"
            body_latex = convert_blocks_to_latex(notion, filtered, mode=mode)

            entry = {
                "name": name,
                "organization": org,
                "location": loc,
                "type": type_name,
                "start_date": start_d,
                "end_date": end_d,
                "date_display": date_display,
                "is_visible": True,
                "body_latex": body_latex,
            }
            cv_data.setdefault(type_name, []).append(entry)

        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")

    return cv_data


def sort_cv_data(cv_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Sort CV data by date (newest first) within each section.
    
    Args:
        cv_data (Dict[str, List[Dict[str, Any]]]): Raw CV data from Notion
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: CV data with entries sorted by date
    """
    for section_name, entries in cv_data.items():
        cv_data[section_name] = sort_entries_by_date(entries)

    return cv_data

# ------------------------------
# Render with Jinja2
# ------------------------------

def render_tex(cv_data: Dict[str, Any], template_file: str, out_file: str) -> None:
    """
    Render the CV data using Jinja2 template.
    
    Loads the LaTeX template, processes it with the CV data, and writes
    the result to the output file.
    
    Args:
        cv_data (Dict[str, Any]): Processed CV data from Notion
        template_file (str): Path to the Jinja2 template file
        out_file (str): Path to the output LaTeX file
        
    Raises:
        Exception: If there's an error reading the template or writing the output
    """
    env = Environment(loader=FileSystemLoader("."), autoescape=False, trim_blocks=True, lstrip_blocks=True)
    env.filters["latex_escape"] = latex_escape
    tmpl = env.get_template(template_file)
    tex = tmpl.render(cv_data=cv_data)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(tex)

# ------------------------------
# Main
# ------------------------------

def main(argv: List[str]) -> int:
    """
    Main entry point for the CV generator.
    
    Handles command line arguments, loads configuration, manages caching,
    and orchestrates the CV generation process.
    
    Args:
        argv (List[str]): Command line arguments
        
    Returns:
        int: Exit code (0 for success, non-zero for error)
        
    Environment Variables:
        NOTION_TOKEN: Required. Your Notion integration token
        DATA_SOURCE_ID: Required. The ID of your Notion database
        TEMPLATE_FILE: Optional. Template file (default: cv_template.tex)
        OUT_FILE: Optional. Output file (default: cv.tex)
        
    Command Line Options:
        --refresh, -r: Force refresh of cached data from Notion
        --sort-only, -s: Only sort cached data, don't fetch from Notion
        
    Note:
        The function implements a caching system to reduce API calls.
        Cache expires after 1 hour and can be refreshed with --refresh flag.
    """
    load_dotenv()
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("DATA_SOURCE_ID")
    template_file = os.getenv("TEMPLATE_FILE", "cv_template.tex")
    
    out_file = os.getenv("OUT_FILE", "cv.tex")
    cache_file = "notion_cache.json"
    
    # Check for command line flags
    force_refresh = "--refresh" in argv or "-r" in argv
    sort_only = "--sort-only" in argv or "-s" in argv

    if not notion_token or not database_id:
        print("ERROR: NOTION_TOKEN and DATA_SOURCE_ID must be set in .env", file=sys.stderr)
        return 2

    # Handle different modes
    if sort_only:
        # Sort-only mode: load from cache and sort, don't fetch from Notion
        if not os.path.exists(cache_file):
            print("ERROR: No cache file found. Use --refresh to fetch data from Notion first.", file=sys.stderr)
            return 3
        print("Sort-only mode: Loading data from cache…")
        with open(cache_file, 'r', encoding='utf-8') as f:
            cv_data = json.load(f)
    else:
        # Normal mode: check cache or fetch from Notion
        cv_data = None
        if not force_refresh and os.path.exists(cache_file):
            try:
                cache_age = time.time() - os.path.getmtime(cache_file)
                if cache_age < 3600:  # 1 hour
                    print("Loading data from cache…")
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cv_data = json.load(f)
                    print("Using cached data (less than 1 hour old)")
                else:
                    print("Cache is older than 1 hour, fetching fresh data…")
            except Exception as e:
                print(f"Error loading cache: {e}, fetching fresh data…")
        elif force_refresh:
            print("Force refresh requested, fetching fresh data…")

        if cv_data is None:
            notion = Client(auth=notion_token)
            print("Fetching data from Notion…")
            cv_data = fetch_notion_data(notion, database_id)
            
            # Save raw data to cache (unsorted)
            print("Saving data to cache…")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cv_data, f, indent=2, ensure_ascii=False)

    # Sort the data (whether from cache or fresh fetch)
    print("Sorting CV data…")
    cv_data = sort_cv_data(cv_data)

    print("Rendering LaTeX…")
    render_tex(cv_data, template_file=template_file, out_file=out_file)

    print(f"Wrote {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))