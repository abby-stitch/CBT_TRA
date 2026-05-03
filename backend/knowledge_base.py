class DistortionKnowledge:
    SOURCE_NOTES = """
Official source basis:
- Beck Institute CBT Worksheet Packet, 2020 Edition:
  https://learn.beckinstitute.org/cms/delivery/media/MCPNPP5FFGJVDJ7C74SMXCMM5CWY
- Beck Institute Coping with Depression booklet:
  https://cares.beckinstitute.org/wp-content/uploads/sites/2/2021/06/Coping-with-Depression.pdf
- Judith S. Beck, Cognitive Behavior Therapy: Basics and Beyond, 3rd edition.

Use these snippets as CBT worksheet guidance only. They are not diagnostic criteria.
"""

    @staticmethod
    def get_step_knowledge(step: int) -> str:
        sections = {
            1: """
Source-grounded Step 1 Knowledge: Situation, emotion, and automatic thought
Source basis: Beck Institute CBT Worksheet Packet sections "Identifying Thoughts", "Questions to Identify Automatic Thoughts", and "Thought Records".
- The cognitive model links the interpretation of a situation, expressed in automatic thoughts or images, with emotion, behavior, and physiological response.
- When mood worsens or unhelpful behavior appears, the worksheet asks the person to identify what was going through their mind.
- A situation can be external, such as something that happened, or internal, such as an intense emotion, painful sensation, image, daydream, flashback, or stream of thoughts.
- Thought records ask the person to notice the worst part of the experience and then record the thoughts or images from that moment.
- The first part of the thought record depends on distinguishing situation, automatic thoughts, and emotions.
""",
            2: """
Source-grounded Step 2 Knowledge: Evidence that supports the automatic thought
Source basis: Beck Institute Thought Record and Testing Your Thoughts worksheets.
- The worksheet asks what evidence suggests the automatic thought is true.
- Evidence belongs in the adaptive-response process because thoughts may be fully true, not true, or partly true.
- Keep this step focused on observations, events, or reasons that make the automatic thought seem believable.
- Do not ask for counter-evidence yet; that is a separate worksheet question.
""",
            3: """
Source-grounded Step 3 Knowledge: Evidence that does not support the automatic thought
Source basis: Beck Institute Thought Record and Testing Your Thoughts worksheets.
- The worksheet asks what evidence suggests the automatic thought is not true or not completely true.
- This step evaluates the thought rather than simply reassuring the user.
- Useful worksheet-based angles include looking for another explanation, considering what is most likely, and considering what the person would tell a friend in the same situation.
- Do not force positivity; keep the focus on grounded evidence and plausible alternatives.
""",
            5: """
Source-grounded Step 5 Knowledge: Adaptive response / alternative response
Source basis: Beck Institute Thought Record, Testing Your Thoughts worksheet, and Coping with Depression Socratic questioning section.
- The worksheet uses questions to help compose an adaptive or alternative response to the automatic thought.
- Relevant questions include evidence for and against the thought, another way of looking at the situation, coping if the worst happens, the best and most realistic outcomes, effects of believing or changing the thought, what the person would tell a friend, and what would be good to do now.
- The response should evaluate the automatic thought in a more reasonable and balanced way.
- The response should be connected to the original automatic thought, not a generic affirmation or unrelated advice.
""",
        }
        section = sections.get(step, "").strip()
        if not section:
            return ""
        return f"{DistortionKnowledge.SOURCE_NOTES.strip()}\n\n{section}"

    @staticmethod
    def get_full_distortions():
        return """
Cognitive Distortions Knowledge Base

Source basis:
- Primary label set and examples follow the Beck Institute CBT Worksheet Packet, 2020 edition.
- Definitions follow the Beck Institute Coping with Depression booklet, "Thinking Errors" section.
- Both sources are Beck Institute materials adapted from or authored by Judith S. Beck and Beck Institute clinicians.

General selection principles:
- Cognitive distortions are not mutually exclusive; more than one label may fit the same automatic thought.
- Prefer the user's explicit choice when they name or confirm a label.
- Classify the specific automatic thought or image, not the user's personality.
- Choose 1-3 labels only; more than one distortion may apply.
- Present labels as tentative possibilities unless the user confirms them.
- Do not diagnose. These labels describe thought patterns in one moment.

1. All-or-nothing thinking
Definition: Interpreting a situation in extreme either/or terms instead of seeing degrees or middle ground.
Source-grounded example: "If this is not a complete success, then it is a failure."

2. Catastrophizing (fortune telling)
Definition: Making a negative future prediction while overlooking other realistic possible outcomes.
Source-grounded example: "If this goes badly, I will not be able to cope or function."

3. Disqualifying or discounting the positive
Definition: Treating positive actions, feedback, or qualities as if they do not really count.
Source-grounded example: "The good result does not mean much; I probably just got lucky."

4. Emotional reasoning
Definition: Assuming a belief is true mainly because it feels true emotionally.
Source-grounded example: "I feel incompetent, so I conclude that I really am incompetent."

5. Labeling
Definition: Applying a broad negative label to yourself or someone else instead of describing the specific behavior or situation.
Source-grounded example: "I made a mistake, so I am a loser."

6. Magnification/minimization
Definition: Making negative details seem larger or more important, and/or making positive details seem smaller or less important.
Source-grounded example: "One mediocre result proves I am inadequate, while good results do not prove much."

7. Mental filter (selective abstraction)
Definition: Focusing heavily on one negative detail while missing the broader picture.
Source-grounded example: "One critical comment means the whole evaluation was bad, even though there was positive feedback too."

8. Mind reading
Definition: Assuming you know what another person is thinking without enough evidence and without considering other possibilities.
Source-grounded example: "They probably think I do not know what I am doing."

9. Overgeneralization
Definition: Drawing a broad negative conclusion from one event or a small amount of evidence.
Source-grounded example: "Because I felt uncomfortable once, I cannot handle this kind of situation."

10. Personalization
Definition: Assuming another person's negative or ambiguous behavior is caused by you, while overlooking other plausible explanations.
Source-grounded example: "They did not greet me, so I must have upset them."

11. “Should” and “must” statements
Definition: Using fixed rules about how you or others should, must, or have to behave.
Source-grounded example: "I should never make mistakes."

12. Tunnel vision
Definition: Seeing only the negative side of a situation and leaving out neutral or positive aspects.
Source-grounded example: "Everything about this situation is bad."
"""
