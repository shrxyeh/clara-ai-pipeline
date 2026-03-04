#!/usr/bin/env python3
"""
LLM-based transcript extraction using Google Gemini.

Primary extraction layer — falls back gracefully to regex if the package
is not installed, GEMINI_API_KEY is not set, or any API call fails.
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEMO_EXTRACTION_PROMPT = """\
Extract structured business configuration from this demo call transcript.

RULES:
- Only extract information EXPLICITLY stated in the transcript.
- Never invent, assume, or infer unstated details.
- If a field is not mentioned, set it to null.
- For business hours days, use full names: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday.
- For times, use 24-hour HH:MM format such as 07:00 or 18:00.
- For timezone, use IANA format such as America/New_York or America/Chicago.
- For emergency_definition, list exact trigger phrases from the transcript.
- For integration_constraints, copy exact constraint phrases from the transcript.
- Return ONLY valid JSON with no comments, no markdown, no explanation.

Required JSON structure (replace example values with actual extracted data):

{
  "company_name": null,
  "business_hours": {
    "days": [],
    "start": null,
    "end": null,
    "timezone": null,
    "notes": null
  },
  "office_address": {
    "full": null,
    "street": null,
    "city": null,
    "state": null,
    "zip": null
  },
  "services_supported": [],
  "emergency_definition": [],
  "emergency_routing_rules": {
    "primary_contact": null,
    "primary_phone": null,
    "secondary_contact": null,
    "secondary_phone": null,
    "fallback": null,
    "order": []
  },
  "non_emergency_routing_rules": {
    "action": null,
    "voicemail_number": null,
    "callback_promise": null,
    "notes": null
  },
  "call_transfer_rules": {
    "timeout_seconds": null,
    "retries": null,
    "what_to_say_if_transfer_fails": null,
    "transfer_announcement": null
  },
  "integration_constraints": []
}

TRANSCRIPT:
{transcript}
"""

ONBOARDING_DELTA_PROMPT = """\
Analyze this ONBOARDING call transcript and extract ONLY the fields that changed or were newly confirmed.

RULES:
- Only include fields explicitly discussed or updated in this call.
- Do not include fields that were not mentioned.
- For lists, include only NEW items being added.
- Never invent or assume anything.
- For days, use full names: Monday, Tuesday, etc.
- For times, use 24-hour HH:MM format.
- For timezone, use IANA format.
- Return ONLY valid JSON with no comments, no markdown, no explanation.
- Set "changed_fields" to a list of top-level field names that changed.

Required JSON structure (only populate fields that actually changed):

{
  "changed_fields": [],
  "business_hours": {
    "days": [],
    "start": null,
    "end": null,
    "timezone": null,
    "notes": null
  },
  "office_address": {
    "full": null,
    "street": null,
    "city": null,
    "state": null,
    "zip": null
  },
  "services_supported": [],
  "emergency_definition": [],
  "emergency_routing_rules": {
    "primary_contact": null,
    "primary_phone": null,
    "secondary_contact": null,
    "secondary_phone": null,
    "fallback": null,
    "order": []
  },
  "non_emergency_routing_rules": {
    "action": null,
    "voicemail_number": null,
    "callback_promise": null,
    "notes": null
  },
  "call_transfer_rules": {
    "timeout_seconds": null,
    "retries": null,
    "what_to_say_if_transfer_fails": null,
    "transfer_announcement": null
  },
  "integration_constraints": []
}

TRANSCRIPT:
{transcript}
"""

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def extract_with_gemini(
    text: str,
    account_id: str,
    mode: str = "demo",
) -> Optional[dict]:
    """
    Extract structured data from a transcript using Gemini.

    Args:
        text:       Raw transcript text.
        account_id: Used for logging only.
        mode:       "demo" for Pipeline A, "onboarding" for Pipeline B delta.

    Returns:
        Parsed dict on success, None if unavailable or failed.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.debug(f"[{account_id}] google-genai not installed — using regex fallback")
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.debug(f"[{account_id}] GEMINI_API_KEY not set — using regex fallback")
        return None

    prompt_template = DEMO_EXTRACTION_PROMPT if mode == "demo" else ONBOARDING_DELTA_PROMPT
    prompt = prompt_template.replace("{transcript}", text)

    client = genai.Client(api_key=api_key)

    for model_name in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    max_output_tokens=4096,
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            result = json.loads(raw)
            logger.info(f"[{account_id}] LLM extraction successful ({model_name}, mode={mode})")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"[{account_id}] {model_name} returned invalid JSON ({e}) — trying next model")
            continue
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                logger.warning(f"[{account_id}] {model_name} quota exceeded — trying next model")
            else:
                logger.warning(f"[{account_id}] {model_name} failed ({err[:80]}) — trying next model")
            continue

    logger.warning(f"[{account_id}] All Gemini models failed — using regex fallback")
    return None
