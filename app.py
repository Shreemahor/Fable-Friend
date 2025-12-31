import os
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated, List, Dict, Any
import json
from operator import add as list_add
from langgraph.graph import add_messages, StateGraph, END, START
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.types import Command, interrupt
import uuid

# Miscallenous variables and setup

import gradio as gr
import time
from file_of_prompts import (
    INTEMEDIARY_PROMPT,  # No longer in use but kept for reference
    INTRO_PROMPT_TEMPLATE,
    STORYTELLER_PROMPT_TEMPLATE,
    ADJUDICATION_PROMPT_TEMPLATE,
)
CONTINUE_KEY = "__CONTINUE__"
REWIND_KEY = "__REWIND__"
MENU_KEY = "__MENU__"
THREAD_META: Dict[str, Dict[str, Any]] = {}
# Marker used for one-turn grace period after retrying from GAME OVER.
# This is intentionally stripped from what the storyteller sees.
GRACE_PERIOD_INVISIBLE_TELLER = "grace_period:"

from langchain_groq import ChatGroq
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.7)
llm2 = ChatGroq(model="llama-3.1-8b-instant", temperature=0.7)

# Allow longer intro + milestone scenes.
try:
    llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.7, max_tokens=2500)
except TypeError:
    pass
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a storyteller guiding an interactive adventure. Keep responses immersive and avoid numbered/bulleted choice menus unless explicitly requested."),
    ("human", "{text}")
])

# creates unique thread id
def _make_thread_id():
    return str(uuid.uuid4())


def _replay_thread(*, starter: dict, inputs: List[str]) -> tuple[list, str]:
    """Rebuild a thread by replaying inputs from the same starter into a new thread_id."""
    new_thread_id = _make_thread_id()
    cfg = {"configurable": {"thread_id": new_thread_id}}

    history: list[dict] = []
    opening = run_until_interrupt(app, starter, config=cfg)
    history.append({"role": "assistant", "content": opening})

    for msg in inputs:
        next_scene = run_until_interrupt(app, Command(resume=msg), config=cfg)
        history.extend(
            [
                {"role": "user", "content": "(Continue the story)" if msg == CONTINUE_KEY else msg},
                {"role": "assistant", "content": next_scene},
            ]
        )

    return history, new_thread_id


def _safe_parse_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                parsed = json.loads(snippet)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


class Story(TypedDict): 
    intro_text: str
    story_summary: str
    situation: Annotated[List[AIMessage], add_messages]
    your_action: Annotated[List[str], list_add]
    theme: str
    char_name: str

    world: Dict[str, Any]
    inventory: List[str]
    turn_count: int
    tension: int
    named_entities: List[str]

    last_action_raw: str
    last_action: str
    progress: int


