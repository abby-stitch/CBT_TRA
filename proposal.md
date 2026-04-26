# CBT Thought Record Agent
## Group member
 Liang Shiyao, 3036656312

## 1. Project Objective
Cognitive Behavioral Therapy (CBT) includes structured tools such as **Thought Records**, which help individuals identify cognitive distortions in automatic thoughts and restructure them into more balanced perspectives.

However, self-practice of CBT often faces practical difficulties:
- Lack of structured step-by-step guidance
- Difficulty maintaining consistent records
- Emotional interruption during self-reflection

This project aims to build a **task-oriented LLM-based CBT Thought Record Agent** that:
- Guides users through a structured thought-record workflow
- Identifies potential cognitive distortions using RAG
- Uses Socratic questioning to encourage self-reflection
- Stores structured records locally
- Generates progress reports based on historical data 

The system is designed as a **self-monitoring support tool**, not a medical or therapeutic system.

## 2. Motivation and Challenges
### 2.1 Motivation
When experiencing emotional distress, users may not have immediate access to professional help. CBT thought-record practice is a validated self-help method, but applying it independently requires discipline, structured recording, and conceptual understanding.

An interactive LLM agent can reduce cognitive load and provide structured guidance.
### 2.2 Challenges

#### (1) Scope Control

CBT includes many techniques. Implementing full CBT therapy is unrealistic and unsafe.  
Therefore, this project focuses only on **Thought Record restructuring**.

#### (2) Structured Interaction Design

The agent must:
- Follow a fixed multi-step workflow
- Maintain state across turns
- Avoid turning into a generic chatbot

#### (3) Safety Boundaries

The system must:
- Detect extreme or high-risk language
- Provide emergency suggestions
- Avoid diagnosis or treatment claims

## 3. System Architecture

The system follows a task-oriented Agent pipeline:
``` text
User Input
    ↓
State Manager
    ↓
LLM + Prompt Constraint
    ↓
RAG Knowledge Retrieval
    ↓
Socratic Question Generation
    ↓
Structured Record Storage
    ↓
Report Generator
```

### 3.1 Workflow Example

Example input:

> “I can't write my resume. Everyone else can. I’m terrible and I’ll never find a job.”

Agent workflow:

1. Identify emotional tone
2. Detect possible cognitive distortion:
    - Overgeneralization
    - All-or-nothing thinking
3. Respond with:
    - Empathetic acknowledgment
    - Guided reflection questions
4. Ask for:
    - Evidence for
    - Evidence against
5. Guide alternative thought generation
6. Ask user to re-rate emotion
7. Save structured record    

### 3.2 Core Components

#### (1) Prompt-Constrained LLM
- Defines tone (supportive, non-judgmental)
- Restricts medical claims
- Enforces step-by-step CBT workflow
#### (2) RAG Module

Knowledge base includes:
- Cognitive distortion definitions
- CBT thought-record templates
- Socratic questioning examples

Datasets:
- Hugging Face CBT-Bench
- C2D2 Dataset
RAG ensures the agent's reasoning remains aligned with CBT principles.

#### (3) Local Record Storage

Each session stores：
- Situation
- Automatic thought
- Emotion rating
- Distortion type
- Evidence for / against
- Alternative thought
- Re-rated emotion
Stored as structured JSON.
#### (4) Report Generator
Generates:
- Chronological summary
- Distribution of distortion types
- Emotion change trends
- Encouraging feedback

## 4. Evaluation Plan
Instead of only feature completion, evaluation will include three layers:
### 4.1 Functional Evaluation
- Can the agent complete all steps of the thought record?
- Can it store structured records?
- Can it generate reports?
### 4.2 Cognitive Distortion Detection Accuracy
- Use sample inputs from CBT-Bench or C2D2
- Compare detected distortion with reference label
### 4.3 Safety Evaluation
- Test extreme/high-risk prompts
- Verify system triggers safety response

## 5. Project Positioning
This project is:
- Not a therapy system
- Not a diagnostic tool
- A structured CBT worksheet assistant powered by LLM
  
Technically, it demonstrates:
- Prompt engineering
- RAG
- State-driven multi-step Agent design
- Structured memory storage
- Safety constraint design