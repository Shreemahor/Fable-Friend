import gradio as gr
import time
import html


HEAD = """
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Fredoka:wght@400;600&family=Lato:wght@300;400&display=swap" rel="stylesheet">
<script defer src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>

<script>
  window.addEventListener("DOMContentLoaded", () => {
    const player = document.getElementById("ball-lottie");
    if (!player) return;
    player.addEventListener("ready", () => player.stop());
  });
</script>
"""


CSS = """
:root {
  --primary-glow: #5b8bff;
  --secondary-glow: #d946ef;
  --bg-dark: #0f1116;
  --gold-primary: #FFD700;
  --gold-secondary: #FF8C00;
  --purple-dark: #2e0249;
  --purple-deep: #1a0b2e;
}

.readout-box {
  background: var(--purple-dark) !important;
  color: #ffffff !important;
  border: 1px solid rgba(255, 215, 0, 0.35) !important;
  border-radius: 12px;
  padding: 10px 12px;
}

.readout-box .readout-label {
  opacity: 0.9;
  font-weight: 700;
  margin-bottom: 2px;
}

.readout-box .readout-value {
  opacity: 0.95;
}

#crystal-gap, #crystal-gap * {
  background: transparent !important;
  border: none !important;
}

.crystal-gap-inner {
  width: 100%;
  height: 260px;
  background: transparent;
}

body {
  margin: 0 !important;
  background-color: var(--bg-dark) !important;
  color: #e9edf5 !important;
  font-family: 'Lato', sans-serif !important;
}

/*
 .gradio-container .wrap, .gradio-container .contain {
// background: transparent !important;
// }
*/

#title-screen .wrap, #title-screen .contain,
#crystal-screen .wrap, #crystal-screen .contain,
#chat-screen .wrap, #chat-screen .contain {
  background: transparent !important;
}

/* Dropdown popup background + text */
.gradio-container [role="listbox"] {
  background: var(--purple-deep) !important;
  border: 1px solid var(--gold-primary) !important;
}

.gradio-container [role="option"] {
  background: transparent !important;
  color: var(--gold-primary) !important;
}

.gradio-container [role="option"]:hover {
  background: rgba(255, 215, 0, 0.12) !important;
}

.gradio-container {
  position: relative !important;
  z-index: 0 !important;
}

.gradio-container {
  --body-background-fill: var(--bg-dark) !important;
  --background-fill-primary: transparent !important;
  --background-fill-secondary: transparent !important;
  --block-background-fill: transparent !important;
  --panel-background-fill: transparent !important;
  --border-color-primary: transparent !important;
}

#crystal-ball-bg {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  z-index: 9999;
  pointer-events: none;

  opacity: 0;
  transition: opacity 0.35s ease, filter 1.5s ease;
}

#crystal-ball-bg {
  z-index: 9999 !important;
}

#crystal-ball-bg, #crystal-ball-bg * {
  pointer-events: none !important;
}

#crystal-ball-bg.active {
  opacity: 1;
}

#crystal-ball-bg {
  transform: scale(1);
  transform-origin: center;
  transition: transform 2s cubic-bezier(0.7, 0, 0.3, 1), filter 1.5s ease;
}

#crystal-ball-bg.zoomed-in {
  transform: scale(20);
  filter: blur(0px) brightness(1);
}

#ball-content {
  transition: opacity 0.5s ease, transform 0.5s ease;
}

#ball-content.fade-out {
  opacity: 0;
  transform: scale(0.85);
}

/* CRYSTAL BALLL SIZE ADJUSTS MENTS IS HERE*/
#crystal-ball-bg lottie-player {
  width: 800px;
  height: 800px;
  filter: drop-shadow(0 0 30px rgba(91, 139, 255, 0.3));
}

#title-screen, #crystal-screen, #chat-screen {
  position: relative;
  z-index: 10;
  width: 100%;
  min-height: 100vh;
}

#title-screen, #crystal-screen, #chat-screen {
  position: relative !important;
  z-index: 10 !important;
  background: transparent !important;
}

.title-text {
  font-family: 'Fredoka', sans-serif;
  font-size: 6rem;
  font-weight: 600;
  background: linear-gradient(135deg, var(--gold-primary) 0%, var(--gold-secondary) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 30px rgba(255, 140, 0, 0.4);
  margin: 0 0 1rem 0;
  text-align: center;
}

.subtitle-text {
  font-family: 'Fredoka', sans-serif;
  font-size: 2rem;
  color: var(--gold-primary);
  margin: 0 0 3rem 0;
  letter-spacing: 1px;
  text-align: center;
}

.screen-inner {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 24px;
  text-align: center;
}

#crystal-screen .screen-inner {
  justify-content: flex-start;
  padding-top: 24px;
}

.btn-magic button {
  background: var(--purple-dark) !important;
  border: 2px solid var(--secondary-glow) !important;
  color: var(--gold-primary) !important;
  padding: 15px 40px !important;
  font-size: 1.2rem !important;
  border-radius: 50px !important;
  transition: all 0.3s ease !important;
  text-transform: uppercase;
  letter-spacing: 1px;
  box-shadow: 0 0 15px rgba(217, 70, 239, 0.2);
  font-weight: 700 !important;
}

.btn-magic button:hover {
  background: var(--secondary-glow) !important;
  color: var(--gold-primary) !important;
  box-shadow: 0 0 30px rgba(217, 70, 239, 0.6) !important;
  transform: translateY(-2px);
}

.ball-content {
  width: 400px;
  text-align: center;
  background: rgba(26, 11, 46, 0.9);
  padding: 2.5rem;
  border-radius: 20px;
  border: 2px solid var(--gold-primary);
  box-shadow: 0 0 30px rgba(0,0,0,0.8), inset 0 0 20px rgba(46, 2, 73, 0.5);
}

.ball-content input, .ball-content textarea, .ball-content select {
  background: rgba(0, 0, 0, 0.6) !important;
  border: 1px solid var(--gold-primary) !important;
  color: var(--gold-primary) !important;
}

.ball-content input:focus, .ball-content textarea:focus, .ball-content select:focus {
  border-color: var(--gold-secondary) !important;
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.3) !important;
}

.ball-content .btn-magic button {
  width: auto !important;
  min-width: 240px;
  margin: 0 auto;
  display: block;
}

.ball-content .gr-text-input,
.ball-content .gr-dropdown {
  width: 92% !important;
  margin: 0 auto !important;
}

.ball-content {
  max-width: 420px !important;
  width: min(420px, 92vw) !important;
  margin: 0 auto !important;
  flex: 0 0 auto !important;
  align-self: center !important;
}

#ball-content {
  max-width: 420px !important;
  width: min(420px, 92vw) !important;
}
"""