def storyteller(state: Story): 
    print("at storyteller node")

    # On the very first step of a new adventure, emit the pre-generated long intro
    # so the user actually sees it. No new state variables required.
    if not (state.get("situation") or []):
        intro = (state.get("intro_text") or "").strip()
        if intro:
            turn_count = int(state.get("turn_count") or 0)
            return {
                "situation": [AIMessage(content=intro)],
                "turn_count": turn_count + 1,
            }
    ai_messages = [m for m in state["situation"] if isinstance(m, AIMessage)]

    if ai_messages:
        summarize_prompt = PromptTemplate.from_template(
            "Summarize/Paraphrase the following storyline into a concise but complete paragraph.\n\n{storyline}"
        )
        output_parser = StrOutputParser()
        what_happened = summarize_prompt | llm2 | output_parser

        recent = ai_messages[-5:]
        recent_text = "\n\n".join(m.content for m in recent)
        summarizer_input = (
            f"Foundational intro (do not rewrite, but keep continuity):\n{state.get('intro_text','')}\n\n"
            f"Current running summary:\n{state['story_summary']}\n\n"
            f"Recent scenes to incorporate:\n{recent_text}"
        )
        state["story_summary"] = what_happened.invoke({"storyline": summarizer_input})

    char_name = (state["char_name"] or "Unknown Hero").strip()

    last_action = (state.get("last_action") or "").strip()
    last_action_raw = (state.get("last_action_raw") or "").strip()
    if last_action_raw.startswith(GRACE_PERIOD_INVISIBLE_TELLER):
        last_action_raw = last_action_raw[len(GRACE_PERIOD_INVISIBLE_TELLER):].lstrip()
    is_continue = (last_action == CONTINUE_KEY)
    progress = int(state.get("progress")) or 0
    is_milestone = (progress >= 100)
    length_rule = "12-18 sentences" if is_milestone else ("2-3 sentences" if is_continue else "5-6 sentences")

    phase = "early" if progress < 34 else ("mid" if progress < 67 else ("late" if progress < 100 else "milestone"))

    named_entities = state.get("named_entities") or []
    existing_names = ", ".join(named_entities) if named_entities else "(none yet)"
    turn_count = int(state.get("turn_count")) or 0
    # every 3 turns (but milestones always end with a hook)
    should_ask_question = True if is_milestone else ((turn_count % 3) == 0)
    # every other turn (but milestones may introduce a major new thread)
    allow_new_proper_noun = True if is_milestone else ((turn_count % 2) == 0)

    prompt = STORYTELLER_PROMPT_TEMPLATE.format(
        length_rule=length_rule,
        char_name=char_name,
        theme=state["theme"],
        phase=phase,
        should_ask_question=should_ask_question,
        allow_new_proper_noun=allow_new_proper_noun,
        existing_names=existing_names,
        intro_text=state.get("intro_text", ""),
        story_summary=state["story_summary"],
        last_action=last_action if last_action else "(starting the adventure)",
        last_action_raw=last_action_raw if last_action_raw else "(none)",
    )

    continuation = llm.invoke([SystemMessage(content=prompt)]).content

    if is_milestone:
        print("[storyteller_node] Milestone scene generated. Resetting progress.")
        return {
            "situation": [AIMessage(content=continuation)],
            "turn_count": turn_count + 1,
            "progress": 0,
        }

    print(f"[storyteller_node] Generated situation:\n{continuation}\n")
    return {
       "situation": [AIMessage(content=continuation)],
       "turn_count": turn_count + 1,
    }


def judger_improver(state: Story):

    raw_action = (state.get("last_action_raw") or "(no raw action)")
    grace_turn = False
    if isinstance(raw_action, str) and raw_action.startswith(GRACE_PERIOD_INVISIBLE_TELLER):
        grace_turn = True
        raw_action = raw_action[len(GRACE_PERIOD_INVISIBLE_TELLER):]
    raw_action = str(raw_action).strip()

    # If user said nothing, it is a continue
    if not raw_action:
        raw_action = CONTINUE_KEY

    tension = int(state.get("tension") or 3)
    progress = int(state.get("progress") or 0)
    turn_count = int(state.get("turn_count") or 0)
    allow_new_proper_noun = ((turn_count % 2) == 0)
    theme = state.get("theme") or "fantasy"
    char_name = (state.get("char_name") or "Unknown Hero").strip()

    adjudication_prompt = ADJUDICATION_PROMPT_TEMPLATE.format(
        char_name=char_name,
        theme=theme,
        tension=tension,
        progress=progress,
        turn_count=turn_count,
        allow_new_proper_noun=allow_new_proper_noun,
        story_summary=state.get("story_summary", ""),
        raw_action=raw_action,
    )

    raw = llm2.invoke([SystemMessage(content=adjudication_prompt)]).content
    obj = _safe_parse_json_object(raw)

    verdict = str(obj.get("verdict") or "ok").strip().lower()
    resolved_action = str(obj.get("resolved_action") or raw_action).strip()
    consequence = str(obj.get("consequence") or "").strip()
    new_name = str(obj.get("new_name") or "").strip()
    tension_change = int(obj.get("tension_change") or obj.get("tension_delta") or 0)
    progress_change = int(obj.get("progress_change") or obj.get("progress_delta") or 0)

    # One-turn grace after rewinding from a GAME OVER: avoid instant re-death.
    if grace_turn and verdict == "game_over":
        verdict = "redirect"
        if not consequence:
            consequence = "You avoid the worst at the last instant, but suffer a brutal setback instead."
        if progress_change < 1:
            progress_change = 1

    # Clamp and apply.
    if tension_change < -2:
        tension_change = -2
    if tension_change > 3:
        tension_change = 3

    if progress_change < 0:
        progress_change = 0
    if progress_change > 20:
        progress_change = 20

    # Continuation chains should still move progress meaningfully.
    if raw_action == CONTINUE_KEY and progress_change < 4:
        progress_change = 4

    new_tension = max(0, min(10, tension + tension_change))
    new_progress = max(0, min(100, progress + progress_change))

    named_entities = list(state.get("named_entities") or [])
    if not allow_new_proper_noun:
        new_name = ""
    if new_name and (new_name not in named_entities) and (len(named_entities) < 12):
        named_entities.append(new_name)

    # Ensure Continue uses a stable token so storyteller can pace correctly.
    if resolved_action.upper() == "CONTINUE" or resolved_action == CONTINUE_KEY:
        resolved_action = CONTINUE_KEY

    # Build a small consequence blurb that the storyteller must incorporate.
    consequence_blurb = ("" if not consequence else f"Immediate consequence: {consequence}")

    if verdict == "game_over":
        game_over_text = (
            f"GAME OVER.\n\n{consequence or 'Your action proves fatal or irrecoverable in this moment.'}\n\n"
            "Type 'start' to begin a new adventure, or describe a different action to rewind from the last safe moment."
        )
        return Command(
            update={
                "situation": [AIMessage(content=game_over_text)],
                "your_action": [resolved_action],
                "last_action": resolved_action,
                "tension": new_tension,
                "progress": new_progress,
                "named_entities": named_entities,
            },
            goto="end",
        )

    # Redirect: we still proceed, but the action is normalized.
    if verdict == "redirect":
        resolved_action = (
            resolved_action
            + ("\n" + consequence_blurb if consequence_blurb else "")
        ).strip()

    print("DEBUG: progreess is ", new_progress)
    return Command(
        update={
            "your_action": [resolved_action],
            "last_action": resolved_action,
            "tension": new_tension,
            "progress": new_progress,
            "named_entities": named_entities,
        },
        goto="storyteller",
    )


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
    if your_action_interrupt == CONTINUE_KEY:
        your_action_interrupt = CONTINUE_KEY

    if your_action_interrupt.lower() in ["done", "bye", "quit"]:
        return Command(update={"your_action": ["Story done"], "last_action_raw": "done", "last_action": "done"}, goto="end")

    return Command(
        update={
            "your_action": [your_action_interrupt],
            "last_action_raw": your_action_interrupt,
        },
        goto="judger_improver",
    )

