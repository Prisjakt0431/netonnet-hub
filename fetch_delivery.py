#!/usr/bin/env python3
"""
Fetches delivery data from Gotom reporting pages and writes delivery.json.
Run by GitHub Actions daily. Requires: pip install requests beautifulsoup4
"""

import re
import json
import time
import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Campaign registry ──────────────────────────────────────────────────
# market: "se" or "no" | type: "aon" or "pm" | id: Gotom task id | token: URL hash
CAMPAIGNS = [
# Sweden – AON
{"id": "882", "token": "d94e5fbaa9bbe1fefd4c59482b87d1d5", "name": "Netonnet SE – AON Februari", "market": "se", "type": "aon"},
{"id": "892", "token": "2395ac68eca37585e8d2c87123051fcc", "name": "Netonnet SE – AON Mars", "market": "se", "type": "aon"},
{"id": "894", "token": "c7471a1cec946cfb0d378849ee094574", "name": "Netonnet SE – AON April", "market": "se", "type": "aon"},
{"id": "1223", "token": "ec41c0ab91c33ce117713acad0832b37", "name": "Netonnet SE – AON Maj", "market": "se", "type": "aon"},

# Sweden – PM
{"id": "1044", "token": "cdddb3549b2617f405e4d376e4d64d83", "name": "Netonnet SE – Samsung TV Maj", "market": "se", "type": "pm"},
{"id": "1046", "token": "350e946254c62fd3e662512674987f59", "name": "Netonnet SE – Weber Maj", "market": "se", "type": "pm"},
{"id": "1045", "token": "a6e7bed96f0a4242b415d812ec4c3678", "name": "Netonnet SE – Pure Elscooter Maj", "market": "se", "type": "pm"},
{"id": "1047", "token": "96e75f52fc437ae51e8987a71cba3ea9", "name": "Netonnet SE – Gardena Maj-Juni", "market": "se", "type": "pm"},
{"id": "1048", "token": "96885f55687773a60beec2217faba6c1", "name": "Netonnet SE – Samsung Phones Maj-Juni", "market": "se", "type": "pm"},
{"id": "1049", "token": "78a5e88a79ecbeb2dff5bbc381a04165", "name": "Netonnet SE – Samsung Tablet Juni", "market": "se", "type": "pm"},
{"id": "1050", "token": "543741a2c665b4c1ce223151955dcfde", "name": "Netonnet SE – Samsung Phones Juni-Juli", "market": "se", "type": "pm"},
{"id": "1051", "token": "33730cdb3f2a5ebe89be8a94f3ff3d93", "name": "Netonnet SE – Ecovacs Juni-Juli", "market": "se", "type": "pm"},
{"id": "1055", "token": "adc6bbbf29848d0d099dff9b04b474f4", "name": "Netonnet SE – TCL Juni", "market": "se", "type": "pm"},
{"id": "1056", "token": "34db32b4bb0491ff091b263b84de6829", "name": "Netonnet SE – LG Juni", "market": "se", "type": "pm"},
{"id": "1094", "token": "388fdab050db0c6dd3edc46baebad3fa", "name": "Netonnet SE – Samsung TV Juni-Juli", "market": "se", "type": "pm"},
{"id": "1095", "token": "64844f52b20eb27c879ff5f3ec8f2908", "name": "Netonnet SE – Dreame Robotgräsklippare Juli", "market": "se", "type": "pm"},
{"id": "1096", "token": "367dae7fd17e0988a6c34147ab8fb68c", "name": "Netonnet SE – Dreame Robotdammsugare Juli", "market": "se", "type": "pm"},
{"id": "1198", "token": "8d045d613c7c217bd2ac71eae11fc8c9", "name": "Netonnet SE – Apple iPhone Juli", "market": "se", "type": "pm"},
{"id": "1199", "token": "5a7c5e1cf2bf5932ea716f70ed937e5b", "name": "Netonnet SE – Samsung Phones Aug", "market": "se", "type": "pm"},

# Norway – AON
{"id": "881", "token": "443c147680c5f218593e398e22a3faf1", "name": "Netonnet NO – AON Februari", "market": "no", "type": "aon"},
{"id": "893", "token": "e1d6c7a5ad02cb6b87b52d9d3b673ddc", "name": "Netonnet NO – AON Mars", "market": "no", "type": "aon"},
{"id": "895", "token": "1b6e682ab593f5bd50854b08029e0f44", "name": "Netonnet NO – AON April", "market": "no", "type": "aon"},
{"id": "1224", "token": "27d2af1f4393a7a9ed0d12352f79651c", "name": "Netonnet NO – AON Maj", "market": "no", "type": "aon"},
{"id": "1225", "token": "9a016c3dc65eb58fbb58f866fec951a3", "name": "Netonnet NO – AON Juni", "market": "no", "type": "aon"},
{"id": "1226", "token": "709ea8c2b531f3651f608273045d20ab", "name": "Netonnet NO – AON Juli", "market": "no", "type": "aon"},
{"id": "1141", "token": "d7153250fbf1167e7c56bfa4600f6792", "name": "Netonnet NO – AON Augusti", "market": "no", "type": "aon"},
{"id": "1142", "token": "33e14563174642e27dd5e9d80a8283bd", "name": "Netonnet NO – AON September", "market": "no", "type": "aon"},
{"id": "1143", "token": "6c8a2e4853fcd9a49cb95cf292513c13", "name": "Netonnet NO – AON Oktober", "market": "no", "type": "aon"},
{"id": "1144", "token": "47a94e165241f83cc951e2efc6b0994a", "name": "Netonnet NO – AON November", "market": "no", "type": "aon"},
{"id": "1145", "token": "8f808c0c7c058f2c710a25608d314a0e", "name": "Netonnet NO – AON December", "market": "no", "type": "aon"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (prisjakt delivery-checker/1.0)"}

def build_url(campaign):
    base = f"https://prisjakt.gotom.io/reporting-task-report/{campaign['id']}/{campaign['token']}"
    if campaign.get("duration"):
        base += "?reportingPeriod%5B1%5D=duration"
    return base

def parse_number(text):
    """'SEK 44\'688.90' or '0' or '' -> float"""
    text = re.sub(r"[A-Za-z]+", "", text).replace("'", "").replace(",", ".").strip()
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0

def parse_pct(text):
    """'87.50%' -> 87.5 | '' -> None"""
    text = text.replace("%", "").replace(",", ".").strip()
    if not text:
        return None
    try:
        return round(float(text), 1)
    except ValueError:
        return None

def identify_product(channel, ad_format, price_type):
    ch = channel.lower()
    af = ad_format.lower()
    pt = price_type.lower()
    if "audience extension" in ch or "- ae" in pt:
        return "A.E"
    if "roc" in af:
        return "ROC"
    if "welcome page" in af:
        return "Welcome Page"
    return None

def fetch_campaign(campaign):
    url = build_url(campaign)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Failed to fetch %s (%s): %s", campaign["name"], campaign["id"], e)
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        log.warning("No delivery table found for %s", campaign["name"])
        return {}

    delivery_table = tables[1]
    rows = delivery_table.find_all("tr")
    products = {}

    for row in rows[1:]:  # skip header row
        cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
        if len(cells) < 17:
            continue

        platform = cells[1]
        if "total" in platform.lower():
            continue  # skip summary rows

        channel = cells[2]
        ad_format = cells[3]
        price_type = cells[8]
        units_booked_str = cells[9]      # e.g. "457'967"
        costs_booked_str = cells[10]      # e.g. "SEK 44'688.90"
        impressions_str = cells[11]       # e.g. "302'179"
        clicks_str = cells[13]            # e.g. "718 edit close"
        ctr_str = cells[14]               # e.g. "0.16%"
        value_delivered_str = cells[16]   # e.g. "SEK 38'000.00"

        product = identify_product(channel, ad_format, price_type)
        if not product:
            log.debug("Unrecognised row: ch=%s af=%s pt=%s", channel, ad_format, price_type)
            continue

        units_booked = parse_number(units_booked_str)
        impressions = parse_number(impressions_str)
        booked = parse_number(costs_booked_str)
        delivered = parse_number(value_delivered_str)
        clicks = int(parse_number(clicks_str))

        # Delivery pct from impressions / units_booked (stable, no HTML noise)
        if units_booked and units_booked > 0:
            pct = round(impressions / units_booked * 100, 1)
        else:
            pct = None

        # CTR from table (col 14) — 2 decimal places
        try:
            ctr = round(float(ctr_str.replace('%', '').replace(',', '.').strip()), 2)
        except (ValueError, AttributeError):
            ctr = None

        products[product] = {
            "booked": booked,
            "delivered": delivered,
            "pct": pct,  # None if not yet started
            "impressions": int(impressions),
            "clicks": clicks,
            "ctr": ctr,  # % e.g. 0.16
        }

    return products

def main():
    result = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "campaigns": {}
    }

    for c in CAMPAIGNS:
        log.info("Fetching %s (id=%s)…", c["name"], c["id"])
        products = fetch_campaign(c)
        result["campaigns"][c["id"]] = {
            "name": c["name"],
            "market": c["market"],
            "type": c.get("type", "aon"),
            "products": products,
        }
        time.sleep(1)  # be polite

    with open("delivery.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info("Wrote delivery.json with %d campaigns.", len(result["campaigns"]))

if __name__ == "__main__":
    main()
