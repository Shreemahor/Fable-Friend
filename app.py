import os
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated, List
from langgraph.graph import add_messages, StateGraph, END, START
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.types import Command, interrupt
import uuid

import gradio as gr
import time

from langchain_groq import ChatGroq
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.7)
llm2 = ChatGroq(model="llama-3.1-8b-instant", temperature=0.7)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a storyteller. You will guide the user through an interactive story where they make choices that affect the outcome of the adventure." \
    "Describe scenes vividly and present the user with clear choices at each step. Keep the story engaging and immersive."),
    ("human", "{text}")
])


class Story(TypedDict): 
    story_summary: str
    situation: Annotated[List[AIMessage], add_messages]
    your_action: Annotated[List[str], add_messages]
    theme: str


def storyteller(state: Story): 

    print("at storyteller node")

    summarize_prompt = PromptTemplate.from_template("Summarize/Paraphrase the following storyline into a concise and fully encompossing" \
    "paragraph: {situation}")
    output_parser = StrOutputParser()
    what_happened = summarize_prompt | llm2 | output_parser

    ai_messages = [m for m in state["situation"] if isinstance(m, AIMessage)]
    recent = ai_messages[-5:]
    recent_text = "\n\n".join(m.content for m in recent)
    summmarizer_input = f"Most importantly a summary: {state['story_summary']}\n\nAlso if necessary Recent scenes:\n{recent_text}"
    state["story_summary"] = what_happened.invoke(summmarizer_input)

    your_action = state["your_action"] if "your_action" in state else ["No Action yet"]

    prompt = f"""
        You are a storyteller. You will guide the user through an interactive story where they make choices that affect the outcome of the adventure.
        After the user makes a choice, continue the story in a paragraph by describing the next situation based on their action, keeping it engaging and immersive
        Theme: {state['theme']},
        Current situation: {state['story_summary']},
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


# Everything after this is gradio and app management integration


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


def initialize_state(char_name, genre) -> dict:
    print("DEBUG on_begin_story received genre =", genre)
    char_name = (char_name or "Unknown Hero").strip()
    genre = (genre or "fantasy").strip()
    print("genre is ", genre)
    genres_map = {
        "fantasy": "High-Fantasy Quest (epic adventure, magic, ancient ruins, heroic tone)",
        "scifi": "Cyberpunk Heist (neon megacity, megacorps, hackers, chrome augmentations, tense noir energy)",
        "grimdark": "Grimdark Survival (brutal stakes, scarcity, moral compromise, bleak atmosphere)",
        "noir": "Noir Detective (rainy streets, shadows, corruption, cynical voice, mystery-driven)",
        "space_opera": "Cosmic Space Opera (galactic scale, factions, starships, wonder, high drama)",
    }
    theme = genres_map.get(genre, genre)
    # opening = (
    #     f"The user is {char_name}, the genre is {genre}. Open with an immersive scene ending with what do you do next?"
    # )
    print("theme is ", theme)

    # this was generated via a prompt to expand themes into detailed story prompts
    theme_expander_prompt = PromptTemplate.from_template("""Task: Act as a Prompt Architect. Your sole purpose is to generate an exceptionally detailed, ready-to-use prompt for a specialized Storywriter LLM. You will be given a core theme or concept.

    Instructions for Your Output:
    Craft a final prompt that is a complete creative brief. It must be self-contained, leaving no room for ambiguity. The goal is to give the final Storywriter LLM all the necessary ingredients and constraints to produce a compelling and thematically rich story opening that achieves immersion and propels the reader into action.

    CRITICAL IMMERSION & ACTION REQUIREMENT:
    The primary goal of the final story introduction is to make the reader feel immersed in the world and situation as if they are present, and to end with a compelling, immediate situation that forces the protagonist (and by extension, the reader) to make a decisive choice or take urgent action. This ending should not be a cliffhanger for the overall plot, but a pressing moment within the opening scene that demands a response.

    Your generated prompt must include the following sections, clearly labeled:

    Core Theme & Central Conflict: State the provided theme. Define the core dramatic tension or central question that will drive the narrative.

    Genre & Tone: Specify the genre (e.g., noir, epic fantasy, cosmic horror, slice-of-life). Describe the precise tone (e.g., cynical and melancholic, awe-inspiring and grand, claustrophobic and dread-filled, warm and nostalgic).

    Setting & Atmosphere:

    Era & Location: Time period and physical place.

    Sensory Details: Mention 2-3 key sensory elements (sights, sounds, smells, weather, textures) crucial for immersion.

    Social/Political Context: Briefly note any relevant societal rules, power structures, or technological levels.

    Protagonist Details:

    Identity & Role: Name, occupation, archetype.

    Defining Trait & Flaw: A key strength and a compelling weakness or internal conflict.

    Immediate Mindset: What is their emotional state as the scene begins? (e.g., weary, anxious, determined, bored).

    Opening Scene Directive:

    In Medias Res: Start the story in the middle of a meaningful, active moment. Provide the specific situation the protagonist is physically engaged in.

    Immediate Goal: What is the protagonist trying to achieve in this very first beat of the scene?

    Inciting Interaction: Describe the character, event, or discovery that interrupts the initial goal and escalates the situation.

    MANDATORY: Immersive Action-Forcing Conclusion: The story introduction MUST end at a moment of high tension where the protagonist is faced with a clear, urgent choice or direct threat that demands an immediate physical or verbal response. Provide the specific dilemma or threat that will end the intro. Examples: A weapon is drawn on them, they are presented with damning evidence and must decide to hide it or reveal it, they are given a 10-second ultimatum, they must choose between two immediate escape routes, a secret is revealed that forces them to confront someone directly.

    Narrative Style & Point of View: Specify the POV (e.g., second-person "You," first-person present tense, or close third-person present tense are strongly preferred for immersion). Include style notes that emphasize sensory language and immediate perception.

    Constraints & Requirements:

    Length: "Write a 350-450 word story introduction."

    Focus: "Do not summarize or 'set the scene' abstractly. Begin in action. Immerse the reader through immediate sensory details (what is seen, heard, felt, smelled) and the protagonist's visceral reactions."

    Ending Directive: "The final paragraph must culminate in the action-forcing situation described above. End with the protagonist in that moment of crisis, decision, or confrontation—do not resolve it."

    Avoid: "Avoid exposition dumps, backstory paragraphs, or internal monologues that are not triggered by the immediate action. Reveal character and world solely through present action, dialogue, and perception."

    Format: Output ONLY the final, fleshed-out prompt for the Storywriter LLM. Do not add any commentary, introductions, or notes before or after it.

    Now, using the following core theme, generate the detailed prompt as instructed:

    Core Theme: {genre}""")
    prompt_to_writer = theme_expander_prompt | llm | StrOutputParser()
    writer_brief = prompt_to_writer.invoke({"genre": theme})
    written_intro = llm.invoke([SystemMessage(content=writer_brief)]).content

    return {
        "story_summary": written_intro,
        "situation": [],
        "your_action": [],
        "theme": theme
    }


def on_begin_story_checked(char_name, genre, history, thread_id):
    print("DEBUG on_begin_story received genre =", genre)
    if genre is None:
        raise ValueError("Please select a story path/genre before beginning.")
    return on_begin_story(char_name, genre, history, thread_id)

def on_begin_story(char_name, genre, history, thread_id):
    # standard stuff
    thread_id = str(uuid.uuid4())
    starter = initialize_state(char_name, genre)
    opening = run_until_interrupt(app, starter, config={"configurable": {"thread_id": thread_id}})
    history = (history or []) + [{"role": "assistant", "content": opening}]

    # return for gradio
    return (
        history,
        thread_id,
        char_name,
        genre,
        True,
        time.time() + 3.5
    )


from gradio_frontend import build_demo, CSS, HEAD
demo = build_demo(on_user_message=on_user_message,on_begin_story=on_begin_story,on_begin_story_checked=on_begin_story_checked)
if __name__ == "__main__":
    demo.queue().launch(theme=gr.themes.Soft(
                            primary_hue="purple",
                            secondary_hue="yellow",
                            neutral_hue="slate",
                            ),
                        css=CSS,
                        head=HEAD,
                        allowed_paths=[os.path.abspath("frontend")]
                        )
    