def end(state: Story):
    print("\n\n\nThe end of your adventure!")


graph = StateGraph(Story)

graph.add_node("storyteller", storyteller)
graph.add_node("user", user)
graph.add_node("judger_improver", judger_improver)
graph.add_node("end", end)

graph.set_entry_point("storyteller")

graph.add_edge(START, "storyteller")
graph.add_edge("storyteller", "user")

# user -> adjudicator -> storyteller or the end
graph.add_edge("user", "judger_improver")

graph.set_finish_point("end")

memory = MemorySaver()
app = graph.compile(checkpointer=memory)


config = {"configurable": {
    "thread_id": uuid.uuid4()
}}
initial_scene = "There are two paths ahead of you in a dark forest: one leading to a spooky castle, the other to a serene lake."
initial_state = {
    "intro_text": initial_scene,
    "story_summary": initial_scene,
    "situation": [],
    "your_action": [],
    "theme": "fantasy",
    "char_name": "Unknown Hero",
    "world": {"location": "", "time": "", "notes": ""},
    "inventory": [],
    "turn_count": 0,
    "tension": 3,
    "named_entities": [],
    "last_action_raw": "",
    "last_action": "",
    "progress": 0,
}


# Everything after this is gradio and app management integration


def run_until_interrupt(app, starter, config):
    latest_message = "Nothing for now"

    for chunk in app.stream(starter, config=config):
        for node_id, value in chunk.items():
            if isinstance(value, dict) and value.get("situation"):
                latest_message = getattr(value["situation"][-1],
                                          "content", str(value["situation"][-1]))
                
        if "__interrupt__" in chunk:
            break
                
    return latest_message


def on_app_start():
    history = []
    thread_id = ""
    return history, thread_id


