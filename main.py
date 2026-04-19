from agent import CBTAgent

agent = CBTAgent()
print("✅ CBT Thought Record Agent | Logic & Conversation Decoupled\n")

# 初始引导：由于 run_cycle 需要用户输入，我们先手动获取第一步的引导词
# 或者我们可以修改 run_cycle 支持空输入，但这里简单处理：
first_msg = agent.generate_response("Hello, I want to start a thought record.", is_complete=False)
agent.chat_history.append({"role": "assistant", "content": first_msg})
print(f"Agent: {first_msg}\n")

while agent.is_active:
    user = input("You: ")
    if user.lower() in ["exit", "quit", "stop"]:
        break
    
    reply = agent.run_cycle(user)
    print(f"Agent: {reply}\n")

print("\n🎉 CBT WORKFLOW COMPLETED!")
print("Files saved: chat_history.json, thought_record.json")