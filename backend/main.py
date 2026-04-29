from backend.agent import CBTAgent

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
    prev_step = agent.current_step
    result = agent.process_user_turn(user_in)
    if result["step_completed"]:
        print(f"✅ Step {prev_step} complete!")
        step = 0

    print(f"Agent: {result['message']}")

    if result["session_completed"]:
        break

print(f"\n=== Session Finished. Data saved in sessions/session_{agent.session_id}.json ===")