def on_user_message(user_message, history, thread_id):
    msg = (user_message or "").strip()
    if not msg:
        return "", history, thread_id, gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

    # MENU: return to crystal selection (clears current thread).
    if msg.lower() == "start" or msg == MENU_KEY or msg == "___MENU__":
        if thread_id and thread_id in THREAD_META:
            THREAD_META.pop(thread_id, None)
        return (
            "",
            [],
            "",
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            False,
            0.0,
        )

    # REWIND: drop the last user+assistant pair by replaying prior inputs.
    if msg == REWIND_KEY:
        was_game_over = False
        if history and isinstance(history, list):
            try:
                last = history[-1]
                if isinstance(last, dict) and ("GAME OVER" in str(last.get("content") or "")):
                    was_game_over = True
            except Exception:
                was_game_over = False

        meta = THREAD_META.get(thread_id or "")
        if not meta:
            return "", history, thread_id, gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
        inputs = list(meta.get("inputs") or [])
        if not inputs:
            return "", history, thread_id, gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

        inputs.pop()  # remove last input
        starter = meta.get("starter") or {}
        new_history, new_thread_id = _replay_thread(starter=starter, inputs=inputs)
        THREAD_META.pop(thread_id, None)
        THREAD_META[new_thread_id] = {"starter": starter, "inputs": inputs, "grace_next": was_game_over}
        return "", new_history, new_thread_id, gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

    meta = THREAD_META.get(thread_id or "")
    if not meta:
        # If we lost meta (server restart), force the user back to menu.
        return (
            "",
            [],
            "",
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            False,
            0.0,
        )

    meta.setdefault("inputs", []).append(msg)

    msg_for_graph = msg
    if meta.get("grace_next"):
        meta["grace_next"] = False
        msg_for_graph = GRACE_PERIOD_INVISIBLE_TELLER + msg

    next_scene = run_until_interrupt(app, Command(resume=msg_for_graph), config={"configurable": {"thread_id": thread_id}})
    if next_scene == "Nothing for now":
        next_scene = "The story has ended. Type __REWIND__ to rewind, or __MENU__ to return to the menu."

    history = (history or []) + [{"role": "user", "content": msg}, {"role": "assistant", "content": next_scene}]
    return "", history, thread_id, gr.update(), gr.update(), gr.update(), gr.update(), gr.update()


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
    # old opening
    # opening = (
    #     f"The user is {char_name}, the genre is {genre}. Open with an immersive scene ending with what do you do next?"
    # )
    print("theme is ", theme)

    intro_prompt = INTRO_PROMPT_TEMPLATE.format(theme=theme, char_name=char_name)
    written_intro = llm.invoke([SystemMessage(content=intro_prompt)]).content

    return {
        "intro_text": written_intro,
        "story_summary": written_intro,
        "situation": [],
        "your_action": [],
        "theme": theme,
        "char_name": char_name,
        "world": {"location": "", "time": "", "notes": ""},
        "inventory": [],
        "turn_count": 0,
        "tension": 3,
        "named_entities": [],
        "last_action_raw": "",
        "last_action": "",
        "progress": 0,
    }


# To make sure button or js does not interfere with genre
def on_begin_story_checked(char_name, genre, history, thread_id):
    print("on_begin_story received genre ", genre)
    if genre is None:
        raise ValueError("Genre become None - something is not working")
    return on_begin_story(char_name, genre, history, thread_id)


def on_begin_story(char_name, genre, history, thread_id):
    # standard stuff
    thread_id = _make_thread_id()
    starter = initialize_state(char_name, genre)
    opening = run_until_interrupt(app, starter, config={"configurable": {"thread_id": thread_id}})
    history = (history or []) + [{"role": "assistant", "content": opening}]

    THREAD_META[thread_id] = {"starter": starter, "inputs": []}

    # return for gradio
    return (
        history,
        thread_id,
        char_name,
        genre,
        True,
        time.time() + 3.5  # animation timing
    )

def continue_story(history, thread_id):
    if not thread_id:
        return history, thread_id

    meta = THREAD_META.get(thread_id)
    if meta is None:
        return history, thread_id
    meta.setdefault("inputs", []).append(CONTINUE_KEY)
    
    next_scene = run_until_interrupt(
        app,
        Command(resume=CONTINUE_KEY),
        config={"configurable": {"thread_id": thread_id}}
    )

    if next_scene == "Nothing for now":
        next_scene = "The story has ended. Type __REWIND__ to rewind, or __MENU__ to return to the menu."

    history = (history or []) + [
        {"role": "user", "content": "(Continue the story)"},
        {"role": "assistant", "content": next_scene}
    ]

    return history, thread_id


from gradio_frontend import build_demo, CSS, HEAD
demo = build_demo(
    on_user_message=on_user_message,
    on_begin_story=on_begin_story,
    on_begin_story_checked=on_begin_story_checked,
    on_continue_story=continue_story,
)
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
    