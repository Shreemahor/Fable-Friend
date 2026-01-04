import os
import io
import urllib.parse
import urllib.request
import urllib.error
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

from huggingface_hub import InferenceClient
from PIL import Image
import gradio as gr
import time
from file_of_prompts import (
    INTEMEDIARY_PROMPT,  # No longer in use but kept for reference
    INTRO_PROMPT_TEMPLATE,
    STORYTELLER_PROMPT_TEMPLATE,
    ADJUDICATION_PROMPT_TEMPLATE,
    IMAGE_PROMPT_BY_SYSTEM,
)
CONTINUE_KEY = "__CONTINUE__"
REWIND_KEY = "__REWIND__"
MENU_KEY = "__MENU__"
THREAD_META: Dict[str, Dict[str, Any]] = {}
# Marker used for one-turn grace period after retrying from GAME OVER.
# This is intentionally stripped from what the storyteller sees.
GRACE_PERIOD_INVISIBLE_TELLER = "grace_period:"


# Role/genre safety:
# If the user somehow bypasses the UI and sends a role that doesn't belong to the chosen genre,
# we snap the genre to the role's parent genre.
ROLE_TO_GENRE: Dict[str, str] = {
    # fantasy
    "valiant_paladin": "fantasy",
    "elven_ranger": "fantasy",
    "arcane_scholar": "fantasy",
    "shadow_thief": "fantasy",
    "circle_druid": "fantasy",
    # scifi
    "elite_netrunner": "scifi",
    "street_samurai": "scifi",
    "tech_specialist": "scifi",
    "social_face": "scifi",
    "heavy_solo": "scifi",
    # grimdark
    "plague_doctor": "grimdark",
    "broken_knight": "grimdark",
    "famine_scavenger": "grimdark",
    "penitent_zealot": "grimdark",
    "grave_robber": "grimdark",
    # noir
    "hardboiled_pi": "noir",
    "femme_fatale": "noir",
    "dirty_cop": "noir",
    "underground_informant": "noir",
    "forensic_analyst": "noir",
    # space_opera
    "starship_pilot": "space_opera",
    "alien_emissary": "space_opera",
    "bounty_hunter": "space_opera",
    "naval_officer": "space_opera",
    "psionic_adept": "space_opera",
}

ROLE_DISPLAY: Dict[str, str] = {
    "valiant_paladin": "Valiant Paladin",
    "elven_ranger": "Elven Ranger",
    "arcane_scholar": "Arcane Scholar",
    "shadow_thief": "Shadow Thief",
    "circle_druid": "Circle Druid",
    "elite_netrunner": "Elite Netrunner",
    "street_samurai": "Street Samurai",
    "tech_specialist": "Tech Specialist",
    "social_face": "Social Face",
    "heavy_solo": "Heavy Solo",
    "plague_doctor": "Plague Doctor",
    "broken_knight": "Broken Knight",
    "famine_scavenger": "Famine Scavenger",
    "penitent_zealot": "Penitent Zealot",
    "grave_robber": "Grave Robber",
    "hardboiled_pi": "Hardboiled P.I.",
    "femme_fatale": "Femme Fatale",
    "dirty_cop": "Dirty Cop",
    "underground_informant": "Underground Informant",
    "forensic_analyst": "Forensic Analyst",
    "starship_pilot": "Starship Pilot",
    "alien_emissary": "Alien Emissary",
    "bounty_hunter": "Bounty Hunter",
    "naval_officer": "Naval Officer",
    "psionic_adept": "Psionic Adept",
}


IMAGE_STYLE_PRESETS: Dict[str, str] = {
    # Keep these short and model-friendly; they'll be injected into every image prompt.
    "cinematic_concept_art": "cinematic concept art, dramatic lighting, wide shot",
    "anime_cel_shaded": "anime cel-shaded illustration, clean lineart, vibrant colors",
    "watercolor_storybook": "watercolor storybook illustration, soft wash, paper texture",
}


def _normalize_genre_for_role(*, genre: str, role_id: str) -> tuple[str, str]:
    """Return (genre, role_display) after validating role_id belongs to genre.

    If role_id maps to a different genre, snap genre to that genre.
    """
    genre = (genre or "").strip()
    role_id = (role_id or "").strip()

    role_display = (ROLE_DISPLAY.get(role_id) or role_id or "Adventurer").strip()
    mapped_genre = ROLE_TO_GENRE.get(role_id)
    if mapped_genre and mapped_genre != genre:
        print(f"[begin_story] role {role_id!r} belongs to {mapped_genre!r}; overriding genre {genre!r}")
        genre = mapped_genre
    return genre, role_display


