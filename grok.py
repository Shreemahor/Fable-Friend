from langchain_groq import ChatGroq
llm = ChatGroq(model="llama-3.1-8b-instant")
print(llm.invoke("what are jellyfish?").content)