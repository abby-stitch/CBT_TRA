import json
import requests
from datetime import datetime
from prompts import CBTPrompts

class CBTAgent:
    def __init__(self, model="gemma2:9b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

        self.current_step = 1
        self.max_step = 7
        self.is_active = True
        self.chat_history = []

        # 最终要求的 JSON 格式
        self.thought_record = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "situation": "",
            "emotions": [],  # 存储 {"emotion": "", "intensity_before": 0, "intensity_after": 0}
            "automatic_thought": "",
            "evidence_for": [],
            "evidence_against": [],
            "identified_distortions": [],
            "alternative_thought": ""
        }

    def _call_llm(self, prompt, temperature=0.7):
        """通用 LLM 调用接口"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature
        }
        try:
            res = requests.post(self.url, json=payload)
            return res.json()["response"].strip()
        except Exception as e:
            print(f"LLM Error: {e}")
            return ""

    def internal_extract(self, user_input):
        """功能 1：静默提取信息（低 Temperature 保证稳定性）"""
        system_prompt = CBTPrompts.system()
        step_prompt = getattr(CBTPrompts, f"step{self.current_step}")()
        chat_history_str = json.dumps(self.chat_history[-5:], ensure_ascii=False)
        current_record_str = json.dumps(self.thought_record, indent=2, ensure_ascii=False)

        extract_instruction = f"""
{system_prompt}
---
CURRENT STEP RULES:
{step_prompt}
---
CURRENT THOUGHT RECORD STATE (ALREADY FILLED):
{current_record_str}
---
CONVERSATION HISTORY:
{chat_history_str}
USER INPUT: {user_input}

TASK:
1. Identify if the user's latest input provides new information for ANY field in the record, especially the current step.
2. Cross-check with the CURRENT THOUGHT RECORD STATE. Do NOT overwrite existing non-empty fields with empty values.
3. Judge if the CURRENT step's required information is now complete (considering both previous state and new input).
4. Output ONLY a valid JSON object:
{{
  "complete": true/false,
  "extracted_data": {{ "field_name": "new_value" }}
}}
"""
        raw_json = self._call_llm(extract_instruction, temperature=0.1)
        try:
            start = raw_json.find("{")
            end = raw_json.rfind("}") + 1
            return json.loads(raw_json[start:end])
        except:
            return {"complete": False, "extracted_data": {}}

    def generate_response(self, user_input, is_complete):
        """功能 2：生成有同理心的回复（正常 Temperature 保证自然度）"""
        system_prompt = CBTPrompts.system()
        step_prompt = getattr(CBTPrompts, f"step{self.current_step}")()
        chat_history_str = json.dumps(self.chat_history[-5:], ensure_ascii=False)
        current_record_str = json.dumps(self.thought_record, indent=2, ensure_ascii=False)

        status_msg = "The user has provided all information for this step. Transition to the next step naturally." if is_complete else "Some information is missing for the CURRENT STEP. Ask for it warmly and DIRECTLY."
        
        chat_instruction = f"""
{system_prompt}
---
CURRENT STEP TASK:
{step_prompt}
---
CURRENT THOUGHT RECORD STATE (ALREADY FILLED):
{current_record_str}
---
STATUS: {status_msg}
CONVERSATION HISTORY: {chat_history_str}
USER INPUT: {user_input}

STRICT GUIDELINES FOR REPLY:
1. NEVER use vague words like "more", "tell me more", or "anything else". Be specific about what is missing.
2. Do NOT ask for information that is already present in the CURRENT THOUGHT RECORD STATE.
3. If info is complete: Briefly validate and transition to the next task's core question.
4. If info is missing: Empathize with the user's latest input, then ask DIRECTLY for the specific missing field (e.g., if intensity is missing, ask "On a scale of 0-100, how strong was that feeling?").
5. Keep the persona of a warm, professional CBT counselor.
"""
        return self._call_llm(chat_instruction, temperature=0.7)

    def generate_final_summary(self):
        """功能 4：生成结语并总结"""
        system_prompt = CBTPrompts.system()
        summary_instruction = f"""
{system_prompt}
---
FINAL THOUGHT RECORD:
{json.dumps(self.thought_record, indent=2, ensure_ascii=False)}

TASK:
1. Provide a warm, supportive closing statement.
2. Summarize what the user has achieved today (e.g., identifying distortions, creating a balanced thought).
3. Encourage them to keep practicing.
"""
        return self._call_llm(summary_instruction, temperature=0.7)

    def update_record(self, data):
        """将提取的数据填入 thought_record，确保不覆盖已有内容"""
        if not data:
            return

        for key, value in data.items():
            # 跳过空值，防止覆盖
            if value is None or value == "" or value == []:
                continue

            # 1. 处理普通字段
            if key in self.thought_record and not isinstance(self.thought_record[key], list):
                # 只有当原值为空时才写入，或者如果新值不同且非空则覆盖（根据需求决定是否覆盖）
                self.thought_record[key] = value
            
            # 2. 处理列表字段
            elif key in ["evidence_for", "evidence_against", "identified_distortions"]:
                if isinstance(value, list):
                    for item in value:
                        if item and item not in self.thought_record[key]:
                            self.thought_record[key].append(item)
                elif value and value not in self.thought_record[key]:
                    self.thought_record[key].append(value)
            
            # 3. 特殊处理 emotions
            elif key in ["emotion", "intensity_before", "intensity_after"]:
                self._handle_emotion_update(key, value)

    def _handle_emotion_update(self, key, value):
        """专门处理 emotions 列表的更新逻辑"""
        if not self.thought_record["emotions"]:
            self.thought_record["emotions"].append({"emotion": "", "intensity_before": 0, "intensity_after": 0})
        
        target = self.thought_record["emotions"][0] # 暂时处理主情绪
        if key == "emotion":
            target["emotion"] = value
        elif key == "intensity_before":
            try:
                target["intensity_before"] = int(value)
            except: pass
        elif key == "intensity_after":
            try:
                target["intensity_after"] = int(value)
            except: pass

    def run_cycle(self, user_input):
        """主控循环：执行单轮对话并管理状态跃迁"""
        if not self.is_active:
            return "Session has ended."

        # 1. 记录用户输入
        self.chat_history.append({"role": "user", "content": user_input})
        
        # 2. 内部提取与判断
        extraction = self.internal_extract(user_input)
        is_complete = extraction.get("complete", False)
        
        # 3. 更新后台数据
        self.update_record(extraction.get("extracted_data", {}))
        
        # 4. 状态跃迁与回复生成
        if is_complete:
            if self.current_step < self.max_step:
                # 步骤前进，生成带“承上启下”的回复
                reply = self.generate_response(user_input, is_complete=True)
                self.current_step += 1
            else:
                # 所有步骤完成，生成总结
                reply = self.generate_final_summary()
                self.is_active = False
        else:
            # 信息不全，生成追问回复
            reply = self.generate_response(user_input, is_complete=False)
            
        # 5. 记录 AI 回复
        self.chat_history.append({"role": "assistant", "content": reply})
        
        # 6. 持久化保存
        self.save_data()
        
        # DEBUG 日志
        print(f"\n[Step {self.current_step}] Complete: {is_complete}")
        print(f"Extracted: {extraction.get('extracted_data')}")
        
        return reply

    def save_data(self):
        """保存完整对话记录和结构化表单"""
        with open("chat_history.json", "w", encoding="utf-8") as f:
            json.dump(self.chat_history, f, indent=2, ensure_ascii=False)
        with open("thought_record.json", "w", encoding="utf-8") as f:
            json.dump(self.thought_record, f, indent=2, ensure_ascii=False)