def _ui_test_image_path() -> str | None:
    """Return a local image path to show in-chat for UI testing, if present."""
    candidates = [
        os.path.join("frontend", "test.png"),
        "test.png",
    ]
    for candidate in candidates:
        try:
            if os.path.exists(candidate):
                return candidate
        except Exception:
            continue
    return None


def _append_ui_test_image_message(history: list[dict]) -> None:
    path = _ui_test_image_path()
    if not path:
        return
    history.append({"role": "assistant", "content": {"path": path}})


def _persist_chat_image_bytes(*, image_bytes: bytes, thread_id: str) -> str | None:
    """Persist PNG bytes under frontend/ so Gradio can serve it; return relative file path."""
    if not image_bytes:
        return None
    try:
        os.makedirs(os.path.join("frontend", "runtime_images"), exist_ok=True)
        stamp = int(time.time() * 1000)
        safe_thread = (thread_id or "thread").replace("/", "_").replace("\\", "_")
        filename = f"{safe_thread}_{stamp}.png"
        rel_path = os.path.join("frontend", "runtime_images", filename)
        with open(rel_path, "wb") as f:
            f.write(image_bytes)
        _cleanup_runtime_images()
        return rel_path
    except Exception as e:
        print(f"[chat_image] failed to persist image: {e}")
        return None


def _cleanup_runtime_images() -> None:
    """Best-effort cleanup so frontend/runtime_images doesn't grow unbounded."""
    try:
        max_files = int(os.environ.get("RUNTIME_IMAGES_MAX_FILES") or "200")
    except Exception:
        max_files = 50

    if max_files <= 0:
        return

    try:
        dir_path = os.path.join("frontend", "runtime_images")
        if not os.path.isdir(dir_path):
            return
        entries: list[tuple[float, str]] = []
        for name in os.listdir(dir_path):
            if not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            path = os.path.join(dir_path, name)
            try:
                entries.append((os.path.getmtime(path), path))
            except Exception:
                continue
        if len(entries) <= max_files:
            return
        entries.sort(key=lambda t: t[0], reverse=True)
        for _, path in entries[max_files:]:
            try:
                os.remove(path)
            except Exception:
                continue
    except Exception:
        return


def _append_real_image_message(history: list[dict], *, image_bytes: Any, thread_id: str) -> None:
    """Append a real generated image to chat history."""
    if not isinstance(image_bytes, (bytes, bytearray)):
        return
    path = _persist_chat_image_bytes(image_bytes=bytes(image_bytes), thread_id=thread_id)
    if not path:
        return
    history.append({"role": "assistant", "content": {"path": path}})


def _find_last_assistant_text_index(history: list[dict]) -> int | None:
    for idx in range(len(history) - 1, -1, -1):
        item = history[idx]
        if not isinstance(item, dict):
            continue
        if item.get("role") != "assistant":
            continue
        content = item.get("content")
        if isinstance(content, str):
            return idx
    return None


def _image_payload_to_pil(image_payload: Any) -> Any:
    """Convert a msgpack-serializable image payload (PNG bytes) into a PIL Image for Gradio."""
    if image_payload is None:
        return None
    if isinstance(image_payload, Image.Image):
        return image_payload
    if isinstance(image_payload, (bytes, bytearray)):
        try:
            return Image.open(io.BytesIO(image_payload))
        except Exception:
            return None
    return image_payload


def _image_payloads_to_pil_list(image_payloads: Any) -> list[Any]:
    if not image_payloads:
        return []
    if not isinstance(image_payloads, list):
        return []
    out: list[Any] = []
    for item in image_payloads:
        pil = _image_payload_to_pil(item)
        if pil is not None:
            out.append(pil)
    return out

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


