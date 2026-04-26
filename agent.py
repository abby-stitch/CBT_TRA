import json
import requests
import re
import os
from datetime import datetime
from prompts import CBTPrompts
from knowledge_base import DistortionKnowledge

class CBTAgent:
    def __init__(self, step=1, initial_record=None, model="gemma2:9b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"
        self.current_step = step
        
        # Terminology: the whole workflow is one Session, each exchange is one Turn
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chat_history = []  # message-level history: [{role, content}]
        self.turns = []         # turn-level history: [{step, assistant_ask, user, assistant_reply}]
        
        self.thought_record = initial_record or {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "situation": "", 
            "emotion": "", 
            "intensity_before": 0, 
            "automatic_thought": "", 
            "evidence_for": [], 
            "evidence_against": [], 
            "distortions": [], 
            "predicted_distortion": [],
            "balanced_thought": "", 
            "intensity_after": 0,
            "summary": ""
        }
        
        self.REQUIRED_FIELDS = {
            1: ["situation", "emotion", "intensity_before", "automatic_thought"],
            2: ["evidence_for"],
            3: ["evidence_against"],
            4: ["distortions"],
            5: ["balanced_thought"],
            6: ["intensity_after"],
            7: ["summary"]
        }
        self.session_status = "in_progress"
        self.safety_reason = None
        self.safety_state = "normal"
        self.last_safety_warning_turn = 0
        self.SAFETY_FALLBACK_PATTERNS = [
            (r"\b(kill myself|suicide|suicidal|end my life|want to die|don't want to live|do not want to live|hurt myself|self[- ]harm|overdose|stop living|better off without me|not wake up)\b", "self_harm_risk"),
            (r"(不想活|活不下去|想死|自杀|伤害自己|不如死了)", "self_harm_risk"),
        ]

    def _debug_log(self, tag: str, **data):
        payload = " | ".join([f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in data.items()])
        print(f"[DEBUG][{tag}] {payload}")

    def _is_field_filled(self, field_name: str) -> bool:
        val = self.thought_record.get(field_name)
        if isinstance(val, list):
            return len(val) > 0
        if isinstance(val, (int, float)):
            return val != 0
        return bool(str(val).strip())

    def missing_fields_for_current_step(self):
        fields = self.REQUIRED_FIELDS.get(self.current_step, [])
        return [f for f in fields if not self._is_field_filled(f)]

    def ensure_predicted_distortions(self) -> list[str]:
        """
        Step 4 helper:
        If predicted_distortion is empty, ask the LLM to propose 1–3 likely distortions using the Step 4 KB,
        store them into thought_record["predicted_distortion"], then return the list.
        """
        if self.current_step != 4:
            return []
        if self.thought_record.get("predicted_distortion"):
            return self.thought_record["predicted_distortion"]

        system_p = CBTPrompts.system()
        step4_p = getattr(CBTPrompts, "step4")()
        record_json = json.dumps(self.thought_record, indent=2, ensure_ascii=False)

        prompt = f"""
{system_p}
---
STEP 4 RULES (use the Knowledge Base inside):
{step4_p}
---
CURRENT RECORD STATE:
{record_json}

TASK:
1. Based on the user's situation, automatic_thought, and evidence, suggest 1–3 likely cognitive distortions.
2. Use ONLY labels that appear in the Knowledge Base.
3. Output ONLY valid JSON:
{{"predicted_distortion": ["distortion1", "distortion2"]}}
"""
        raw = self._call_llm(prompt, temperature=0.1)
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return []
            json_str = re.sub(r",\s*\}", "}", match.group(0))
            data = json.loads(json_str)
            preds = data.get("predicted_distortion") or []
            if isinstance(preds, str):
                preds = [preds]
            preds = [p.strip() for p in preds if isinstance(p, str) and p.strip()]
            if preds:
                self.thought_record["predicted_distortion"] = preds[:3]
            return self.thought_record.get("predicted_distortion", [])
        except Exception:
            return []

    # def _field_ask_spec(self, field_name: str) -> str:
    #     specs = {
    #         "situation": "Ask what happened / what the specific situation was. One sentence is enough.",
    #         "emotion": "Ask for a feeling word (e.g., upset, anxious, sad).",
    #         "intensity_before": "Ask for a 0–100 rating of the emotion at its peak.",
    #         "automatic_thought": "Ask for the specific thought/image at the worst moment (the 'hot thought').",
    #         "evidence_for": "Ask for factual evidence supporting the thought (facts, not feelings).",
    #         "evidence_against": "Ask for factual evidence against the thought (facts that don't fit it).",
    #         "distortions": "First propose 1–3 likely distortion labels, then ask the user which ones fit (use tentative language).",
    #         "balanced_thought": "Ask for a more balanced, realistic alternative thought (not overly positive).",
    #         "intensity_after": "Ask for a 0–100 rating of the original emotion now.",
    #     }
    #     return specs.get(field_name, f"Ask for: {field_name}")

    # def _ask_with_llm(self, missing_fields):
    #     system_p = CBTPrompts.system()
    #     step_p = getattr(CBTPrompts, f"step{self.current_step}")()
    #     current_record_json = json.dumps(self.thought_record, indent=2, ensure_ascii=False)
    #     missing_specs = "\n".join([f"- {f}: {self._field_ask_spec(f)}" for f in missing_fields])
    #     recent_turns = "\n".join([f"{m['role']}: {m['content']}" for m in self.chat_history[-4:]])
    #
    #     prompt = f"""
    # {system_p}
    # ---
    # CURRENT STEP: {self.current_step}
    # STEP RULES:
    # {step_p}
    # ---
    # CURRENT RECORD STATE:
    # {current_record_json}
    # ---
    # RECENT TURNS:
    # {recent_turns}
    # ---
    # MISSING FIELDS (ask ONLY for these):
    # {missing_fields}
    #
    # FIELD-SPECIFIC GUIDANCE:
    # {missing_specs}
    #
    # TASK:
    # 1. Write ONE warm, clear question to obtain the missing field(s).
    # 2. Do NOT ask for anything already present in CURRENT RECORD STATE.
    # 3. If both emotion and intensity_before are missing, ask them together in one question.
    # 4. Otherwise, ask for ONLY ONE missing field at a time (choose the most important).
    # 5. Output ONLY the question (no explanation, no JSON, no markdown).
    # """
    #     return self._call_llm(prompt, temperature=0.7)

    def _call_llm(self, prompt, temperature=0.7):
        payload = {"model": self.model, "prompt": prompt, "stream": False, "temperature": temperature}
        try:
            res = requests.post(self.url, json=payload)
            return res.json()["response"].strip()
        except Exception as e:
            return f"Error: {e}"

    def _semantic_safety_check(self, user_input: str) -> tuple[str, str | None]:
        recent_turns = "\n".join([f"{m['role']}: {m['content']}" for m in self.chat_history[-4:]])
        safety_prompt = CBTPrompts.safety_check()
        prompt = f"""
{safety_prompt}

RECENT TURNS:
{recent_turns}
USER INPUT:
{user_input}
"""
        raw = self._call_llm(prompt, temperature=0.1)
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(re.sub(r",\s*\}", "}", match.group(0)))
                risk = data.get("risk_level")
                reason = data.get("reason")
                if risk in {"normal", "supportive_warning", "acute_warning"}:
                    self._debug_log("SAFETY_CHECK", source="llm", risk=risk, reason=reason, user_input=user_input)
                    return risk, reason
        except Exception:
            pass

        text = user_input.lower()
        for pattern, _ in self.SAFETY_FALLBACK_PATTERNS:
            if re.search(pattern, text):
                self._debug_log("SAFETY_CHECK", source="fallback", risk="acute_warning", reason="fallback pattern matched acute-risk phrase", user_input=user_input)
                return "acute_warning", "fallback pattern matched acute-risk phrase"
        self._debug_log("SAFETY_CHECK", source="default", risk="normal", reason=None, user_input=user_input)
        return "normal", None

    def _should_include_safety_note(self, risk_level: str) -> bool:
        if risk_level == "acute_warning":
            return True
        if risk_level != "supportive_warning":
            return False
        if self.last_safety_warning_turn == 0:
            return True
        return (len(self.turns) - self.last_safety_warning_turn) >= 2

    def _reset_safety_memory_if_normal(self, risk_level: str):
        if risk_level == "normal":
            self.safety_state = "normal"
            self.safety_reason = None
            self.last_safety_warning_turn = 0

    def _support_guidance_line(self, risk_level: str) -> str:
        if risk_level == "acute_warning":
            return "If you might be unsafe right now, please reach out to a trusted person, local emergency help, or professional support as soon as you can."
        if risk_level == "supportive_warning":
            return "If these thoughts start to feel unsafe or overwhelming, please consider reaching out to someone you trust or to professional support."
        return ""

    def _ensure_support_guidance(self, message: str, risk_level: str, include_safety_note: bool) -> str:
        if not include_safety_note:
            return message
        guidance = self._support_guidance_line(risk_level)
        if not guidance:
            return message
        lowered = message.lower()
        if any(token in lowered for token in ["professional support", "someone you trust", "trusted person", "emergency help"]):
            return message
        return f"{message}\n\n{guidance}"

    def save_session(self):
        """Persist session data after each turn to avoid data loss."""
        # Ensure sessions directory exists
        os.makedirs("sessions", exist_ok=True)
        
        session_data = {
            "session_id": self.session_id,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_step": self.current_step,
            "session_status": self.session_status,
            "safety_state": self.safety_state,
            "safety_reason": self.safety_reason,
            "last_safety_warning_turn": self.last_safety_warning_turn,
            "thought_record": self.thought_record,
            "chat_history": self.chat_history,
            "turns": self.turns
        }
        file_path = f"sessions/session_{self.session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        self._debug_log("SESSION_SAVED", session_id=self.session_id, file_path=file_path, current_step=self.current_step, session_status=self.session_status, safety_state=self.safety_state)

    def respond(self, user_input: str | None = None, step_completed: bool = False, step_before: int | None = None, risk_level: str = "normal", safety_reason: str | None = None, include_safety_note: bool = False) -> str:
        """
        Single response function:
        - Explain when needed, then ask naturally.
        - Ask for missing fields when needed.
        - Transition naturally after step completion.
        - Step 7 outputs a summary.
        """
        system_p = CBTPrompts.system()
        step_p = getattr(CBTPrompts, f"step{self.current_step}")()
        current_record_json = json.dumps(self.thought_record, indent=2, ensure_ascii=False)
        recent_turns = "\n".join([f"{m['role']}: {m['content']}" for m in self.chat_history[-6:]])
        missing = self.missing_fields_for_current_step()
        step_before_val = step_before if step_before is not None else self.current_step
        step_after_val = self.current_step
        predicted = self.ensure_predicted_distortions() if self.current_step == 4 else []

        # Final summary step
        if self.current_step == 7:
            prompt = f"""
{system_p}
---
CURRENT STEP: 7
STEP RULES:
{step_p}
---
FINAL RECORD:
{current_record_json}

TASK:
Generate the final supportive summary now.
Output only the counselor message.
"""
            summary = self._call_llm(prompt, temperature=0.7)
            self.thought_record["summary"] = summary
            self.session_status = "completed"
            return summary

        # Opening message
        if user_input is None:
            return "Hello, I'm here to support you. What's on your mind today?"

        transition_block = ""
        if step_completed and step_after_val != step_before_val:
            transition_block = f"""
---
TRANSITION MODE:
The user's latest message completed Step {step_before_val}. You are now in Step {step_after_val}.
Do NOT continue discussing Step {step_before_val}. Briefly acknowledge and ask the core question for Step {step_after_val}.
"""

        predicted_block = ""
        step4_block = ""
        safety_block = ""
        if risk_level != "normal":
            safety_block = f"""
---
SAFETY CONTEXT:
- risk_level: {risk_level}
- reason: {safety_reason}
- include_safety_note_this_turn: {include_safety_note}
- If include_safety_note_this_turn is true, include 1-2 warm, natural sentences acknowledging pain.
- If include_safety_note_this_turn is true, you should also explicitly encourage the user to seek trusted or professional support if they may be unsafe.
- Do NOT use fixed template wording for the whole reply. Vary the phrasing naturally based on the user's message.
- If include_safety_note_this_turn is false, do NOT repeat the previous safety reminder.
- If risk_level is acute_warning, output only the supportive safety-focused reply for this turn and do not continue the CBT task.
"""
        if self.current_step == 4:
            predicted_block = f"""
---
PREDICTED DISTORTIONS (Step 4 suggestions, if any):
{predicted}
"""
            step4_block = """
3. Step 4 special behavior:
   - Use PREDICTED DISTORTIONS as your initial suggestion (1–3 items).
   - Present them as tentative (might/could), with 1 short sentence each.
   - Ask the user whether any of them fit their thought.
"""

        prompt = f"""
{system_p}
---
CURRENT STEP: {self.current_step}
STEP RULES:
{step_p}
{transition_block}
CURRENT RECORD STATE:
{current_record_json}
---
RECENT TURNS:
{recent_turns}
---
LATEST USER MESSAGE:
{user_input}
---
MISSING FIELDS FOR CURRENT STEP:
{missing}
{predicted_block}
{safety_block}

TASK:
1. Produce ONE natural counselor response for this turn.
2. If user asks for clarification/explanation, answer it briefly first (especially in Step 4, use the knowledge base and explain at most 3 relevant distortions, not the full list), then continue naturally.
{step4_block}3. Then do one of:
   - if there are missing fields: ask for the most important missing item;
   - if no missing fields: give a short transition and ask the next-step question.
4. Keep tone empathetic and specific. Avoid vague repetition like "tell me more" unless you specify what exactly is missing.
5. Output only the counselor message.
"""
        return self._call_llm(prompt, temperature=0.7)

    def process_user_turn(self, user_input: str) -> dict:
        self.chat_history.append({"role": "user", "content": user_input})
        prev_step = self.current_step
        self._debug_log("TURN_START", session_id=self.session_id, step_before=prev_step, user_input=user_input)
        risk, reason = self._semantic_safety_check(user_input)
        self.safety_state = risk
        self.safety_reason = reason
        self._reset_safety_memory_if_normal(risk)
        include_safety_note = self._should_include_safety_note(self.safety_state)
        self._debug_log("TURN_SAFETY", risk=self.safety_state, reason=self.safety_reason, include_safety_note=include_safety_note, last_safety_warning_turn=self.last_safety_warning_turn)

        step_completed = False
        if risk != "acute_warning":
            step_completed = self.extract_and_fill(user_input)
            if step_completed:
                self.current_step += 1

        assistant_msg = self.respond(
            user_input,
            step_completed=step_completed,
            step_before=prev_step,
            risk_level=risk,
            safety_reason=reason,
            include_safety_note=include_safety_note,
        )
        assistant_msg = self._ensure_support_guidance(assistant_msg, risk, include_safety_note)
        if self.safety_state != "normal" and include_safety_note:
            self.last_safety_warning_turn = len(self.turns) + 1

        self._debug_log("TURN_RESULT", step_before=prev_step, step_after=self.current_step, step_completed=step_completed, session_status=self.session_status, safety_state=self.safety_state, assistant_msg=assistant_msg)
        self.chat_history.append({"role": "assistant", "content": assistant_msg})
        self.turns.append({
            "step_before": prev_step,
            "step_after": self.current_step,
            "user": user_input,
            "assistant": assistant_msg,
            "risk_state": self.safety_state,
            "risk_reason": self.safety_reason,
            "include_safety_note": include_safety_note,
        })
        self.save_session()
        return {"message": assistant_msg, "step_completed": step_completed, "session_completed": self.session_status != "in_progress"}

    def extract_and_fill(self, user_input):
        """Context-aware extraction logic."""
        system_p = CBTPrompts.system()
        step_p = getattr(CBTPrompts, f"step{self.current_step}")()
        # Include context to handle short confirmations (Yes/No) more accurately
        context = "\n".join([f"{m['role']}: {m['content']}" for m in self.chat_history[-2:]])
        current_record_json = json.dumps(self.thought_record, indent=2, ensure_ascii=False)
        required_now = self.REQUIRED_FIELDS.get(self.current_step, [])
        
        prompt = f"""
{system_p}
---
CURRENT STEP RULES: {step_p}
CONTEXT (Recent Conversation):
{context}
CURRENT RECORD STATE:
{current_record_json}
---
NEW USER INPUT: "{user_input}"

TASK:
1. Extract info for ANY CBT field in the thought record.
2. PRIORITY: Since we are in Step {self.current_step}, focus on extracting these fields if present: {required_now}.
3. Default: do NOT overwrite fields that are already filled in CURRENT RECORD STATE.
   Exception: if the user's message is clearly correcting previous info (e.g., "Correction:", "Actually", "Not X, it was Y"), you MAY overwrite.
   If overwriting, you MUST include: "overwrite_fields": ["field1", "field2"] listing exactly which fields are being corrected.
4. If user confirms something (e.g. "Yes", "Correct"), use CONTEXT to infer what they are confirming.
5. Mapping rules:
   - "emotion": store ONE primary feeling word.
     Accept common emotion words and close variants (e.g., upset, anxious, nervous, sad, angry, ashamed, frustrated, disappointed, hurt, scared, overwhelmed).
     Minor spelling mistakes are allowed if the intended meaning is clear (e.g., "anxiou" -> "anxious", "disapointed" -> "disappointed").
     If the user gives multiple emotions, choose the main emotion most central to the distress in this turn.
     If the user describes an emotional state indirectly but the meaning is clear, infer the closest feeling word.
     Do NOT treat self-judgment words as emotions (e.g., terrible, worthless, failure, stupid).
     If the user explicitly says "I feel X" where X is a self-judgment, map it to "automatic_thought" instead.
     Only leave "emotion" out if the intended feeling is truly unclear.
   - Self-judgment / interpretation / prediction belongs to "automatic_thought" (e.g., terrible, worthless, failure, "I'll never find a job", "Everyone else can").
   - "intensity_before"/"intensity_after": a number 0-100. If user replies only \"55\", treat it as the missing intensity for the current step.
   - "distortions": MUST be names/labels of distortions, not questions.
   - "predicted_distortion": assistant-suggested distortion labels (store as a list).
   - "evidence_for"/"evidence_against": should be factual statements; output as a list when possible.
6. Step 4 special extraction:
   - If CURRENT STEP is 4 and the user asks you to decide / asks what distortions they have, you may output "predicted_distortion" (1–3 labels) using the Knowledge Base.
7. Output ONLY valid JSON. No markdown, no extra text.
"""
        raw_json = self._call_llm(prompt, temperature=0.1)
        try:
            match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            if match:
                json_str = re.sub(r',\s*\}', '}', match.group(0))
                data = json.loads(json_str)
                overwrite_fields = data.pop("overwrite_fields", None) or data.pop("_overwrite_fields", None) or []
                data.pop("edit_intent", None)

                allow_overwrite_fields: set[str] = set()
                if isinstance(overwrite_fields, str):
                    overwrite_fields = [overwrite_fields]
                if isinstance(overwrite_fields, list):
                    allow_overwrite_fields = {
                        str(f).strip()
                        for f in overwrite_fields
                        if isinstance(f, (str, int, float)) and str(f).strip() in self.thought_record and str(f).strip() != "date"
                    }

                self.update_record(data, allow_overwrite_fields=allow_overwrite_fields)
        except Exception as e:
            print(f"[ERROR] Extraction failed: {e}\nRaw: {raw_json}")
        
        is_complete = self.is_current_step_complete()
        print(f"\n[DEBUG] Step: {self.current_step} | Hard-Check Complete: {is_complete}")
        print(f"[DEBUG] Record: {json.dumps(self.thought_record, indent=2, ensure_ascii=False)}\n")
        return is_complete

    def is_current_step_complete(self):
        fields = self.REQUIRED_FIELDS.get(self.current_step, [])
        for f in fields:
            val = self.thought_record.get(f)
            if isinstance(val, list) and not val: return False
            if isinstance(val, (int, float)) and val == 0: return False
            if isinstance(val, str) and not val.strip(): return False
        return True

    def _distortion_label_set(self) -> set[str]:
        text = DistortionKnowledge.get_full_distortions()
        labels: set[str] = set()
        for line in text.splitlines():
            m = re.match(r"^\s*\d+\.\s*(.+?)\s*$", line)
            if m:
                labels.add(m.group(1).strip())
        return labels

    def _normalize_list_str(self, value) -> list[str]:
        items = value if isinstance(value, list) else [value]
        out: list[str] = []
        for item in items:
            if item is None:
                continue
            s = str(item).strip()
            if not s:
                continue
            parts = [p.strip() for p in re.split(r"[;\n]+", s) if p.strip()]
            out.extend(parts)

        dedup: list[str] = []
        seen: set[str] = set()
        for x in out:
            if x not in seen:
                dedup.append(x)
                seen.add(x)
        return dedup

    def _normalize_field(self, field: str, value):
        if value is None:
            return None

        if field in {"intensity_before", "intensity_after"}:
            if isinstance(value, (int, float)):
                n = int(value)
            else:
                m = re.search(r"-?\d+", str(value))
                if not m:
                    return None
                n = int(m.group(0))
            return max(0, min(100, n))

        if field == "emotion":
            s = str(value).strip()
            if not s:
                return None
            s = re.sub(r"\s+", " ", s)
            if " " in s:
                s = s.split(" ", 1)[0]
            return s

        if field in {"situation", "automatic_thought", "balanced_thought", "summary"}:
            s = str(value).strip()
            return s if s else None

        if field in {"evidence_for", "evidence_against"}:
            items = self._normalize_list_str(value)
            return items if items else None

        if field in {"distortions", "predicted_distortion"}:
            items = self._normalize_list_str(value)
            labels = self._distortion_label_set()
            filtered = [x for x in items if x in labels]
            return filtered if filtered else None

        return None

    def update_record(self, data: dict, allow_overwrite_fields: set[str] | None = None):
        allow = allow_overwrite_fields or set()
        for k, v in data.items():
            if k not in self.thought_record:
                continue

            normalized = self._normalize_field(k, v)
            if normalized is None:
                continue

            current = self.thought_record.get(k)
            if isinstance(current, list):
                if k in allow:
                    self.thought_record[k] = normalized if isinstance(normalized, list) else self._normalize_list_str(normalized)
                    continue

                new_items = normalized if isinstance(normalized, list) else self._normalize_list_str(normalized)
                for item in new_items:
                    if item and item not in current:
                        current.append(item)
                continue

            if k in allow:
                self.thought_record[k] = normalized
                continue

            if not current or current == 0:
                self.thought_record[k] = normalized

# if __name__ == "__main__":
#     agent = CBTAgent(step=1)
#     print(f"=== CBT Session Started (ID: {agent.session_id}) ===")
#
#     first_msg = agent.respond(None)
#     print(f"Agent: {first_msg}")
#     agent.chat_history.append({"role": "assistant", "content": first_msg})
#     agent.save_session()
#     step = 0
#     while agent.current_step <= 7:
#         step += 1
#         print(f"========== Step {agent.current_step} Round {step} =========")
#         user_in = input("You: ")
#         if user_in.lower() in ["exit", "quit"]:
#             break
#         agent.chat_history.append({"role": "user", "content": user_in})
#
#         prev_step = agent.current_step
#         step_completed = agent.extract_and_fill(user_in)
#         if step_completed:
#             print(f"✅ Step {agent.current_step} complete!")
#             step = 0
#             agent.current_step += 1
#
#         assistant_msg = agent.respond(user_in, step_completed=step_completed, step_before=prev_step)
#         print(f"Agent: {assistant_msg}")
#         agent.chat_history.append({"role": "assistant", "content": assistant_msg})
#
#         agent.turns.append({
#             "step_before": prev_step,
#             "step_after": agent.current_step,
#             "user": user_in,
#             "assistant": assistant_msg,
#             "risk_state": getattr(agent, "safety_state", "normal"),
#             "risk_reason": getattr(agent, "safety_reason", None),
#             "include_safety_note": False,
#         })
#         agent.save_session()
#
#         if agent.current_step == 7:
#             break
#
#     print(f"\n=== Session Finished. Data saved in sessions/session_{agent.session_id}.json ===")
