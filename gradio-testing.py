import gradio as gr
gr.load_chat("http://localhost:11434/v1/", model="smollm2:135m", token="***").launch(share=True)