def _replay_thread(*, starter: dict, inputs: List[str]) -> tuple[list, str, Any, list[Any]]:
    """Rebuild a thread by replaying inputs from the same starter into a new thread_id."""
    new_thread_id = _make_thread_id()
    cfg = {"configurable": {"thread_id": new_thread_id}}

    history: list[dict] = []
    opening, opening_image = run_until_interrupt(app, starter, config=cfg)
    history.append({"role": "assistant", "content": opening})
    if opening_image is not None:
        _append_real_image_message(history, image_bytes=opening_image, thread_id=new_thread_id)
    last_image = opening_image
    images: list[Any] = []
    if opening_image is not None:
        images.append(opening_image)

    for msg in inputs:
        next_scene, new_image = run_until_interrupt(app, Command(resume=msg), config=cfg)
        if new_image is not None:
            last_image = new_image
            images.append(new_image)
        history.extend(
            [
                {"role": "user", "content": "(Continue the story)" if msg == CONTINUE_KEY else msg},
                {"role": "assistant", "content": next_scene},
            ]
        )
        if new_image is not None:
            _append_real_image_message(history, image_bytes=new_image, thread_id=new_thread_id)

    return history, new_thread_id, last_image, images


def _get_latest_interrupt_configs(thread_id: str) -> list[Any]:
    """Return interrupt snapshots (newest first) for a given thread_id."""
    try:
        cfg = {"configurable": {"thread_id": thread_id}}
        snapshots = list(app.get_state_history(cfg))
        interrupts = [s for s in snapshots if getattr(s, "interrupts", None)]
        interrupts.sort(key=lambda s: int(getattr(s, "index", 0)), reverse=True)
        return interrupts
    except Exception as e:
        print(f"[rewind] failed to read state history: {e}")
        return []


