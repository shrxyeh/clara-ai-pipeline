#!/usr/bin/env python3
"""
Retell Agent Draft Spec generator.

Takes an AccountMemo dict and produces a RetellAgentSpec JSON.
Prompts are built deterministically from memo fields.
Enforces prompt hygiene: office/after-hours flows, transfer protocol, no internal tool exposure.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are {agent_name}, a professional AI receptionist for {company_name}.
Your job is to help callers by routing their calls, collecting essential information, and ensuring they receive the help they need.

IMPORTANT RULES:
- Be {tone}: professional, helpful, and clear.
- Never reveal that you are using any automated systems or internal routing processes.
- Only collect information needed for routing: caller name, callback number, and when relevant, address.
- Do not ask unnecessary questions. Keep the conversation focused.
- Always confirm the caller's details before ending the call.
- If you cannot help, assure the caller that a team member will follow up promptly.

---

## OFFICE HOURS FLOW
(Use when the call is received {business_hours_days} between {business_hours_start} and {business_hours_end} {timezone})

1. GREET: "Thank you for calling {company_name}. This is {agent_name}. How can I help you today?"
2. UNDERSTAND PURPOSE: Listen to the caller's need. Clarify briefly if unclear.
3. COLLECT CALLER INFO: Ask for their name and best callback number.
   - "Could I get your name and the best number to reach you?"
4. ROUTE / TRANSFER: Attempt to transfer to the main team.
   - Say: "{transfer_announcement}" then initiate the transfer.
   - If transfer fails after {timeout_seconds} seconds: go to TRANSFER FAIL PROTOCOL.
5. TRANSFER FAIL PROTOCOL:
   - Say: "{transfer_fail_message}"
   - Confirm you have their name and number. Offer a callback confirmation.
   - "I have your details and our team will call you back shortly."
6. CONFIRM NEXT STEPS: "We'll have someone follow up with you. Is there anything else I can help you with?"
7. CLOSE: "Thank you for calling {company_name}. Have a great day."

---

## AFTER-HOURS FLOW
(Use when the call is received outside of {business_hours_days} {business_hours_start}–{business_hours_end} {timezone})

1. GREET: "Thank you for calling {company_name}. You've reached us outside of our regular business hours. This is {agent_name}."
2. UNDERSTAND PURPOSE: "I want to make sure I connect you with the right support. Can you briefly describe what's happening?"
3. DETERMINE IF EMERGENCY:
   Ask: "Is this an urgent issue that needs immediate attention?" or assess from description.
   Emergency triggers include: {emergency_triggers}

   IF EMERGENCY:
   4a. COLLECT INFO IMMEDIATELY:
       - "I'm going to get someone on the line for you right away. Can I get your name, callback number, and if applicable, your address or service location?"
   4b. ATTEMPT EMERGENCY TRANSFER:
       - Initiate transfer to on-call staff ({emergency_primary}).
       - If first contact unreachable, attempt {emergency_secondary}.
       - Say: "Please hold while I connect you with our on-call team."
   4c. EMERGENCY TRANSFER FAIL PROTOCOL:
       - Say: "I wasn't able to reach our on-call team directly, but I have your information and our team will call you back as soon as possible. {emergency_fallback_message}"
       - If safety at risk: "If you believe there is immediate danger, please call 911."
       - "We take emergencies very seriously and someone will be in touch with you shortly."

   IF NON-EMERGENCY:
   4d. COLLECT DETAILS:
       - "No problem. I'll make sure your message gets to our team. Can I get your name, callback number, and a brief description of what you need?"
   4e. PROMISE FOLLOW-UP:
       - "Our team will reach out to you during our next business day, {business_hours_days} starting at {business_hours_start} {timezone}. {non_emergency_callback_note}"
   4f. CONFIRM: "I've noted your request. Is there anything else I can help you with?"

5. CLOSE: "Thank you for calling {company_name}. {closing_message}"

---

## SERVICES
{company_name} provides: {services_list}

## COMPANY INFO
- Business Hours: {business_hours_days}, {business_hours_start} – {business_hours_end} {timezone}
- Office Address: {office_address}
- Main Line: {main_phone}

---

## STRICTLY PROHIBITED
- Do not invent information about services, pricing, technician availability, or scheduling commitments.
- Do not mention internal systems, software, or routing processes to the caller.
- Do not promise specific arrival times unless explicitly confirmed.
- If unsure, always default to: "I'll make sure our team follows up with you."
"""


