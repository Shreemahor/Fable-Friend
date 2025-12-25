import os
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated
from langgraph.graph import add_messages, StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core import ChatPromptTemplate

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

llm = ChatOpenAI(model="openrouter/auto",
                api_key=openrouter_api_key,
                base_url="https://openrouter.ai/api/v1"
)

memory = MemorySaver()

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful pirate. Chat with the user friendly but always respond like a pirate."),
    ("human", "{text}")
])
chain = prompt | llm

class BasicChatState(TypedDict): 
    messages: Annotated[list, add_messages]


def storyteller(state: BasicChatState): 
    return {
       "messages": [llm.invoke(state["messages"])]
    }

graph = StateGraph(BasicChatState)

graph.add_node("storyteller", storyteller)

graph.add_edge("storyteller", END)

graph.set_entry_point("storyteller")

app = graph.compile(checkpointer=memory)
print(app.get_graph().draw_ascii())

config = {"configurable": {
    "thread_id": 1
}}

while True: 
    user_input = input("You: ")
    if(user_input in ["exit", "end"]):
        break
    else: 
        result = app.invoke({
            "messages": [HumanMessage(content=user_input)]
        }, config=config)

        print("Fable Friend: " + result["messages"][-1].content)
