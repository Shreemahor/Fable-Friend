import gradio as gr
import time


HEAD = """
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Fredoka:wght@400;600&family=Lato:wght@300;400&display=swap" rel="stylesheet">
<script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>

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

body, .gradio-container {
  background-color: var(--bg-dark) !important;
  color: #e9edf5 !important;
  font-family: 'Lato', sans-serif !important;
  overflow: hidden;
  height: 100vh;
}

// .gradio-container .wrap, .gradio-container .contain {
// //   background: transparent !important;
// }

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
  z-index: 0;
  pointer-events: none;

  opacity: 0;
  transition: opacity 0.35s ease, filter 1.5s ease;
}

#crystal-ball-bg {
  z-index: -10 !important;
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

#crystal-ball-bg lottie-player {
  width: 900px;
  height: 900px;
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

.ball-content {
  max-width: 420px;
  width: min(420px, 92vw);
  margin: 0 auto;
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


def build_demo(*, on_user_message, on_begin_story) -> gr.Blocks:

    with gr.Blocks(theme=gr.themes.Soft(
        primary_hue="purple",
        secondary_hue="yellow",
        neutral_hue="slate",
    )) as demo:
        
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
            with gr.Group(elem_id="ball-content", elem_classes=["ball-content"]):
                char_name = gr.Textbox(label="What is your name?", placeholder="Enter your character's name...")
                genre = gr.Dropdown(
                    label="Choose your Path",
                    choices=[
                        ("High Fantasy Adventure", "fantasy"),
                        ("Cyberpunk Mystery", "scifi"),
                        ("Eldritch Horror", "horror"),
                        ("Victorian Romance", "romance")
                    ],
                    value=None,
                )
                begin_btn = gr.Button("Begin Your Story", elem_classes=["btn-magic"])


        chat_screen = gr.Group(visible=False, elem_id="chat-screen")
        with chat_screen:
            chat = gr.Chatbot()
            box = gr.Textbox(label="Your action", placeholder="What do you do? Type here...")

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
            fn=on_begin_story,
            inputs=[char_name, genre, history_state, thread_id_state],
            outputs=[history_state, thread_id_state, char_name_state, genre_state,
                     transition_pending, transition_deadline],
            js="""
            () => {
            const bg = document.getElementById("crystal-ball-bg");
            const content = document.getElementById("ball-content");
            const player = document.getElementById("ball-lottie");

            // ensure unblurred when starting
            if (bg) bg.classList.remove("blurred");

            // play the lottie
            if (player) player.play();

            // match your index.html timing: play -> fade form -> zoom
            setTimeout(() => { if (content) content.classList.add("fade-out"); }, 1500);
            setTimeout(() => { if (bg) bg.classList.add("zoomed-in"); }, 2000);

            // STOP the lottie + hide the whole background after the transition
            setTimeout(() => {
            if (player) {
                // prevent re-looping and stop drawing frames
                player.loop = false;
                if (player.stop) player.stop();
                else if (player.pause) player.pause();
            }
            if (bg) {
                // hide the fixed background layer so it doesn't keep repainting
                bg.classList.remove("active");
            }
            }, 3400);
            }
            """
        )

        box.submit(
            fn=on_user_message,
            inputs=[box, history_state, thread_id_state],
            outputs=[box, history_state, thread_id_state]
        )

        history_state.change(fn=lambda h: h, inputs=[history_state], outputs=[chat])

    return demo