def _revert_history_by_record(history: list[dict], record: dict) -> list[dict]:
    history = list(history or [])
    rtype = record.get("type")

    if rtype == "user":
        before_len = int(record.get("history_len_before") or 0)
        if before_len < 0:
            before_len = 0
        return history[:before_len]

    if rtype == "continue":
        idx = record.get("assistant_text_index")
        prior_text = record.get("assistant_text_before")
        if isinstance(idx, int) and 0 <= idx < len(history) and isinstance(history[idx], dict):
            history[idx]["content"] = prior_text
        # Remove any appended image message.
        if record.get("image_added"):
            # Usually the image is the last message.
            if history and isinstance(history[-1], dict) and isinstance(history[-1].get("content"), dict) and "path" in history[-1].get("content", {}):
                history.pop()
        return history

    return history


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
    role: str
    image_style: str

    world: Dict[str, Any]
    inventory: List[str]
    turn_count: int
    tension: int
    named_entities: List[str]

    last_action_raw: str
    last_action: str
    progress: int
    is_key_event: bool  # True on the intro turn and on milestone scenes.

    img_generation_rules: str
    last_image_prompt: str
    last_image: Any


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
                # Intro is a key scene for generating the first image.
                "is_key_event": True,
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
    role = (state.get("role") or "Adventurer").strip()

    last_action = (state.get("last_action") or "").strip()
    last_action_raw = (state.get("last_action_raw") or "").strip()
    if last_action_raw.startswith(GRACE_PERIOD_INVISIBLE_TELLER):
        last_action_raw = last_action_raw[len(GRACE_PERIOD_INVISIBLE_TELLER):].lstrip()
    is_continue = (last_action == CONTINUE_KEY)
    progress = int(state.get("progress")) or 0
    is_key_event = (progress >= 100)
    length_rule = "12-18 sentences" if is_key_event else ("2-3 sentences" if is_continue else "5-6 sentences")

    phase = "early" if progress < 34 else ("mid" if progress < 67 else ("late" if progress < 100 else "milestone"))

    named_entities = state.get("named_entities") or []
    existing_names = ", ".join(named_entities) if named_entities else "(none yet)"
    turn_count = int(state.get("turn_count")) or 0
    # every 3 turns (but milestones always end with a hook)
    should_ask_question = True if is_key_event else ((turn_count % 3) == 0)
    # every other turn (but milestones may introduce a major new thread)
    allow_new_proper_noun = True if is_key_event else ((turn_count % 2) == 0)

    prompt = STORYTELLER_PROMPT_TEMPLATE.format(
        length_rule=length_rule,
        char_name=char_name,
        theme=state["theme"],
        role=role,
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

    if is_key_event:
        print("[storyteller_node] Milestone scene generated. Resetting progress.")
        return {
            "situation": [AIMessage(content=continuation)],
            "turn_count": turn_count + 1,
            "progress": 0,
            # Preserve milestone info for the image node (progress is reset here).
            "is_key_event": True,
        }

    print(f"[storyteller_node] Generated situation:\n{continuation}\n")
    return {
       "situation": [AIMessage(content=continuation)],
       "turn_count": turn_count + 1,
         "is_key_event": False,
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

    # One-turn grace period after rewinding from a GAME OVER: avoid instant re-death
    if grace_turn and verdict == "game_over":
        verdict = "redirect"
        if not consequence:
            consequence = "You avoid the worst at the last instant, but suffer a brutal setback instead."
        if progress_change < 1:
            progress_change = 1

    # Clamp and apply
    if tension_change < -2:
        tension_change = -2
    if tension_change > 3:
        tension_change = 3

    if progress_change < 0:
        progress_change = 0
    if progress_change > 20:
        progress_change = 20

    # Continuation still actually advances still.
    if raw_action == CONTINUE_KEY and progress_change < 4:
        progress_change = 4

    new_tension = max(0, min(10, tension + tension_change))
    new_progress = max(0, min(100, progress + progress_change))

    named_entities = list(state.get("named_entities") or [])
    if not allow_new_proper_noun:
        new_name = ""
    if new_name and (new_name not in named_entities) and (len(named_entities) < 12):
        named_entities.append(new_name)

    if resolved_action.upper() == "CONTINUE" or resolved_action == CONTINUE_KEY:
        resolved_action = CONTINUE_KEY

    # Get consequence blurb that the storyteller must incorporate.
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


def get_image(state: Story):

    print("[image_node] At image node")

    hf_token = os.environ.get("HF_TOKEN")
    client = InferenceClient(provider="nebius", api_key=hf_token) if hf_token else None

    turn = int(state.get("turn_count")) or 0
    # Cadence: intro/milestone scenes always generate; otherwise generate every 3 turns.
    # (turn_count is incremented in storyteller, so intro is typically turn==1.)
    should_generate_image = bool(state.get("is_key_event")) or ((turn % 3) == 1)

    if should_generate_image:
        scene_text = ""
        try:
            scene_text = str(state.get("situation")[-1].content)
        except Exception:  # if something goes wrong
            scene_text = ""

        last_action = str(state.get("last_action") or "").strip()
        last_action_raw = str(state.get("last_action_raw") or "").strip()
        if last_action_raw.startswith(GRACE_PERIOD_INVISIBLE_TELLER):
            last_action_raw = last_action_raw[len(GRACE_PERIOD_INVISIBLE_TELLER):].lstrip()

        img_generation_rules = (state.get("img_generation_rules") or "").strip()
        last_image_prompt = (state.get("last_image_prompt") or "").strip()
        theme = (state.get("theme") or "fantasy").strip()
        char_name = (state.get("char_name") or "Unknown Hero").strip()
        role = (state.get("role") or "Adventurer").strip()
        image_style_id = (state.get("image_style") or "").strip()
        image_style_preset = (IMAGE_STYLE_PRESETS.get(image_style_id) or "").strip()

        def _clamp_line(s: str, max_len: int) -> str:
            s = " ".join((s or "").split())
            if len(s) <= max_len:
                return s
            return (s[: max_len - 1].rstrip() + "…")

        def _clamp_rules(text: str) -> str:
            lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
            lines = lines[:3]
            return "\n".join(_clamp_line(ln, 140) for ln in lines)

        # this runs only once to establish the image generation guidelines for the rest of the story
        if not img_generation_rules:
            rule_prompt = (
                "You create a tiny, stable visual tagset for diffusion prompting.\n"
                "Output EXACTLY 3 lines, no extra text, no names, no ages, no proper nouns:\n"
                "STYLE: <8-12 words describing a consistent visual style>\n"
                "HERO: <3-6 words describing the protagonist silhouette/gear archetype>\n"
                "MOTIFS: <3-6 short nouns, comma-separated>\n\n"
                "Rules:\n"
                "- Do NOT write paragraphs.\n"
                "- Do NOT mention the protagonist's name.\n"
                "- Keep it generic and drawable by small models.\n\n"
                f"Theme: {theme}\n"
                f"Role: {role}\n"
                + (f"Style preference (important): {image_style_preset}\n" if image_style_preset else "")
                + "Intro (for vibe only; do not copy names/phrases):\n"
                + f"{_clamp_line((state.get('intro_text') or '').strip(), 500)}"
            )
            img_generation_rules = llm2.invoke([SystemMessage(content=rule_prompt)]).content

        img_generation_rules = _clamp_rules(img_generation_rules)

        print("DEBUG Image generation rules:\n", img_generation_rules)

        # Create a SHORT prompt that focuses on the visible action/scene (not lore, not names).
        # Include the player's action so images actually change with input.
        action_hint = ""
        if last_action and last_action != CONTINUE_KEY:
            action_hint = last_action
        elif last_action_raw and last_action_raw != CONTINUE_KEY:
            action_hint = last_action_raw

        image_prompt_human = (
            "Goal: output ONE short diffusion prompt (single line).\n"
            "Hard limits:\n"
            "- 12 to 28 words total\n"
            "- NO proper nouns, NO character names, NO ages, NO long backstory\n"
            "- Prefer depicting the main action + environment + 1-2 key objects\n"
            "- If possible, avoid close-up portraits; show the scene/vehicles/action\n"
            "- If the player's action suggests an action shot, reflect it\n\n"
            + (f"STYLE PRESET (must include in output):\n{_clamp_line(image_style_preset, 120)}\n\n" if image_style_preset else "")
            + f"STYLE TAGS:\n{img_generation_rules}\n\n"
            + (f"PREV PROMPT (for continuity only):\n{_clamp_line(last_image_prompt, 180)}\n\n" if last_image_prompt else "")
            + (f"PLAYER ACTION (important):\n{_clamp_line(action_hint, 180)}\n\n" if action_hint else "")
            + f"SCENE TEXT (may be verbose; extract gist):\n{_clamp_line(scene_text, 600)}\n\n"
            "Examples of acceptable outputs:\n"
            "- massive starship dragged into a vortex, small fighter attacking drones, neon space debris, cinematic wide shot\n"
            "- rain-soaked alley stakeout, detective silhouette under streetlamp, distant sirens, gritty noir lighting\n"
            "Now output ONLY the prompt line."
        )

        image_prompt = llm2.invoke(
            [SystemMessage(content=IMAGE_PROMPT_BY_SYSTEM), HumanMessage(content=image_prompt_human)]
        ).content.strip()

        # Ensure the user-selected style preset is always included.
        if image_style_preset:
            merged = f"{image_style_preset}, {image_prompt}" if image_prompt else image_style_preset
            image_prompt = merged

        # Final clamp tightening check: keep it one line, short.
        image_prompt = " ".join(image_prompt.split())
        image_prompt = _clamp_line(image_prompt, 260)
        print("DEBUG Generated image prompt:\n", image_prompt)

        def _ensure_png_bytes(raw: bytes) -> bytes:
            if not raw:
                return raw
            try:
                pil = Image.open(io.BytesIO(raw))
                buf = io.BytesIO()
                try:
                    pil.convert("RGB").save(buf, format="PNG", optimize=True)
                except Exception:
                    pil.save(buf, format="PNG")
                return buf.getvalue()
            except Exception:
                return raw

        def _pollinations_text_to_image_bytes(prompt_text: str) -> bytes:
            api_key = (os.environ.get("POLLINATIONS_API_KEY") or "").strip()
            base = "https://gen.pollinations.ai/image/"
            encoded_prompt = urllib.parse.quote((prompt_text or "").strip(), safe="")
            params: dict[str, str] = {
                "model": "turbo",
                "width": str(int(os.environ.get("POLLINATIONS_WIDTH") or "768")),
                "height": str(int(os.environ.get("POLLINATIONS_HEIGHT") or "768")),
                # Keep defaults conservative; can be tuned later.
                "safe": "true",
            }
            headers: dict[str, str] = {
                "User-Agent": "FableFriend/1.0",
            }
            if api_key:
                if api_key.startswith("sk_"):
                    headers["Authorization"] = f"Bearer {api_key}"
                elif api_key.startswith("pk_"):
                    params["key"] = api_key

            url = base + encoded_prompt + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                raise RuntimeError(f"Pollinations HTTP {getattr(e, 'code', '?')}: {body[:300]}")
            return _ensure_png_bytes(data)

        image_bytes: bytes | None = None
        hf_error: Exception | None = None

        # Primary: Hugging Face inference
        if client is None:
            print("[image_node] HF_TOKEN not set; will try Pollinations fallback")
        elif False:  # Disable HF for now due to cost
            try:
                image = client.text_to_image(
                    image_prompt,
                    model="black-forest-labs/FLUX.1-schnell",
                )

                # IMPORTANT: Do NOT store a PIL Image in LangGraph state.
                # MemorySaver checkpoints serialize state via msgpack and PIL objects are not serializable.
                buf = io.BytesIO()
                try:
                    image.convert("RGB").save(buf, format="PNG", optimize=True)
                except Exception:
                    image.save(buf, format="PNG")
                image_bytes = buf.getvalue()
            except Exception as e:
                hf_error = e
                print(f"[image_node] HF image generation failed; falling back to Pollinations: {e}")

        # Fallback: Pollinations with the SAME prompt
        if not image_bytes or True:
            try:
                image_bytes = _pollinations_text_to_image_bytes(image_prompt)
            except Exception as e:
                print(f"[image_node] Pollinations fallback failed: {e}")
                if hf_error:
                    print(f"[image_node] Original HF error: {hf_error}")
                return {}

        return {
            "last_image": image_bytes,
            "last_image_prompt": image_prompt,
            "img_generation_rules": img_generation_rules,
            # Reset key-scene flag
            "is_key_event": False,
        }
    else:
        print("[image_node] No need for image generation this turn.")
        return {}


def end(state: Story):
    print("\n\n\nThe end of your adventure!")  # just for reference even though unreachable


graph = StateGraph(Story)

graph.add_node("storyteller", storyteller)
graph.add_node("user", user)
graph.add_node("judger_improver", judger_improver)
graph.add_node("image", get_image)
graph.add_node("end", end)

graph.set_entry_point("storyteller")

graph.add_edge(START, "storyteller")
# Run image generation BEFORE the interrupting user node so the image update
# isn't skipped/canceled when the graph hits interrupt().
graph.add_edge("storyteller", "image")
graph.add_edge("image", "user")
# user -> adjudicator -> storyteller
graph.add_edge("user", "judger_improver")

graph.set_finish_point("end")  # even though you will never reach this

memory = MemorySaver()
app = graph.compile(checkpointer=memory)
# print("DEBUG: Graph structure:\n", app.get_graph().draw_ascii())


config = {"configurable": {
    "thread_id": uuid.uuid4()
}}

# This part is not actually used or important, it's just an old version, kept for testing
initial_scene = "There are two paths ahead of you in a dark forest: one leading to a spooky castle, the other to a serene lake."

initial_state = {
    "intro_text": "Nothing for now",
    "story_summary": "Nothing for now",
    "situation": [],
    "your_action": [],
    "theme": "fantasy",
    "char_name": "Unknown Hero",
    "role": "",
    "image_style": "",
    "world": {"location": "", "time": "", "notes": ""},
    "inventory": [],
    "turn_count": 0,
    "tension": 3,
    "named_entities": [],
    "last_action_raw": "",
    "last_action": "",
    "progress": 0,
    "is_key_event": False,
    "img_generation_rules": "",
    "last_image_prompt": "",
    "last_image": None,
}


# Everything after this is gradio and app management integration


def run_until_interrupt(app, starter, config):
    latest_message = "Nothing for now"
    latest_image = None

    for chunk in app.stream(starter, config=config):
        for node_id, value in chunk.items():
            if isinstance(value, dict) and value.get("situation"):
                latest_message = getattr(value["situation"][-1],
                                          "content", str(value["situation"][-1]))

            if isinstance(value, dict) and ("last_image" in value):
                if value.get("last_image") is not None:
                    latest_image = value.get("last_image")
                
        if "__interrupt__" in chunk:
            break
                
    return latest_message, latest_image


def on_app_start():
    history = []
    thread_id = ""
    return history, thread_id


def on_user_message(user_message, history, thread_id):
    msg = (user_message or "").strip()
    if not msg:
        meta = THREAD_META.get(thread_id or "") or {}
        return "", history, thread_id, gr.update(), gr.update(), gr.update()

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
        )

    # REWIND: drop the last user+assistant pair by replaying prior inputs.
    if msg == REWIND_KEY:
        meta = THREAD_META.get(thread_id or "") or {}
        if not meta:
            return "", history, thread_id, gr.update(), gr.update(), gr.update()

        records = list(meta.get("turn_records") or [])
        if not records:
            return "", history, thread_id, gr.update(), gr.update(), gr.update()

        # Restore previous LangGraph interrupt checkpoint (prevents re-generation).
        interrupts = _get_latest_interrupt_configs(thread_id)
        if len(interrupts) >= 2:
            # Move to the previous interrupt.
            meta["cfg"] = interrupts[1].config

        record = records.pop()
        meta["turn_records"] = records

        # Keep meta inputs/images consistent.
        inputs = list(meta.get("inputs") or [])
        if inputs:
            inputs.pop()
        meta["inputs"] = inputs

        if record.get("image_added") and (meta.get("images") or []):
            try:
                meta["images"].pop()
            except Exception:
                pass
        meta["last_image"] = (meta.get("images") or [None])[-1] if meta.get("images") else None

        new_history = _revert_history_by_record(history, record)
        THREAD_META[thread_id] = meta
        return "", new_history, thread_id, gr.update(), gr.update(), gr.update()

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
        )

    meta.setdefault("inputs", []).append(msg)

    msg_for_graph = msg
    if meta.get("grace_next"):
        meta["grace_next"] = False
        msg_for_graph = GRACE_PERIOD_INVISIBLE_TELLER + msg

    # Always run from the pinned checkpoint config if available.
    cfg = meta.get("cfg") or {"configurable": {"thread_id": thread_id}}
    next_scene, new_image = run_until_interrupt(app, Command(resume=msg_for_graph), config=cfg)
    if next_scene == "Nothing for now":
        next_scene = "The story has ended. Type __REWIND__ to rewind, or __MENU__ to return to the menu."

    if new_image is not None:
        meta["last_image"] = new_image
        meta.setdefault("images", []).append(new_image)

    history = list(history or [])
    record = {"type": "user", "history_len_before": len(history), "image_added": bool(new_image is not None)}
    history = history + [{"role": "user", "content": msg}, {"role": "assistant", "content": next_scene}]
    try:
        if new_image is not None:
            _append_real_image_message(history, image_bytes=new_image, thread_id=thread_id)
    except Exception:
        pass

    meta.setdefault("turn_records", []).append(record)
    # Pin the current interrupt checkpoint config for reliable rewinds.
    try:
        meta["cfg"] = app.get_state({"configurable": {"thread_id": thread_id}}).config
    except Exception:
        pass
    return "", history, thread_id, gr.update(), gr.update(), gr.update()


