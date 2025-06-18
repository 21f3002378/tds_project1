import base64
import json
import numpy as np
from typing import Optional, List
from fastapi import FastAPI
from pydantic import BaseModel
from PIL import Image
import io
import pytesseract
import requests
import os

app = FastAPI()

# Load precomputed chunks
with open("chunked_embeddings.json", "r", encoding="utf-8") as f:
    CHUNKS = json.load(f)

# AIPipe Embedding Endpoint
AIPIPE_TOKEN = os.getenv("AIPIPE_TOKEN")
AIPIPE_URL = "https://aipipe.org/openai/v1/embeddings"
HEADERS = {
    "Authorization": f"Bearer {AIPIPE_TOKEN}",
    "Content-Type": "application/json"
}

# --- Models ---
class QueryRequest(BaseModel):
    question: str
    image: Optional[str] = None

class ReferenceLink(BaseModel):
    url: str
    text: str

class QueryResponse(BaseModel):
    answer: str
    links: Optional[List[ReferenceLink]] = []

# --- Helper Functions ---
def extract_text_from_image(base64_str: str) -> str:
    try:
        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data))
        return pytesseract.image_to_string(image)
    except Exception as e:
        print("OCR failed:", e)
        return ""

def get_embedding(text: str, model="text-embedding-3-small"):
    response = requests.post(
        AIPIPE_URL,
        headers=HEADERS,
        json={"model": model, "input": text}
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]

def dot_product(vec1, vec2):
    return float(np.dot(np.array(vec1), np.array(vec2)))

def get_best_context(question_text: str) -> dict:
    question_emb = get_embedding(question_text)
    scored_chunks = [
        (dot_product(question_emb, chunk["embedding"]), chunk)
        for chunk in CHUNKS
    ]
    best_score, best_chunk = max(scored_chunks, key=lambda x: x[0])
    return best_chunk

def generate_answer(context_text: str, question: str) -> str:
    prompt = f"""You are an AI assistant. Use the context below to answer the user's question clearly.

### Context:
{context_text}

### Question:
{question}

Answer:"""

    completion = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
    )
    return completion.json()["choices"][0]["message"]["content"]

# --- API Endpoint ---
@app.post("/api/", response_model=QueryResponse)
async def handle_question(req: QueryRequest):
    image_text = extract_text_from_image(req.image) if req.image else ""
    combined_question = f"{req.question}\n\nImage Text:\n{image_text}" if image_text else req.question

    best_chunk = get_best_context(combined_question)
    answer = generate_answer(best_chunk["text"], req.question)

    return QueryResponse(
        answer=answer.strip(),
        links=[]  # Add if needed
    )
