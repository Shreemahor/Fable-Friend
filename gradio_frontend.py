import gradio as gr

def build_demo(*, on_user_message, on_begin_story) -> gr.Blocks:

    with gr.Blocks() as demo:

        thread_id_state = gr.State("")
        history_state = gr.State([])
        char_name_state = gr.State("")
        genre_state = gr.State("")


        title_screen = gr.Group(visible=True)
        with title_screen:
            gr.Markdown("# Fable Friend")
            start_btn = gr.Button("Start Your Adventure!")


        crystal_ball_screen = gr.Group(visible=False)
        with crystal_ball_screen:
            char_name = gr.Textbox(label="Name your character")
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
            begin_btn = gr.Button("Begin Your Story")


        chat_screen = gr.Group(visible=False)
        with chat_screen:
            chat = gr.Chatbot()
            box = gr.Textbox(label="Your action", placeholder="What do you do? Type here...")


        start_btn.click(
            fn=lambda: (gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=False)),
            inputs=[],
            outputs=[title_screen, crystal_ball_screen, chat_screen],
        )

        begin_btn.click(
            fn=on_begin_story,
            inputs=[char_name, genre, history_state, thread_id_state],
            outputs=[history_state, thread_id_state, char_name_state, genre_state,
                     title_screen, crystal_ball_screen, chat_screen]
        )

        box.submit(
            fn=on_user_message,
            inputs=[box, history_state, thread_id_state],
            outputs=[box, history_state, thread_id_state]
        )

        history_state.change(fn=lambda h: h, inputs=[history_state], outputs=[chat])

    return demo