def on_menu_click(history, thread_id):
    return on_user_message(MENU_KEY, history, thread_id)


def on_rewind_click(history, thread_id):
    return on_user_message(REWIND_KEY, history, thread_id)


def initialize_state(char_name, genre, role_id, image_style: str = "") -> dict:
    print("DEBUG on_begin_story received genre =", genre)
    char_name = (char_name or "Unknown Hero").strip()
    genre = (genre or "fantasy").strip()
    role_id = (role_id or "").strip()

    genre, role_display = _normalize_genre_for_role(genre=genre, role_id=role_id)
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

    intro_prompt = INTRO_PROMPT_TEMPLATE.format(theme=theme, char_name=char_name, role=role_display)



    #  no longer repalcing reall llm call temporarliy to prevent api
    written_intro = llm.invoke([SystemMessage(content=intro_prompt)]).content
    # written_intro = 'Just testing'



    return {
        "intro_text": written_intro,
        "story_summary": written_intro,
        "situation": [],
        "your_action": [],
        "theme": theme,
        "char_name": char_name,
        "role": role_display,
        "image_style": (image_style or "").strip(),
        "world": {"location": "", "time": "", "notes": ""},
        "inventory": [],
        "turn_count": 0,
        "tension": 3,
        "named_entities": [],
        "last_action_raw": "",
        "last_action": "",
        "progress": 0,
        # Intro turn should generate the first image.
        "is_key_event": True,
        "img_generation_rules": "",
        "last_image_prompt": "",
        "last_image": None,
    }