def _format_days(days: list) -> str:
    if not days:
        return "business days"
    if len(days) == 7:
        return "every day"
    if days == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        return "Monday through Friday"
    if len(days) > 2:
        return f"{days[0]} through {days[-1]}"
    return " and ".join(days)


def _format_services(services: list) -> str:
    if not services:
        return "various trade services"
    return ", ".join(s.title() for s in services)


def _format_emergency_triggers(triggers: list) -> str:
    if not triggers:
        return "situations posing immediate safety or property risk"
    formatted = [f"  - {t.replace('_', ' ').title()}" for t in triggers[:8]]
    return "\n" + "\n".join(formatted)


def _get_main_phone(memo: dict) -> str:
    er = memo.get("emergency_routing_rules") or {}
    ne = memo.get("non_emergency_routing_rules") or {}
    vm = ne.get("voicemail_number")
    if vm:
        return vm
    ep = er.get("primary_phone")
    if ep:
        return ep
    return "our main office line"


def generate_spec(memo: dict) -> dict:
    """Generate a Retell Agent Draft Spec from an AccountMemo dict."""
    account_id = memo.get("account_id", "ACC-UNKNOWN")
    company_name = memo.get("company_name") or "the company"
    version = memo.get("version", "v1")
    now = datetime.now(timezone.utc).isoformat()

    agent_name = f"{company_name} Virtual Receptionist"

    bh = memo.get("business_hours") or {}
    bh_days = _format_days(bh.get("days") or [])
    bh_start = bh.get("start") or "opening time"
    bh_end = bh.get("end") or "closing time"
    tz = bh.get("timezone") or ""
    tz_short = tz.split("/")[-1].replace("_", " ") if tz else ""

    addr_obj = memo.get("office_address") or {}
    office_address = addr_obj.get("full") or addr_obj.get("street") or "our office"

    services = memo.get("services_supported") or []
    services_list = _format_services(services)

    emergencies = memo.get("emergency_definition") or []
    emergency_triggers_str = _format_emergency_triggers(emergencies)

    er = memo.get("emergency_routing_rules") or {}
    emergency_primary = er.get("primary_phone") or er.get("primary_contact") or "on-call staff"
    emergency_secondary = er.get("secondary_phone") or er.get("secondary_contact") or "backup on-call"
    emergency_fallback = er.get("fallback") or "Our team will call you back as quickly as possible."

    tr = memo.get("call_transfer_rules") or {}
    timeout_seconds = tr.get("timeout_seconds") or 45
    retries = tr.get("retries") or 1
    transfer_announcement = tr.get("transfer_announcement") or "Please hold while I connect you with our team."
    transfer_fail_msg = tr.get("what_to_say_if_transfer_fails") or (
        "I wasn't able to connect you directly, but I have your information and our team will call you back shortly."
    )

    ne = memo.get("non_emergency_routing_rules") or {}
    ne_callback = ne.get("callback_promise") or "during our next business day"
    main_phone = _get_main_phone(memo)

    closing_message = (
        "If this is an emergency, please don't hesitate to call back. "
        "We're here to help."
    )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        company_name=company_name,
        tone="professional and friendly",
        business_hours_days=bh_days,
        business_hours_start=bh_start,
        business_hours_end=bh_end,
        timezone=tz_short,
        transfer_announcement=transfer_announcement,
        timeout_seconds=timeout_seconds,
        transfer_fail_message=transfer_fail_msg,
        emergency_triggers=emergency_triggers_str,
        emergency_primary=emergency_primary,
        emergency_secondary=emergency_secondary,
        emergency_fallback_message=emergency_fallback,
        non_emergency_callback_note="Your reference will be noted.",
        services_list=services_list,
        office_address=office_address,
        main_phone=main_phone,
        closing_message=closing_message,
    )

    prompt_lower = system_prompt.lower()
    hygiene = {
        "has_office_hours_flow": "office hours flow" in prompt_lower,
        "has_after_hours_flow": "after-hours flow" in prompt_lower,
        "has_transfer_protocol": "transfer" in prompt_lower,
        "has_transfer_fail_protocol": "transfer fail" in prompt_lower,
        "mentions_tools_to_caller": any(
            phrase in prompt_lower for phrase in ["tool", "function call", "api", "webhook"]
        ),
        "collects_name_and_number": "name" in prompt_lower and "number" in prompt_lower,
        "has_anything_else_close": "anything else" in prompt_lower,
    }

    tools = [
        {
            "name": "transfer_call",
            "description": "INTERNAL: Routes the call to the specified phone number. Never announce as 'tool'.",
            "trigger": "When caller needs to be connected to staff or on-call technician"
        },
        {
            "name": "log_caller_info",
            "description": "INTERNAL: Records caller name, phone, and message to the task tracker.",
            "trigger": "When collecting caller contact info for callback"
        },
        {
            "name": "check_business_hours",
            "description": "INTERNAL: Determines if current time is within business hours.",
            "trigger": "At call start to determine which flow to use"
        },
    ]

    spec = {
        "agent_name": agent_name,
        "version": version,
        "account_id": account_id,
        "created_at": now,
        "updated_at": None,
        "voice_style": {
            "voice_id": "11labs-Adrian",
            "language": "en-US",
            "tone": "professional",
            "speaking_rate": 1.0
        },
        "system_prompt": system_prompt,
        "key_variables": {
            "timezone": tz or None,
            "business_hours_start": bh_start,
            "business_hours_end": bh_end,
            "business_hours_days": bh_days,
            "office_address": office_address if office_address != "our office" else None,
            "emergency_routing_primary": emergency_primary,
            "emergency_routing_secondary": emergency_secondary,
            "emergency_fallback": emergency_fallback,
            "company_name": company_name,
            "services_list": services_list,
        },
        "tool_invocation_placeholders": tools,
        "call_transfer_protocol": {
            "method": "warm_transfer",
            "announcement": transfer_announcement,
            "timeout_seconds": timeout_seconds,
            "retries": retries,
        },
        "transfer_fail_protocol": {
            "message_to_caller": transfer_fail_msg,
            "collect_info": True,
            "promise_callback": True,
            "escalation": emergency_fallback if emergencies else None,
        },
        "prompt_hygiene_checklist": hygiene,
        "retell_import_instructions": _build_import_instructions(agent_name),
    }

    if hygiene.get("mentions_tools_to_caller"):
        logger.warning(f"[{account_id}] PROMPT HYGIENE VIOLATION: system prompt mentions tools/functions!")
    if not hygiene.get("has_office_hours_flow"):
        logger.warning(f"[{account_id}] PROMPT HYGIENE WARNING: office hours flow not detected in prompt")
    if not hygiene.get("has_after_hours_flow"):
        logger.warning(f"[{account_id}] PROMPT HYGIENE WARNING: after-hours flow not detected in prompt")

    logger.info(f"Generated spec for {account_id} v{version}: hygiene={hygiene}")
    return spec


def _build_import_instructions(agent_name: str) -> str:
    return f"""
MANUAL RETELL UI IMPORT INSTRUCTIONS

1. Log in to your Retell account at https://app.retellai.com
2. Navigate to Agents → Create New Agent
3. Set Agent Name: "{agent_name}"
4. Under LLM / Prompt: paste the full contents of the "system_prompt" field
5. Under Voice: select preferred voice (suggested: 11labs-Adrian)
6. Under Variables: add each entry from "key_variables" as a custom variable
7. Under Call Transfer: configure using "call_transfer_protocol" settings
8. Under Tools / Functions: create internal tools from "tool_invocation_placeholders"
   (these are INTERNAL ONLY — never expose tool names to callers)
9. Verify the "prompt_hygiene_checklist" shows all True values before going live

Note: Retell programmatic agent creation requires a paid plan.
This spec file is the zero-cost alternative — manual copy/paste import.
""".strip()


if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python spec_generator.py <account_memo.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        memo = json.load(f)
    spec = generate_spec(memo)
    print(json.dumps(spec, indent=2))
