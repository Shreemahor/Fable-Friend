# Fable-Friend
## Fable✨Friend: Your own AI story🔮
***An interactive AI story adventure with infinite possibilities, you choose what you do in your story, and AI decides what happens to your story next. With amazing genres, roles, images, and full gameplay, and more it’s your own journey.***

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
      ------------------------------------------------------------------------------------------------------------------------------------------------------------
     \/                                                                                                                                                          |
*Storyteller* uses state and knowledge to generate your story - different style and especially if you've just started or reached a milestone --->                |
*Image* uses another llm to look at state and generate a prompt for the image generator --->                                                                     |
*User* It's YOU! You can do something, continue, rewind, or go to the menu to start a new story --->                                                             |
*Judger Improver* To keep you and the other nodes in check - filling the other nodes in with details and making sure you can't get away with anything ------------

2. **Gradio** for the frontend by handling all the images, animations, buttons, dropdowns, accordian, chatinterface, displaying and supporting HTML, CSS, and JS.
It took lots of refinements to get such a robust interface with Gradio which typically supports only one page

## Requirements

Python 3.11 and pip install -r requirements.txt
**The main file to run is app.py**
