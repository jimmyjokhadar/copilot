from agents.intentAgent import IntentAgent

class IntentService:
    def run(self, **kwargs):
        agent = IntentAgent(kwargs["user_ctx"])
        return agent.invoke(kwargs)
