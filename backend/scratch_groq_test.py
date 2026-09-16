import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from models import OpportunityEvaluations
from langchain_core.prompts import PromptTemplate

load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
print(f"Groq Key: {groq_key[:5]}...")
fallback_llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=groq_key, temperature=0.1)

structured_llm = fallback_llm.with_structured_output(OpportunityEvaluations)

prompt = PromptTemplate.from_template("Extract the jobs from this text: 'We are hiring a software engineer at Google for $150k. Remote.'")

try:
    result = structured_llm.invoke(prompt.to_messages())
    print("SUCCESS!")
    print(result)
except Exception as e:
    print(f"FAILED: {e}")