def check_finish_animation(is_pending, deadline):
    if is_pending and time.time() > deadline:
        return (
            gr.update(visible=False),  # crystal ball
            gr.update(visible=True),  # chat
            False,  # animation pending
            0.0  # deadline
        )
    return (
        gr.update(),
        gr.update(),
        is_pending,
        deadline
    )


def _render_readout(label, value):
  safe_label = html.escape(label or "")
  safe_value = html.escape((value or "").strip())
  return (
    f'<div class="readout-box">'
    f'<div class="readout-label">{safe_label}</div>'
    f'<div class="readout-value">{safe_value}</div>'
    f'</div>'
  )


# on_begin_story not used but used in app.py and kept here for reference
def build_demo(*, on_user_message, on_begin_story, on_begin_story_checked, on_continue_story, on_rewind_story, on_menu_story) -> gr.Blocks:

    with gr.Blocks(fill_height=True) as demo:
        
        transition_pending = gr.State(False)
        transition_deadline = gr.State(0.0)
        transition_timer = gr.Timer(0.1, active=True)

        gr.HTML("""
        <div id="crystal-ball-bg">
        <lottie-player
            id="ball-lottie"
            src="/gradio_api/file=frontend/crystal-ball.json"
            background="transparent"
            speed="1"
            loop
            mode="normal">
        </lottie-player>
        </div>
        """, sanitize=False)
        
        thread_id_state = gr.State("")
        history_state = gr.State([])
        char_name_state = gr.State("")
        genre_state = gr.State("")
        image_style_state = gr.State("")

        ROLE_OPTIONS = {
          "fantasy": [
            ("Valiant Paladin 🛡️", "valiant_paladin"),
            ("Elven Ranger 🏹", "elven_ranger"),
            ("Arcane Scholar 🧙‍♂️", "arcane_scholar"),
            ("Shadow Thief 🗝️", "shadow_thief"),
            ("Circle Druid 🌿", "circle_druid"),
          ],
          "scifi": [
            ("Elite Netrunner 🖥️", "elite_netrunner"),
            ("Street Samurai ⚔️", "street_samurai"),
            ("Tech Specialist 🔧", "tech_specialist"),
            ("Social Face 🕶️", "social_face"),
            ("Heavy Solo 🦾", "heavy_solo"),
          ],
          "grimdark": [
            ("Plague Doctor 🎭", "plague_doctor"),
            ("Broken Knight ⚔️", "broken_knight"),
            ("Famine Scavenger 🎒", "famine_scavenger"),
            ("Penitent Zealot 🕯️", "penitent_zealot"),
            ("Grave Robber 🔦", "grave_robber"),
          ],
          "noir": [
            ("Hardboiled P.I. 🚬", "hardboiled_pi"),
            ("Femme Fatale 💋", "femme_fatale"),
            ("Dirty Cop 🚔", "dirty_cop"),
            ("Underground Informant 🐀", "underground_informant"),
            ("Forensic Analyst 🔍", "forensic_analyst"),
          ],
          "space_opera": [
            ("Starship Pilot 🚀", "starship_pilot"),
            ("Alien Emissary 👽", "alien_emissary"),
            ("Bounty Hunter 🔫", "bounty_hunter"),
            ("Naval Officer 🎖️", "naval_officer"),
            ("Psionic Adept 🔮", "psionic_adept"),
          ],
        }

        def _debug_print_genre(g):
          print(f"[debug] genre={g!r}")

        def _on_genre_change(g):
          choices = ROLE_OPTIONS.get((g or "").strip(), [])
          if not choices:
            return (
              gr.update(choices=[("Choose your Path first", "__NEED_PATH__")], value=None),
              gr.update(value=""),
            )
          return (
            gr.update(choices=choices, value=None),
            gr.update(value=""),
          )

        def _on_role_change(r, g):
          if not (g or "").strip() or r == "__NEED_PATH__":
            return (
              gr.update(value=None),
              gr.update(value='<div style="color: #ffffff;">Choose your Path first.</div>'),
            )
          return (
            gr.update(),
            gr.update(value=""),
          )


        title_screen = gr.Group(visible=True, elem_id="title-screen")
        with title_screen:
            with gr.Group(elem_classes=["screen-inner"]):
                gr.Image(
                    value="frontend/title.png",
                    show_label=False,
                    interactive=False,
                    container=False,
                )
                start_btn = gr.Button("Start Your Adventure!", elem_classes=["btn-magic"])


        crystal_ball_screen = gr.Group(visible=False, elem_id="crystal-screen")
        with crystal_ball_screen:
          with gr.Group(elem_classes=["screen-inner"]):
            begin_btn = gr.Button("Begin Your Story", elem_classes=["btn-magic"])
            begin_warning = gr.HTML(value="", elem_id="begin-warning")

            with gr.Row(equal_height=True):
              with gr.Column(scale=4, min_width=360):
                with gr.Group(elem_id="ball-content", elem_classes=["ball-content"]):
                  char_name = gr.Textbox(
                    label="What is your name?",
                    placeholder="Enter your character's name...",
                  )
                  genre = gr.Dropdown(
                    label="Choose your Path",
                    choices=[
                      ("High-Fantasy Quest ⚔️🐉", "fantasy"),
                      ("Cyberpunk Heist 🤖🏙️", "scifi"),
                      ("Grimdark Survival 💀🏚️", "grimdark"),
                      ("Noir Detective 🕵️‍♂️🔦", "noir"),
                      ("Cosmic Space Opera 🌌🛸", "space_opera"),
                    ],
                    value=None,
                    elem_id="genre-dd",
                  )
                  genre.change(fn=_debug_print_genre, inputs=genre, outputs=None, queue=False)

              with gr.Column(scale=4, min_width=440):
                gr.HTML(
                  value='<div class="crystal-gap-inner"></div>',
                  elem_id="crystal-gap",
                )

              with gr.Column(scale=4, min_width=360):
                with gr.Group(elem_id="role-content", elem_classes=["ball-content"]):
                  role = gr.Dropdown(
                    label="Choose your role",
                    choices=[("Choose your Path first", "__NEED_PATH__")],
                    value=None,
                    elem_id="role-dd",
                  )
                  role_hint = gr.HTML(value="")

                  image_style = gr.Dropdown(
                    label="Choose your image style",
                    choices=[
                      ("placeholder 1", "placeholder_1"),
                      ("placeholder 2", "placeholder_2"),
                      ("placeholder 3", "placeholder_3"),
                    ],
                    value=None,
                    elem_id="image-style-dd",
                  )
                  image_style.change(
                    fn=lambda s: (s or ""),
                    inputs=image_style,
                    outputs=image_style_state,
                    queue=False,
                  )

                  genre.change(
                    fn=_on_genre_change,
                    inputs=genre,
                    outputs=[role, role_hint],
                    queue=False,
                  )
                  role.change(
                    fn=_on_role_change,
                    inputs=[role, genre],
                    outputs=[role, role_hint],
                    queue=False,
                  )


        chat_screen = gr.Group(visible=False, elem_id="chat-screen")
        with chat_screen:
            gr.Markdown(
                """
<div align="center">

# Fable✨Friend
#### Your own AI story🔮

</div>
"""
            )
            gr.HTML(
                '<div align="center"><img src="/gradio_api/file=frontend/icon.png" width="120" height="120" /></div>'
            )

            with gr.Accordion("Story Settings ⚙️: ", open=False):
              char_readout = gr.HTML(
                value=_render_readout("Character: ", "Unknown Hero"),
              )
              genre_readout = gr.HTML(
                value=_render_readout("Genre: ", ""),
              )

            chatbot = gr.Chatbot(
                elem_id="chatbot",
                show_label=False,
                height=None,
                placeholder="Your story begins...",
                layout="bubble",
                like_user_message=True,
                avatar_images=(None, "frontend/avatar.png"),
            )
            textbox = gr.Textbox(
                label="Your action",
                placeholder="What do you do? Type here...",
                show_label=False,
            )

            REWIND_KEY = "__REWIND__"
            MENU_KEY = "__MENU__"

            def _submit_message(user_message, history, thread_id):
                (
                    box,
                    new_history,
                    new_thread_id,
                    title_u,
                    crystal_u,
                    chat_u,
                    pending,
                    deadline,
                    _images,
                ) = on_user_message(user_message, history, thread_id)

                return (
                    box,
                    new_history,
                    new_history,
                    new_thread_id,
                    title_u,
                    crystal_u,
                    chat_u,
                    pending,
                    deadline,
                )

            def _rewind_click(history, thread_id):
                return _submit_message(REWIND_KEY, history, thread_id)

            def _menu_click(history, thread_id):
                out = _submit_message(MENU_KEY, history, thread_id)
                # Clear readouts when returning to menu.
                return (*out, _render_readout("Character", "Unknown Hero"), _render_readout("Genre", ""))

            def _continue_click(history, thread_id):
                new_history, new_thread_id, _images = on_continue_story(history, thread_id)
                return new_history, new_history, new_thread_id

            textbox.submit(
                fn=_submit_message,
                inputs=[textbox, history_state, thread_id_state],
                outputs=[
                    textbox,
                    chatbot,
                    history_state,
                    thread_id_state,
                    title_screen,
                    crystal_ball_screen,
                    chat_screen,
                    transition_pending,
                    transition_deadline,
                ],
            )

            with gr.Row(equal_height=True):
                continue_btn = gr.Button("Continue", scale=2, min_width=160)
                rewind_btn = gr.Button("Rewind", scale=1, min_width=140)
                menu_btn = gr.Button("Menu", scale=1, min_width=120)

            continue_btn.click(
                fn=_continue_click,
                inputs=[history_state, thread_id_state],
                outputs=[chatbot, history_state, thread_id_state],
            )

            rewind_btn.click(
                fn=_rewind_click,
                inputs=[history_state, thread_id_state],
                outputs=[
                    textbox,
                    chatbot,
                    history_state,
                    thread_id_state,
                    title_screen,
                    crystal_ball_screen,
                    chat_screen,
                    transition_pending,
                    transition_deadline,
                ],
            )

            menu_btn.click(
                fn=_menu_click,
                inputs=[history_state, thread_id_state],
                outputs=[
                    textbox,
                    chatbot,
                    history_state,
                    thread_id_state,
                    title_screen,
                    crystal_ball_screen,
                    chat_screen,
                    transition_pending,
                    transition_deadline,
                    char_readout,
                    genre_readout,
                ],
            )

        transition_timer.tick(
            fn=check_finish_animation,
            inputs=[transition_pending, transition_deadline],
            outputs=[crystal_ball_screen, chat_screen, transition_pending, transition_deadline],
            queue=False
        )

        start_btn.click(
            fn=lambda: (gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=False)),
            inputs=[],
            outputs=[title_screen, crystal_ball_screen, chat_screen],
            js="""
            () => {
                const bg = document.getElementById("crystal-ball-bg");
                if (bg) {
                    bg.classList.add("active");     // show background on crystal screen
                    bg.classList.remove("blurred"); // just in case CAN ADDDD BLURRRRED
                    bg.classList.remove("zoomed-in");
                }
            }
            """
        )

        begin_btn.click(
            fn=None,
            js="""
              () => {
              const warn = document.getElementById("begin-warning");
              const genreRoot = document.getElementById("genre-dd");
              const roleRoot = document.getElementById("role-dd");
              const genreVal = (genreRoot?.querySelector("input") || genreRoot?.querySelector("select"))?.value;
              const roleVal = (roleRoot?.querySelector("input") || roleRoot?.querySelector("select"))?.value;
              if (!genreVal || !roleVal) {
                if (warn) warn.innerHTML = `<div style="color: #ffffff; font-weight: 700;">Finish your adventure's details!</div>`;
                return;
              }

              const bg = document.getElementById("crystal-ball-bg");
              const content = document.getElementById("ball-content");
              const player = document.getElementById("ball-lottie");

              if (bg) bg.classList.remove("blurred");

              // play the lottie
              if (player) player.play();

              setTimeout(() => { if (content) content.classList.add("fade-out"); }, 1500);
              setTimeout(() => { if (bg) bg.classList.add("zoomed-in"); }, 2000);

              // STOP the lottie and hide the whole background after the transition
              setTimeout(() => {
              if (player) {
                  // prevent re-looping and stop drawing frames
                  player.loop = false;
                  if (player.stop) player.stop();
                  else if (player.pause) player.pause();
              }
              if (bg) {
                  bg.classList.remove("active");
              }
              }, 3400);
              }
              """
        )

        def _begin_story_click(n, g, r, h, t):
          if not (g or "").strip() or not (r or "").strip() or r == "__NEED_PATH__":
            return (
              h,
              t,
              n,
              g,
              False,
              0.0,
              h,
              gr.update(),
              gr.update(),
              '<div style="color: #ffffff; font-weight: 700;">Finish your adventure\'s details!</div>',
            )

          out = on_begin_story_checked(n, g, r, h, t)
          new_history = out[0]
          new_thread_id = out[1]
          new_char_name = out[2]
          new_genre = out[3]
          pending = out[4]
          deadline = out[5]
          display_char_name = (new_char_name or "").strip() or "Unknown Hero"
          return (
              new_history,
              new_thread_id,
              new_char_name,
              new_genre,
              pending,
              deadline,
              new_history,
              _render_readout("Character", display_char_name),
              _render_readout("Genre", new_genre),
          "",
          )

        begin_btn.click(
            fn=_begin_story_click,
          inputs=[char_name, genre, role, history_state, thread_id_state],
          outputs=[history_state, thread_id_state, char_name_state, genre_state, transition_pending, transition_deadline, chatbot, char_readout, genre_readout, begin_warning],
        )

    return demo