# To make sure button or js does not interfere with genre
def on_begin_story_checked(char_name, genre, role_id, image_style, history, thread_id):
    print("on_begin_story received genre ", genre)
    # Never hard-fail here: a malicious/buggy client can send None or mismatched
    # values and we should recover gracefully rather than crashing the app.
    if genre is None:
        genre = "fantasy"
    if role_id is None:
        role_id = ""
    if image_style is None:
        image_style = ""
    return on_begin_story(char_name, genre, role_id, image_style, history, thread_id)


def on_begin_story(char_name, genre, role_id, image_style, history, thread_id):
    # standard stuff
    thread_id = _make_thread_id()
    normalized_genre, _role_display = _normalize_genre_for_role(
        genre=(genre or "fantasy"),
        role_id=(role_id or ""),
    )
    starter = initialize_state(char_name, normalized_genre, role_id, image_style)
    opening, opening_image = run_until_interrupt(app, starter, config={"configurable": {"thread_id": thread_id}})
    history = (history or []) + [{"role": "assistant", "content": opening}]
    try:
        if opening_image is not None:
            _append_real_image_message(history, image_bytes=opening_image, thread_id=thread_id)
    except Exception:
        pass

    images: list[Any] = []
    if opening_image is not None:
        images.append(opening_image)
    meta: Dict[str, Any] = {
        "starter": starter,
        "inputs": [],
        "last_image": opening_image,
        "images": images,
        "turn_records": [],
    }
    try:
        meta["cfg"] = app.get_state({"configurable": {"thread_id": thread_id}}).config
    except Exception:
        pass
    THREAD_META[thread_id] = meta

    # return for gradio
    return (
        history,
        thread_id,
        char_name,
        normalized_genre,
    )

