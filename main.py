from agent import CBTAgent

agent = CBTAgent()
print(f"=== CBT Session Started (ID: {agent.session_id}) ===")

# Initial assistant message
first_msg = agent.respond(None)
print(f"Agent: {first_msg}")
agent.chat_history.append({"role": "assistant", "content": first_msg})
agent.save_session()
step = 0
while agent.current_step <= 7:
    step += 1
    print(f"========== Step {agent.current_step} Round {step} =========")
    user_in = input("You: ")
    if user_in.lower() in ["exit", "quit"]:
        break
    agent.chat_history.append({"role": "user", "content": user_in})

    prev_step = agent.current_step
    step_completed = agent.extract_and_fill(user_in)
    if step_completed:
        print(f"✅ Step {agent.current_step} complete!")
        step = 0
        agent.current_step += 1

    assistant_msg = agent.respond(user_in, step_completed=step_completed, step_before=prev_step)
    print(f"Agent: {assistant_msg}")
    agent.chat_history.append({"role": "assistant", "content": assistant_msg})

    agent.turns.append({
        "step_before": prev_step,
        "step_after": agent.current_step,
        "user": user_in,
        "assistant": assistant_msg
    })
    agent.save_session()

    if agent.current_step == 7:
        # summary already generated in this turn
        break

print(f"\n=== Session Finished. Data saved in sessions/session_{agent.session_id}.json ===")
