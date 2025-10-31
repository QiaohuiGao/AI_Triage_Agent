from dotenv import load_dotenv; load_dotenv()
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER","bedrock")
AWS_REGION = os.getenv("AWS_REGION","us-west-2")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT","")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY","")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT","")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY","")
PINECONE_ENV = os.getenv("PINECONE_ENV","us-east-1")
PINECONE_SYMPTOM_INDEX = os.getenv("PINECONE_SYMPTOM_INDEX","symptom-index")
PINECONE_CONDITION_INDEX = os.getenv("PINECONE_CONDITION_INDEX","condition-index")
PINECONE_CAREPATH_INDEX = os.getenv("PINECONE_CAREPATH_INDEX","carepath-index")
POSTGRES_URL = os.getenv("POSTGRES_URL","postgresql+psycopg2://user:pass@localhost:5432/triage")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY","")
PORT = int(os.getenv("PORT","8080"))
VOTE_PASSES = 3
AGREEMENT_MIN = 0.55
CONFIDENCE_MIN = 0.55
RED_FLAG_TERMS = {"chest pain","shortness of breath","one-sided weakness","slurred speech"}