def continue_story(history, thread_id):
    if not thread_id:
        return history, thread_id

    meta = THREAD_META.get(thread_id)
    if meta is None:
        return history, thread_id
    meta.setdefault("inputs", []).append(CONTINUE_KEY)
    
    cfg = meta.get("cfg") or {"configurable": {"thread_id": thread_id}}
    next_scene, new_image = run_until_interrupt(app, Command(resume=CONTINUE_KEY), config=cfg)

    if next_scene == "Nothing for now":
        next_scene = "The story has ended. Type __REWIND__ to rewind, or __MENU__ to return to the menu."

    if new_image is not None:
        meta["last_image"] = new_image
        meta.setdefault("images", []).append(new_image)

    # Continue should NOT add a synthetic user message; append to the last assistant *text* message.
    history = list(history or [])
    last_text_idx = _find_last_assistant_text_index(history)
    record = {
        "type": "continue",
        "assistant_text_index": last_text_idx,
        "assistant_text_before": (str(history[last_text_idx].get("content") or "") if last_text_idx is not None else ""),
        "image_added": bool(new_image is not None),
    }
    if last_text_idx is not None:
        prior = str(history[last_text_idx].get("content") or "")
        history[last_text_idx]["content"] = (prior + "\n\n" + next_scene).strip() if prior else next_scene
    else:
        history.append({"role": "assistant", "content": next_scene})

    try:
        if new_image is not None:
            _append_real_image_message(history, image_bytes=new_image, thread_id=thread_id)
    except Exception:
        pass

    meta.setdefault("turn_records", []).append(record)
    try:
        meta["cfg"] = app.get_state({"configurable": {"thread_id": thread_id}}).config
    except Exception:
        pass

    return history, thread_id


from gradio_frontend import build_demo, CSS, HEAD
demo = build_demo(
    on_user_message=on_user_message,
    on_begin_story=on_begin_story,
    on_begin_story_checked=on_begin_story_checked,
    on_continue_story=continue_story,
    on_rewind_story=on_rewind_click,
    on_menu_story=on_menu_click,
)
if __name__ == "__main__":
    demo.queue().launch(theme=gr.themes.Soft(
                            primary_hue="purple",
                            secondary_hue="yellow",
                            neutral_hue="slate",
                            text_size=gr.themes.sizes.text_md,
                            radius_size=gr.themes.sizes.radius_md,
                            ).set(
                            input_background_fill="#663399",
                            input_background_fill_dark="#663399",
                            panel_background_fill="#663399",
                            panel_background_fill_dark="#663399",
                            ),
                        css=CSS,
                        head=HEAD,
                        allowed_paths=[os.path.abspath("frontend")]
                        )
    