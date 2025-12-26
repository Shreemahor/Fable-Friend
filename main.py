import os
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated, List
from langgraph.graph import add_messages, StateGraph, END, START
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command, interrupt
import uuid

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
llm = ChatOpenAI(model="allenai/olmo-3.1-32b-think:free",
                api_key=openrouter_api_key,
                base_url="https://openrouter.ai/api/v1"
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a fantasy game dungeon master. You will guide the user through an interactive story where they make choices that affect the outcome of the adventure." \
    "Describe scenes vividly and present the user with clear choices at each step. Keep the story engaging and immersive."),
    ("human", "{text}")
])
chain = prompt | llm

# initial_situation = llm.invoke("You are a fantasy storyteller. Create an interesting and engaging opening situation for a new story." \
# "It should force the user to make a choice in the start of their adventure.").content
# print(initial_situation)


class Story(TypedDict): 
    story_summary: str
    situation: Annotated[List[str], add_messages]
    your_action: Annotated[List[str], add_messages]


def storyteller(state: Story): 

    print("at storyteller node")
    situation = state["story_summary"]
    your_action = state["your_action"] if "your_action" in state else ["No Action yet"]

    prompt = f"""
        You are a fantasy dugeon master. You will guide the user through an interactive story where they make choices that affect the outcome of the adventure.
        After the user makes a choice, continue the story in a paragraph by describing the next situation based on their action, keeping it engaging and immersive
        Current situation: {situation},
        The user's last action: {your_action[-1] if your_action else "No action yet"}
    """

    response = llm.invoke([
        SystemMessage(content=prompt)
    ])
    continuation = response.content

    print(f"[storyteller_node] Generated situation:\n{continuation}\n")
    return {
       "situation": [AIMessage(content=continuation)],
       "your_action": your_action   
    }


def user(state: Story): 
    
    situation = state["situation"]
    print("\n [user_node] awaiting user action...")

    your_action_interrupt = interrupt(
        {
            "situation": situation, 
            "message": "What do you do next in the story?"
        }
    )

    print(f"[user_node] Received user action: {your_action_interrupt}")

    if your_action_interrupt.lower() in ["done", "bye", "quit"]:
        return Command(update={"your_action": state["your_action"] + ["Story done"]}, goto="end")

    return Command(update={"your_action": state["your_action"] + [your_action_interrupt]}, goto="storyteller")

def end(state: Story):
    print("\n\n\nThe end of your adventure!")


graph = StateGraph(Story)

graph.add_node("storyteller", storyteller)
graph.add_node("user", user)
graph.add_node("end", end)

graph.set_entry_point("storyteller")

graph.add_edge(START, "storyteller")
graph.add_edge("storyteller", "user")

graph.set_finish_point("end")

memory = MemorySaver()
app = graph.compile(checkpointer=memory)
print(app.get_graph().draw_ascii())


config = {"configurable": {
    "thread_id": uuid.uuid4()
}}
initial_scene = "There are two paths ahead of you in a dark forest: one leading to a spooky castle, the other to a serene lake."
initial_state = {
    "story_summary": initial_scene,
    "situation": [],
    "your_action": []
}


if __name__ == "__main__":
    for chunk in app.stream(initial_state, config=config):
        for node_id, value in chunk.items():
        #  If we reach an interrupt, continuously ask for human feedback
            if node_id == "__interrupt__":
                while True: 
                    what_do_you_do = input("You: ")

                    app.invoke(Command(resume=what_do_you_do), config=config)

                    if what_do_you_do.lower() in ["done", "bye", "quit"]:
                        break

# if __name__ == "__main__": 
#     while True: 
#         user_input = input("You: ")
#         if(user_input in ["exit", "end", "quit", "bye"]):
#             break
#         else: 
#             result = app.invoke({
#                 "messages": [HumanMessage(content=user_input)]
#             }, config=config)

#             print("Fable Friend: " + result["messages"][-1].content)
