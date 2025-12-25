import os
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated
from langgraph.graph import add_messages, StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate


openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
llm = ChatOpenAI(model="allenai/olmo-3.1-32b-think:free",
                api_key=openrouter_api_key,
                base_url="https://openrouter.ai/api/v1"
)

memory = MemorySaver()

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a fantasy game dungeon master. You will guide the user through an interactive story where they make choices that affect the outcome of the adventure." \
    "Describe scenes vividly and present the user with clear choices at each step. Keep the story engaging and immersive."),
    ("human", "{text}")
])
chain = prompt | llm

initial_situation = llm.invoke("You are a fantasy storyteller. Create an interesting and engaging opening situation for a new story." \
"It should force the user to make a choice in the start of their adventure.").content
print(initial_situation)

class BasicChatState(TypedDict): 
    messages: Annotated[list, add_messages]
    situation: str


def storyteller(state: BasicChatState): 
    return {
       "messages": [chain.invoke(state["messages"])]
    }


graph = StateGraph(BasicChatState)

graph.set_entry_point("storyteller")

#graph.add_node("situation")

graph.add_node("storyteller", storyteller)

graph.add_edge("storyteller", END)

app = graph.compile(checkpointer=memory)
print(app.get_graph().draw_ascii())

config = {"configurable": {
    "thread_id": 1
}}

if __name__ == "__main__": 
    while True: 
        user_input = input("You: ")
        if(user_input in ["exit", "end", "quit", "bye"]):
            break
        else: 
            result = app.invoke({
                "messages": [HumanMessage(content=user_input)]
            }, config=config)

            print("Fable Friend: " + result["messages"][-1].content)
