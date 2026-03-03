#!/usr/bin/env python3
"""
Rule-based transcript extraction engine.

Parses demo/onboarding call transcripts and extracts structured data
into the AccountMemo schema using regex + keyword matching.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DAY_ALIASES = {
    "monday": "Monday", "mon": "Monday",
    "tuesday": "Tuesday", "tue": "Tuesday", "tues": "Tuesday",
    "wednesday": "Wednesday", "wed": "Wednesday",
    "thursday": "Thursday", "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday",
    "friday": "Friday", "fri": "Friday",
    "saturday": "Saturday", "sat": "Saturday",
    "sunday": "Sunday", "sun": "Sunday",
}

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TIMEZONE_MAP = {
    "eastern": "America/New_York", "est": "America/New_York", "edt": "America/New_York",
    "central": "America/Chicago", "cst": "America/Chicago", "cdt": "America/Chicago",
    "mountain": "America/Denver", "mst": "America/Denver", "mdt": "America/Denver",
    "pacific": "America/Los_Angeles", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "alaska": "America/Anchorage", "akst": "America/Anchorage",
    "hawaii": "Pacific/Honolulu", "hst": "Pacific/Honolulu",
}

SERVICE_KEYWORDS = [
    "hvac", "heating", "ventilation", "air conditioning", "air conditioner", "ac repair",
    "plumbing", "drain", "drain cleaning", "water heater", "sewage",
    "electrical", "electrician", "wiring", "panel",
    "refrigeration", "chiller", "building automation",
    "fire damage", "water damage", "mold remediation", "sewage cleanup",
    "biohazard", "crime scene cleanup", "restoration",
    "fire suppression", "sprinkler",
    "mechanical", "boiler", "ventilation",
    "chimney", "pest control", "locksmith",
]

EMERGENCY_KEYWORDS = [
    "no heat", "no heating", "no hot water", "heat out",
    "gas leak", "gas smell",
    "burst pipe", "broken pipe", "pipe burst",
    "flooding", "flood", "active water",
    "no power", "power outage", "complete outage",
    "electrical fire", "arcing", "sparks",
    "exposed wiring",
    "panel failure",
    "refrigeration failure", "chiller failure",
    "sewage backup", "sewage overflow",
    "fire damage", "smoke damage",
    "property damage", "safety risk", "immediate danger",
    "ammonia leak", "chemical hazard",
    "elevator failure",
    "mold", "biohazard",
    "banging noise", "screeching noise", "burning smell",
    "water heater explosion",
    "temperature loss",
]

WORD_TIMES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "noon": 12, "midnight": 0,
}


def _normalize_time(raw: str) -> Optional[str]:
    """Convert '7 AM', '7:30 AM', '14:00', 'seven AM', 'noon' → '07:00' / '14:00'."""
    raw_stripped = raw.strip()
    raw_up = raw_stripped.upper()

    m = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)?$', raw_up)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        if ap == "PM" and h != 12:
            h += 12
        if ap == "AM" and h == 12:
            h = 0
        return f"{h:02d}:{mi:02d}"

    m = re.match(r'^(\d{1,2})\s*(AM|PM)?$', raw_up)
    if m:
        h, ap = int(m.group(1)), m.group(2)
        if ap == "PM" and h != 12:
            h += 12
        if ap == "AM" and h == 12:
            h = 0
        return f"{h:02d}:00"

    raw_low = raw_stripped.lower()
    for word, num in WORD_TIMES.items():
        pattern = re.compile(r'\b' + word + r'\b(?:\s*(am|pm))?', re.IGNORECASE)
        wm = pattern.match(raw_low)
        if wm:
            h = num
            ap = (wm.group(1) or "").upper()
            if ap == "PM" and h != 12:
                h += 12
            if ap == "AM" and h == 12:
                h = 0
            return f"{h:02d}:00"

    return None


def _parse_days_range(text: str) -> list:
    """Parse 'Monday through Friday' or 'Monday to Friday' → list of day names."""
    text_lower = text.lower()
    range_match = re.search(
        r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)'
        r'\s+(?:through|to|thru|-)\s+'
        r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)',
        text_lower
    )
    if range_match:
        start_day = DAY_ALIASES.get(range_match.group(1))
        end_day = DAY_ALIASES.get(range_match.group(2))
        if start_day and end_day:
            si = DAY_ORDER.index(start_day)
            ei = DAY_ORDER.index(end_day)
            return DAY_ORDER[si:ei + 1]

    found = []
    for alias, canonical in DAY_ALIASES.items():
        if re.search(r'\b' + alias + r'\b', text_lower) and canonical not in found:
            found.append(canonical)
    return sorted(set(found), key=lambda d: DAY_ORDER.index(d)) if found else []


def _extract_phone(text: str) -> Optional[str]:
    m = re.search(r'\b(\d{3}[-.\s]\d{3}[-.\s]\d{4}(?:\s*(?:ext|x|extension)\.?\s*\d+)?)\b', text)
    return m.group(1).strip() if m else None


def _extract_all_phones(text: str) -> list:
    return re.findall(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}(?:\s*(?:ext|x|extension)\.?\s*\d+)?\b', text)


def _extract_timezone(text: str) -> Optional[str]:
    text_lower = text.lower()
    for alias, tz in TIMEZONE_MAP.items():
        if re.search(r'\b' + alias + r'\b', text_lower):
            return tz
    return None


US_STATES = {
    "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
    "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
    "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
    "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada",
    "New Hampshire","New Jersey","New Mexico","New York","North Carolina",
    "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
    "South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
    "Virginia","Washington","West Virginia","Wisconsin","Wyoming",
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY",
}


def _extract_address(text: str) -> Optional[dict]:
    """Extract street address, supporting full state names and abbreviations."""
    state_pattern = '|'.join(
        re.escape(s) for s in sorted(US_STATES, key=len, reverse=True)
    )
    pattern = re.compile(
        r'(\d{3,5}\s+[A-Z][a-zA-Z0-9\s\.\-]+?'
        r'(?:Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Blvd|Boulevard|Way|Lane|Ln|Court|Ct|Place|Pl|N\.|S\.|E\.|W\.)?'
        r'(?:\s*,?\s*(?:Suite|Ste|Unit|Apt|#)\.?\s*\d+)?'
        r'\s*,\s*[A-Za-z\s]{2,25}'
        r'\s*,\s*(?:' + state_pattern + r')'
        r'(?:\s*,?\s*\d{5}(?:-\d{4})?)?)',
        re.MULTILINE
    )
    m = pattern.search(text)
    if m:
        full = re.sub(r'\s+', ' ', m.group(0).strip().rstrip('.'))
        parts = [p.strip() for p in full.split(',')]
        result = {"full": full}
        if len(parts) >= 1:
            result["street"] = parts[0]
        if len(parts) >= 2:
            result["city"] = parts[1]
        if len(parts) >= 3:
            last = parts[-1].strip()
            second_last = parts[-2].strip() if len(parts) >= 4 else None
            if re.match(r'^\d{5}(-\d{4})?$', last):
                result["zip"] = last
                if second_last:
                    result["state"] = second_last
            else:
                tokens = last.split()
                zip_tokens = [t for t in tokens if re.match(r'^\d{5}', t)]
                state_tokens = [t for t in tokens if not re.match(r'^\d', t)]
                result["state"] = ' '.join(state_tokens) if state_tokens else None
                result["zip"] = zip_tokens[0] if zip_tokens else None
        return result

    simple = re.search(
        r'\b(\d{3,5}[A-Za-z\s\.\,]+(?:Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Way|Blvd|Lane|Ln)[A-Za-z\s\.\,]*\d{5})\b',
        text
    )
    if simple:
        full = simple.group(0).strip()
        return {"full": full, "street": None, "city": None, "state": None, "zip": None}

    return None


def _extract_services(text: str) -> list:
    text_lower = text.lower()
    found = []
    for kw in SERVICE_KEYWORDS:
        if kw in text_lower and kw not in found:
            found.append(kw.title())
    return found


def _extract_emergencies(text: str) -> list:
    text_lower = text.lower()
    found = []
    for kw in EMERGENCY_KEYWORDS:
        if kw in text_lower:
            trigger = kw.replace(' ', '_').upper()
            if trigger not in [f.upper().replace(' ', '_') for f in found]:
                found.append(kw)
    return list(dict.fromkeys(found))


def _extract_integration_constraints(text: str) -> list:
    constraints = []
    for pattern_str in [
        r'never\s+(?:create|book|schedule|log|add|enter)\s+[^.!?\n]{5,80}',
        r'do\s+not\s+(?:create|book|schedule|log|add|enter)\s+[^.!?\n]{5,80}',
    ]:
        for m in re.finditer(pattern_str, text, re.IGNORECASE):
            c = m.group(0).strip().rstrip(',')
            if c not in constraints:
                constraints.append(c)

    for m in re.finditer(
        r'(?:ServiceTitan|ServiceTrade|FieldEdge|Xactimate|Dash|HouseCall Pro)\b[^.!?\n]{0,200}(?:never|only|no|don\'t|constraint|not allowed)[^.!?\n]{0,100}',
        text, re.IGNORECASE
    ):
        snippet = m.group(0).strip()
        if snippet and snippet not in constraints:
            constraints.append(snippet[:150])

    return constraints


def _extract_routing_contacts(text: str, context_keywords: list) -> dict:
    result = {
        "primary_contact": None, "primary_phone": None,
        "secondary_contact": None, "secondary_phone": None,
        "fallback": None, "order": []
    }

    lines = text.split('\n')
    contact_lines = []
    capture = False
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in context_keywords):
            capture = True
        if capture:
            contact_lines.append(line)
            if len(contact_lines) > 15:
                break

    context_text = '\n'.join(contact_lines)
    phones = _extract_all_phones(context_text)

    first_match = re.search(
        r'(?:first(?:ly)?|primary|1st|call me|try\s+(?:me|my))[^\n]{0,60}?'
        r'(?:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[,\s]+(?:at\s+)?)?'
        r'(\d{3}[-.\s]\d{3}[-.\s]\d{4})',
        context_text, re.IGNORECASE
    )
    second_match = re.search(
        r'(?:second(?:ly)?|backup|2nd|if\s+(?:I|he|she|they)\s+(?:don\'t|doesn\'t|fail))[^\n]{0,60}?'
        r'(?:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[,\s]+(?:at\s+)?)?'
        r'(\d{3}[-.\s]\d{3}[-.\s]\d{4})',
        context_text, re.IGNORECASE
    )

    if first_match:
        result["primary_contact"] = first_match.group(1)
        result["primary_phone"] = first_match.group(2)
    elif phones:
        result["primary_phone"] = phones[0]

    if second_match:
        result["secondary_contact"] = second_match.group(1)
        result["secondary_phone"] = second_match.group(2)
    elif len(phones) > 1:
        result["secondary_phone"] = phones[1]

    fallback_match = re.search(
        r'(?:if both fail|fallback|last resort|if (?:neither|all) (?:fail|answer|pick up))[^.!?\n]{10,200}',
        context_text, re.IGNORECASE
    )
    if fallback_match:
        result["fallback"] = fallback_match.group(0).strip()

    if phones:
        result["order"] = phones[:3]

    return result


def _extract_transfer_rules(text: str) -> dict:
    rules = {
        "timeout_seconds": None,
        "retries": None,
        "what_to_say_if_transfer_fails": None,
        "transfer_announcement": None
    }

    timeout_match = re.search(
        r'(?:give it|wait|timeout|after|within)\s+(\d+)\s*seconds?',
        text, re.IGNORECASE
    )
    if timeout_match:
        rules["timeout_seconds"] = int(timeout_match.group(1))

    retry_match = re.search(
        r'(\d+|one|two|three|once|twice)\s+retr(?:y|ies)',
        text, re.IGNORECASE
    )
    if retry_match:
        word = retry_match.group(1).lower()
        word_to_num = {"one": 1, "once": 1, "two": 2, "twice": 2, "three": 3}
        rules["retries"] = word_to_num.get(word, int(word) if word.isdigit() else None)

    # Prefer quoted phrases for the transfer announcement
    announcement_match = re.search(
        r'(?:say|tell the caller|tell them|always say)[^"\']*["\u201c\u201d]([^"\']{10,150})["\u201c\u201d]',
        text, re.IGNORECASE
    )
    if announcement_match:
        rules["transfer_announcement"] = announcement_match.group(1).strip()
    else:
        hold_match = re.search(
            r'(?:Please hold|One moment|Hold (?:on|please)|I\'?m (?:connecting|transferring))[^.!?]{5,100}',
            text, re.IGNORECASE
        )
        if hold_match:
            rules["transfer_announcement"] = hold_match.group(0).strip()
        else:
            tell_match = re.search(
                r'tell the caller (?:they\'?re|that they\'?re|they are)[^.!?\n]{5,80}',
                text, re.IGNORECASE
            )
            if tell_match:
                rules["transfer_announcement"] = "You are being connected to our team now."

    fail_match = re.search(
        r'(?:if (?:the )?transfer fails?|if (?:both|all) (?:fail|calls? fail))[^.!?\n]{10,200}',
        text, re.IGNORECASE
    )
    if fail_match:
        rules["what_to_say_if_transfer_fails"] = fail_match.group(0).strip()

    return rules


def _extract_business_hours(text: str) -> dict:
    hours = {"days": None, "start": None, "end": None, "timezone": None, "notes": None}

    time_token = r'(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|noon|midnight)|\d{1,2}(?::\d{2})?)(?:\s*(?:AM|PM|am|pm))?'
    time_range = re.search(
        r'(' + time_token + r')\s+(?:to|-|through)\s+(' + time_token + r')',
        text, re.IGNORECASE
    )
    if time_range:
        start_raw = time_range.group(1)
        end_raw = time_range.group(2)
        if re.search(r'am|pm', start_raw, re.IGNORECASE) or re.search(r'am|pm', end_raw, re.IGNORECASE):
            hours["start"] = _normalize_time(start_raw)
            hours["end"] = _normalize_time(end_raw)
        else:
            context = text[time_range.start():time_range.start()+80]
            am_pm_match = re.search(r'\b(am|pm)\b', context, re.IGNORECASE)
            suffix = am_pm_match.group(1).upper() if am_pm_match else ""
            hours["start"] = _normalize_time(start_raw + (" AM" if not suffix else ""))
            hours["end"] = _normalize_time(end_raw + (" " + suffix if suffix else ""))

    if not hours["start"]:
        broader = re.search(
            r'(\d{1,2}(?::\d{2})?)\s*(?:AM|PM)?\s+(?:to|-)\s+(\d{1,2}(?::\d{2})?)\s*(?:AM|PM)',
            text, re.IGNORECASE
        )
        if broader:
            hours["start"] = _normalize_time(broader.group(1))
            hours["end"] = _normalize_time(broader.group(2))

    days = _parse_days_range(text)
    if days:
        hours["days"] = days

    tz = _extract_timezone(text)
    if tz:
        hours["timezone"] = tz

    return hours


def _extract_account_id(text: str) -> Optional[str]:
    m = re.search(r'ACCOUNT:\s*(ACC-\d+)', text, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _extract_company_name(text: str) -> Optional[str]:
    m = re.search(r'COMPANY:\s*(.+)', text)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"(?:we'?re|this is|I'?m with)\s+([A-Z][A-Za-z\s&]+?)(?:\s*—|\s*,|\s*\.|$)", text)
    if m2:
        return m2.group(1).strip()
    return None


def _extract_source(text: str) -> str:
    text_upper = text.upper()
    if "TYPE: DEMO" in text_upper:
        return "demo_call"
    if "TYPE: ONBOARDING" in text_upper:
        return "onboarding_call"
    return "manual"


def _extract_non_emergency_routing(text: str) -> dict:
    rules = {"action": None, "voicemail_number": None, "callback_promise": None, "notes": None}
    text_lower = text.lower()

    if "voicemail" in text_lower or "leave a message" in text_lower:
        rules["action"] = "voicemail"
        phones = _extract_all_phones(text)
        if phones:
            rules["voicemail_number"] = phones[-1]
    elif "message and callback" in text_lower or "take a message" in text_lower:
        rules["action"] = "message_and_callback"

    callback_match = re.search(
        r'(?:call(?:ing)? (?:them|you|the caller) back|callback|follow(?:\s|-)?up)\s+'
        r'(?:within|in|by)\s+(.{5,50}?)(?:\.|,|$)',
        text, re.IGNORECASE
    )
    if callback_match:
        rules["callback_promise"] = callback_match.group(0).strip()

    if "next business day" in text_lower:
        rules["callback_promise"] = "next business day"

    return rules


def _compute_confidence(memo: dict) -> dict:
    confidence = {}
    required_fields = [
        "company_name", "business_hours", "emergency_definition",
        "emergency_routing_rules", "call_transfer_rules"
    ]
    for field in required_fields:
        val = memo.get(field)
        if val is None:
            confidence[field] = "missing"
        elif isinstance(val, dict):
            filled = sum(1 for v in val.values() if v is not None)
            total = len(val)
            confidence[field] = "high" if filled > total * 0.7 else "medium" if filled > 0 else "low"
        elif isinstance(val, list):
            confidence[field] = "high" if len(val) > 0 else "low"
        else:
            confidence[field] = "high"
    return confidence


def _identify_unknowns(memo: dict) -> list:
    unknowns = []
    bh = memo.get("business_hours") or {}
    if not bh.get("days"):
        unknowns.append("Business hours days not found in transcript")
    if not bh.get("start") or not bh.get("end"):
        unknowns.append("Business hours open/close time not found in transcript")
    if not bh.get("timezone"):
        unknowns.append("Timezone not specified — confirm with client")

    er = memo.get("emergency_routing_rules") or {}
    if not er.get("primary_phone"):
        unknowns.append("Emergency primary contact phone number not found")

    if not memo.get("emergency_definition"):
        unknowns.append("Emergency triggers not defined — what counts as an emergency?")

    if not memo.get("services_supported"):
        unknowns.append("Services supported not identified from transcript")

    return unknowns


def extract_memo(text: str, source_file: str = "") -> dict:
    """
    Parse a transcript and return a structured account memo dict.
    Missing fields are left as None and surfaced in questions_or_unknowns.
    """
    logger.info(f"Extracting memo from: {source_file or 'input text'}")

    account_id = _extract_account_id(text) or "ACC-UNKNOWN"
    company_name = _extract_company_name(text)
    source = _extract_source(text)
    now = datetime.now(timezone.utc).isoformat()

    bh = _extract_business_hours(text)
    if not any(bh.values()):
        bh = None

    address = _extract_address(text)
    services = _extract_services(text)
    emergencies = _extract_emergencies(text)

    emergency_routing = _extract_routing_contacts(
        text,
        ["emergency", "who should", "who to call", "emergency routing", "dispatch"]
    )
    non_emergency = _extract_non_emergency_routing(text)
    transfer = _extract_transfer_rules(text)
    constraints = _extract_integration_constraints(text)

    bh_days = ", ".join(bh["days"]) if bh and bh.get("days") else "your business hours"
    bh_start = bh["start"] if bh and bh.get("start") else "opening time"
    bh_end = bh["end"] if bh and bh.get("end") else "closing time"
    bh_tz = bh["timezone"].split("/")[-1] if bh and bh.get("timezone") else ""

    office_hours_summary = (
        f"During business hours ({bh_days} {bh_start}–{bh_end} {bh_tz}), "
        f"calls are answered and routed to the main office or scheduling desk. "
        f"If transfer fails, a message is taken and callback is promised."
    ) if bh else None

    after_hours_summary = (
        f"After hours, the agent confirms whether the issue is an emergency. "
        f"Emergency calls are immediately routed to on-call staff. "
        f"Non-emergency calls receive a message-taking flow with a next-business-day callback promise."
    )

    memo = {
        "account_id": account_id,
        "company_name": company_name,
        "version": "v1",
        "created_at": now,
        "updated_at": None,
        "source": source,
        "business_hours": bh,
        "office_address": address,
        "services_supported": services if services else None,
        "emergency_definition": emergencies if emergencies else None,
        "emergency_routing_rules": emergency_routing if any(emergency_routing.values()) else None,
        "non_emergency_routing_rules": non_emergency if any(non_emergency.values()) else None,
        "call_transfer_rules": transfer if any(transfer.values()) else None,
        "integration_constraints": constraints if constraints else None,
        "after_hours_flow_summary": after_hours_summary,
        "office_hours_flow_summary": office_hours_summary,
        "questions_or_unknowns": None,
        "notes": f"Extracted from {source} transcript via rule-based engine.",
        "extraction_confidence": None,
    }

    memo["extraction_confidence"] = _compute_confidence(memo)
    unknowns = _identify_unknowns(memo)
    memo["questions_or_unknowns"] = unknowns if unknowns else None

    logger.info(
        f"Extraction complete for {account_id}: "
        f"confidence={memo['extraction_confidence']}, unknowns={len(unknowns)}"
    )
    return memo


def extract_onboarding_updates(text: str, source_file: str = "") -> dict:
    """
    Extract the delta (changed/confirmed fields) from an onboarding transcript.
    Returns only fields that were explicitly updated — does not overwrite untouched v1 data.
    """
    logger.info(f"Extracting onboarding updates from: {source_file or 'input text'}")

    full = extract_memo(text, source_file)
    full["version"] = "v2"
    full["source"] = "onboarding_call"

    updates = {}
    text_lower = text.lower()

    change_signals = [
        "changed", "change", "updated", "update", "new", "now", "actually",
        "correction", "correct that", "revised", "revised to", "pushed to",
        "extended", "reduced", "different", "moved to", "instead",
    ]

    changed_lines = [
        line.strip() for line in text.split('\n')
        if any(sig in line.lower() for sig in change_signals)
    ]

    bh = _extract_business_hours(text)
    if bh and any(bh.values()):
        time_change = re.search(
            r'(?:changed|now|extended|pushed|open|opens)\s+[^.]{0,50}'
            r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM))',
            text, re.IGNORECASE
        )
        if time_change or any(s in text_lower for s in ["changed", "extended", "pushed to", "now open"]):
            updates["business_hours"] = bh

    address = _extract_address(text)
    if address and re.search(r'(?:new (?:location|office|address)|second (?:location|office)|moved)', text, re.IGNORECASE):
        updates["office_address"] = address

    er = _extract_routing_contacts(text, ["emergency", "dispatch", "routing"])
    if er and any(er.values()):
        if re.search(r'(?:number changed|new (?:number|cell)|updated to|changed to|correct number)', text, re.IGNORECASE):
            updates["emergency_routing_rules"] = er

    tr = _extract_transfer_rules(text)
    if tr and any(tr.values()):
        if re.search(r'(?:change|reduce|extend|want to change|now want)\s+(?:that|the timeout|the retry)', text, re.IGNORECASE):
            updates["call_transfer_rules"] = tr

    new_emergencies = _extract_emergencies(text)
    if new_emergencies and re.search(r'(?:add|also add|also include|new emergency)', text, re.IGNORECASE):
        updates["emergency_definition"] = new_emergencies

    new_constraints = _extract_integration_constraints(text)
    if new_constraints:
        updates["integration_constraints"] = new_constraints

    new_services = _extract_services(text)
    if new_services and re.search(r'(?:added a service|new service|we now do|also do)', text, re.IGNORECASE):
        updates["services_supported"] = new_services

    updates["_onboarding_changed_lines"] = changed_lines
    updates["_source_file"] = source_file

    logger.info(
        f"Onboarding delta extracted for {full['account_id']}: "
        f"changed_fields={list(k for k in updates if not k.startswith('_'))}"
    )

    return {"full_extraction": full, "delta": updates}


if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python extractor.py <transcript.txt>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        text = f.read()
    result = extract_memo(text, sys.argv[1])
    print(json.dumps(result, indent=2))
