import json
import requests
import re
import os
from datetime import datetime
from prompts import CBTPrompts

class CBTAgentTest:
    def __init__(self, step=1, initial_record=None, model="gemma2:9b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"
        self.current_step = step
        
        # 1. 术语统一：整个流程是一个 Session，每一轮是一次 Turn
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chat_history = []  # 记录所有 Turns
        
        self.thought_record = initial_record or {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "situation": "", 
            "emotion": "", 
            "intensity_before": 0, 
            "automatic_thought": "", 
            "evidence_for": [], 
            "evidence_against": [], 
            "distortions": [], 
            "balanced_thought": "", 
            "intensity_after": 0
        }
        
        self.REQUIRED_FIELDS = {
            1: ["situation", "emotion", "intensity_before", "automatic_thought"],
            2: ["evidence_for"],
            3: ["evidence_against"],
            4: ["distortions"],
            5: ["balanced_thought"],
            6: ["intensity_after"],
            7: [] 
        }

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

    def _field_ask_spec(self, field_name: str) -> str:
        specs = {
            "situation": "Ask what happened / what the specific situation was. One sentence is enough.",
            "emotion": "Ask for a feeling word (e.g., upset, anxious, sad).",
            "intensity_before": "Ask for a 0–100 rating of the emotion at its peak.",
            "automatic_thought": "Ask for the specific thought/image at the worst moment (the 'hot thought').",
            "evidence_for": "Ask for factual evidence supporting the thought (facts, not feelings).",
            "evidence_against": "Ask for factual evidence against the thought (facts that don't fit it).",
            "distortions": "Ask which cognitive distortion labels might apply (1–3 labels).",
            "balanced_thought": "Ask for a more balanced, realistic alternative thought (not overly positive).",
            "intensity_after": "Ask for a 0–100 rating of the original emotion now.",
        }
        return specs.get(field_name, f"Ask for: {field_name}")

    def _ask_with_llm(self, missing_fields):
        system_p = CBTPrompts.system()
        step_p = getattr(CBTPrompts, f"step{self.current_step}")()
        current_record_json = json.dumps(self.thought_record, indent=2, ensure_ascii=False)
        missing_specs = "\n".join([f"- {f}: {self._field_ask_spec(f)}" for f in missing_fields])

        prompt = f"""
{system_p}
---
CURRENT STEP: {self.current_step}
STEP RULES:
{step_p}
---
CURRENT RECORD STATE:
{current_record_json}
---
MISSING FIELDS (ask ONLY for these):
{missing_fields}

FIELD-SPECIFIC GUIDANCE:
{missing_specs}

TASK:
1. Write ONE warm, clear question to obtain the missing field(s).
2. Do NOT ask for anything already present in CURRENT RECORD STATE.
3. If both emotion and intensity_before are missing, ask them together in one question.
4. Otherwise, ask for ONLY ONE missing field at a time (choose the most important).
5. Output ONLY the question.
"""
        return self._call_llm(prompt, temperature=0.7)

    def _call_llm(self, prompt, temperature=0.7):
        payload = {"model": self.model, "prompt": prompt, "stream": False, "temperature": temperature}
        try:
            res = requests.post(self.url, json=payload)
            return res.json()["response"].strip()
        except Exception as e:
            return f"Error: {e}"

    def save_session(self):
        """每轮对话后保存：防止丢失，记录完整 Session"""
        # 确保 sessions 目录存在
        os.makedirs("sessions", exist_ok=True)
        
        session_data = {
            "session_id": self.session_id,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_step": self.current_step,
            "thought_record": self.thought_record,
            "chat_history": self.chat_history
        }
        file_path = f"sessions/session_{self.session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

    def ask_user(self):
        """根据当前表单状态提问"""
        if self.current_step == 7:
            system_p = CBTPrompts.system()
            step_p = getattr(CBTPrompts, f"step{self.current_step}")()
            current_record_json = json.dumps(self.thought_record, indent=2, ensure_ascii=False)
            prompt = f"{system_p}\n---\n{step_p}\n---\nFINAL RECORD:\n{current_record_json}\n\nTASK: Generate the final summary now."
            return self._call_llm(prompt, temperature=0.7)

        is_empty = (
            not self._is_field_filled("situation")
            and not self._is_field_filled("emotion")
            and not self._is_field_filled("automatic_thought")
        )
        if is_empty:
            system_p = CBTPrompts.system()
            step_p = getattr(CBTPrompts, f"step{self.current_step}")()
            current_record_json = json.dumps(self.thought_record, indent=2, ensure_ascii=False)
            prompt = f"""
{system_p}
---
CURRENT STEP: {self.current_step}
STEP RULES:
{step_p}
---
CURRENT RECORD STATE:
{current_record_json}

TASK:
Start the session as a warm CBT counselor. Ask one gentle, open-ended opening question.
Output ONLY the question.
"""
            return self._call_llm(prompt, temperature=0.7)

        missing = self.missing_fields_for_current_step()
        if not missing:
            return "Thanks—let's move to the next step."

        return self._ask_with_llm(missing)

    def extract_and_fill(self, user_input):
        """上下文感知的提取逻辑"""
        system_p = CBTPrompts.system()
        step_p = getattr(CBTPrompts, f"step{self.current_step}")()
        # 核心改进：引入上下文，解决 Yes/No 识别问题
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
3. If a field is already filled in CURRENT RECORD STATE, do NOT overwrite it.
4. If user confirms something (e.g. "Yes", "Correct"), use CONTEXT to infer what they are confirming.
5. Mapping rules:
   - "emotion": a feeling word (e.g. upset, sad, anxious). If the user says \"I'm upset\", extract emotion=\"upset\".
   - "intensity_before"/"intensity_after": a number 0-100. If user replies only \"55\", treat it as the missing intensity for the current step.
   - "distortions": MUST be names/labels of distortions, not questions.
   - "evidence_for"/"evidence_against": should be factual statements; output as a list when possible.
6. Output ONLY valid JSON. No markdown, no extra text.
"""
        raw_json = self._call_llm(prompt, temperature=0.1)
        try:
            match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            if match:
                json_str = re.sub(r',\s*\}', '}', match.group(0))
                data = json.loads(json_str)
                self.update_record(data)
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

    def update_record(self, data):
        for k, v in data.items():
            if not v: continue
            if k in self.thought_record:
                if isinstance(self.thought_record[k], list):
                    new_items = v if isinstance(v, list) else [v]
                    for item in new_items:
                        if item and item not in self.thought_record[k]:
                            self.thought_record[k].append(item)
                elif not self.thought_record[k] or self.thought_record[k] == 0:
                    self.thought_record[k] = v

if __name__ == "__main__":
    agent = CBTAgentTest(step=1)
    print(f"=== CBT Session Started (ID: {agent.session_id}) ===")
    
    while agent.current_step <= 7:
        # 1. Agent's Turn
        reply = agent.ask_user()
        print(f"Agent: {reply}")
        agent.chat_history.append({"role": "assistant", "content": reply})
        agent.save_session() # 及时保存
        
        if agent.current_step == 7: break 

        # 2. User's Turn
        user_in = input("You: ")
        if user_in.lower() in ["exit", "quit"]: break
        agent.chat_history.append({"role": "user", "content": user_in})
        
        # 3. Process Turn
        if agent.extract_and_fill(user_in):
            print(f"✅ Step {agent.current_step} complete!")
            agent.current_step += 1
        
        agent.save_session() # 及时保存

    print(f"\n=== Session Finished. Data saved in sessions/session_{agent.session_id}.json ===")
