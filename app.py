import os
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated, List
from langgraph.graph import add_messages, StateGraph, END, START
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command, interrupt
import uuid

import gradio as gr

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


config = {"configurable": {
    "thread_id": uuid.uuid4()
}}
initial_scene = "There are two paths ahead of you in a dark forest: one leading to a spooky castle, the other to a serene lake."
initial_state = {
    "story_summary": initial_scene,
    "situation": [],
    "your_action": []
}


def run_until_interrupt(app, starter, config):
    latest_message = "Nothing for now"

    for chunk in app.stream(starter, config=config):
        if "__interrupt__" in chunk:
            break

        for node_id, value in chunk.items():
            if isinstance(value, dict) and value.get("situation"):
                latest_message = getattr(value["situation"][-1],
                                          "content", str(value["situation"][-1]))
                
    return latest_message


def on_app_start():
    history = []
    thread_id = str(uuid.uuid4())

    opening = run_until_interrupt(app, initial_state,
                                  config={"configurable": {"thread_id": thread_id}})
    history.append({"role": "assistant", "content": opening})

    return history, thread_id


def on_user_message(user_message, history, thread_id):
    msg = (user_message or "").strip()
    if not msg:
        return "", history, thread_id

    if (not thread_id) or (msg.lower() == "start"):
        thread_id = str(uuid.uuid4())
        opening = run_until_interrupt(
            app, initial_state, config={"configurable": {"thread_id": thread_id}}
        )
        history = (history or []) + [{"role": "assistant", "content": opening}]
        return "", history, thread_id

    next_scene = run_until_interrupt(
        app,
        Command(resume=msg),
        config={"configurable": {"thread_id": thread_id}}
    )

    history = (history or []) + [{"role": "user", "content": msg},
                                 {"role": "assistant", "content": next_scene}]
    return "", history, thread_id



with gr.Blocks() as demo:
    thread_id_state = gr.State("")
    chat = gr.Chatbot()
    box = gr.Textbox(label="Type 'start' to begin")
    box.submit(on_user_message, inputs=[box, chat, thread_id_state],
               outputs=[box, chat, thread_id_state])

if __name__ == "__main__":
    demo.queue().launch()
