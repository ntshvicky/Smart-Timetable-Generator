from __future__ import annotations

import json
import re

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ConstraintParseLog
from app.schemas.timetable import ConstraintPayload, ParseInstructionResponse


class GeminiConstraintService:
    allowed_rule_types = {
        "teacher_unavailable",
        "subject_first_half",
        "subject_not_after_lunch",
        "avoid_consecutive_subject",
        "fixed_subject_slot",
        "teacher_max_periods",
        "class_blocked_slot",
    }

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    async def parse(self, school_id: int, text: str) -> ParseInstructionResponse:
        if self.settings.gemini_api_key:
            constraints, provider = await self._parse_with_gemini(text), "gemini"
        else:
            constraints, provider = self._fallback_parse(text), "fallback"
        valid = [self._normalize_constraint(item) for item in constraints]
        self.db.add(ConstraintParseLog(school_id=school_id, input_text=text, parsed_json=json.dumps([c.model_dump() for c in valid]), provider=provider))
        self.db.commit()
        return ParseInstructionResponse(constraints=valid, provider=provider)

    async def _parse_with_gemini(self, text: str) -> list[dict]:
        prompt = f"""
Convert school timetable instructions into JSON constraints.
Return only a JSON array. Schema:
rule_type: one of teacher_unavailable, subject_first_half, subject_not_after_lunch, avoid_consecutive_subject, fixed_subject_slot, teacher_max_periods, class_blocked_slot
target_type: class|teacher|subject|school
target_values: array of strings
day_scope: array of day names
period_scope: array of integers
priority: hard|soft
parsed_description: short text
confidence_score: number 0 to 1

Instruction: {text}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent?key={self.settings.gemini_api_key}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
            response.raise_for_status()
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, list) else [parsed]

    def _fallback_parse(self, text: str) -> list[dict]:
        lower = text.lower()
        constraints: list[dict] = []
        days = [d for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] if d.lower() in lower]
        periods = [int(num) for num in re.findall(r"(?:period|periods|p)\s*(\d+)", lower)]
        classes = re.findall(r"class(?:es)?\s*([0-9A-Za-z,\s]+)", text, re.IGNORECASE)
        class_values = []
        if classes:
            class_values = [part.strip() for part in re.split(r",|\band\b", classes[0]) if part.strip()]
        if "first half" in lower:
            subject = self._extract_subject(text)
            constraints.append({"rule_type": "subject_first_half", "target_type": "subject", "target_values": [subject] + class_values, "day_scope": days, "period_scope": [], "priority": "soft", "parsed_description": text, "confidence_score": 0.72})
        if "after lunch" in lower and ("do not" in lower or "not" in lower):
            constraints.append({"rule_type": "subject_not_after_lunch", "target_type": "subject", "target_values": [self._extract_subject(text)] + class_values, "day_scope": days, "period_scope": [], "priority": "soft", "parsed_description": text, "confidence_score": 0.7})
        if "unavailable" in lower:
            teacher_match = re.search(r"teacher\s+([A-Za-z-]+)|([A-Z][a-z]+)\s+is unavailable", text)
            teacher = next((g for g in teacher_match.groups() if g), "unknown") if teacher_match else "unknown"
            constraints.append({"rule_type": "teacher_unavailable", "target_type": "teacher", "target_values": [teacher], "day_scope": days, "period_scope": periods, "priority": "hard", "parsed_description": text, "confidence_score": 0.75})
        if "consecutive" in lower:
            constraints.append({"rule_type": "avoid_consecutive_subject", "target_type": "subject", "target_values": [self._extract_subject(text)] + class_values, "day_scope": days, "period_scope": [], "priority": "soft", "parsed_description": text, "confidence_score": 0.68})
        if "last period" in lower or ("period" in lower and days):
            constraints.append({"rule_type": "fixed_subject_slot", "target_type": "subject", "target_values": [self._extract_subject(text)] + class_values, "day_scope": days, "period_scope": periods, "priority": "hard", "parsed_description": text, "confidence_score": 0.66})
        return constraints or [{"rule_type": "class_blocked_slot", "target_type": "school", "target_values": [], "day_scope": days, "period_scope": periods, "priority": "soft", "parsed_description": text, "confidence_score": 0.35}]

    def _extract_subject(self, text: str) -> str:
        known = ["Math", "Science", "English", "Hindi", "PT", "Computer", "SST"]
        for subject in known:
            if re.search(rf"\b{subject}\b", text, re.IGNORECASE):
                return subject
        return text.split()[0] if text.split() else "unknown"

    def _normalize_constraint(self, item: dict) -> ConstraintPayload:
        payload = ConstraintPayload(**item)
        if payload.rule_type not in self.allowed_rule_types:
            payload.rule_type = "class_blocked_slot"
        if payload.priority not in {"hard", "soft"}:
            payload.priority = "soft"
        payload.confidence_score = max(0.0, min(1.0, payload.confidence_score))
        return payload
