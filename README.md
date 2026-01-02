# Fable-Friend
https://huggingface.co/spaces/Shreemahor/Fable-Friend
## Fable✨Friend: Your own AI story🔮
***An interactive AI story adventure with infinite possibilities, you choose what you do in your story, and AI decides what happens to your story next. With amazing genres, roles, images, and full gameplay, and more it’s your own journey.***
![final-shortest](https://github.com/user-attachments/assets/247b44ed-1f46-40a2-bbc6-2d829877ad95)
<img width="1704" height="904" alt="storm" src="https://github.com/user-attachments/assets/5a98aad7-8054-4186-84fc-12a0265201e5" />
<img width="1437" height="901" alt="samurai" src="https://github.com/user-attachments/assets/b81829c5-60c1-416c-ad76-0d2b747ebc35" />

## What are it's feautures?

- Your story is *AI Powered* Do anything you want! it's your journey and AI is the dungeonmaster
- You can pick your own genre from high fantasy to space adventures
- You can pick your own role 5 in each genre
- There is **IMAGE GENERATION** to really make your story come alive
- With a continue button to just let the story unfold and a rewind to do something different
- If you make bad choices it's GAME OVER, but if you know what your doing eventually you'll reach a milestone and enter a new chapter of the story!

## How Does it Work?

1. **Langchain and Langgraph** power the logic by storing all of your story settings and more - genre, role, name, progress, last action, world, tension, summaries, and lots more in state so the storytelling llm knows what its doing:

The *main loop* is


*Storyteller* uses state and knowledge to generate your story - different style and especially if you've just started or reached a milestone --->                

*Image* uses another llm to look at state and generate a prompt for the image generator --->                                                                     

*User* It's YOU! You can do something, continue, rewind, or go to the menu to start a new story --->                                                             

*Judger Improver* To keep you and the other nodes in check - filling the other nodes in with details and making sure you can't get away with anything --------------> all the way back to Storyteller and so on


Notes: Two models are used - gptoss-120b and llama-3.1-8b

2. **Gradio** for the frontend by handling all the images, animations, buttons, dropdowns, accordian, chatinterface, displaying and supporting HTML, CSS, and JS.
It took lots of refinements to get such a robust interface with Gradio which typically supports only one page

## Requirements

Python 3.11 and pip install -r requirements.txt
**The main file to run is app.py**

There are many environment variables but the main ones are:
+ GROQ_API_KEY - your groq cloud api key for the main story creating text llms
+ HF_TOKEN - primary image provider your hugging face token for image generation using FLUX1-schnell
+ POLLINATIONS_API_KEY - secondary image provider (alternative to hugging face) your pollinations api key using turbo (or zimage if you prefer)

## Hugging Face Spaces

The API keys are set in my space's secrets.
Images are stored in runtime_images and they get cleaned once RUNTIME_IMAGES_MAX_FILES is reached, because there is only so much space available. Currently I have the image max at 50.
Just type "python app.py" and Fable Friend will get going!

## Structure

There are three main files:
**app.py**: main execution file that has all the Langchain and Langgraph logic and the app entry point
**gradio_frontend.py**: file that has all frontend elements with Gradio and includes CSS, HTML and JS parts and uses the UI, seperated from app.py to ensure the backend and frontend stay seperate
**file_of_prompts.py**: file that is just a list of the longer prompts for the llm to ensure that app.py is not cluttered with lots of long prompts

There is the /frontend folder that has ui elements like the crystal ball animation, a test image, and avatar for Fable Friend, an icon, and a title picture.

## Limitations & Future

Hugging Face offers better image generation but Pollinations.ai is a cheaper option. The image style and general image consistency depends on the model and its adherance to the prompt.
A bigger llm than gpt-oss-120b could possibly improve the storytelling. In the future, streaming the storyteller's response, a bigger and better image style set would be nice. It would be interesting to see how a more game based system with chapters, additional hp, or combat would work with AI. Maybe one day, users can save their story.

## Credits

Thank you to Gradio, Langchain & Langgraph, models from Groq Cloud, Hugging Face, Pollinations.ai!

## More Samples of it in Action 🔮 ✨

<img width="1885" height="937" alt="image" src="https://github.com/user-attachments/assets/a35598c9-c2df-4001-8f86-f70c4e2080de" />
<img width="1880" height="894" alt="scififinal" src="https://github.com/user-attachments/assets/8bd91e6d-931e-4588-bf26-a85e30e24c7e" />
