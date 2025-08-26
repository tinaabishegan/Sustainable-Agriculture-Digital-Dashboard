# chatbot_api.py
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores.utils import filter_complex_metadata

# --- 1. SET UP YOUR ENVIRONMENT ---

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found. Please set it in your environment or a .env file.")

PERSIST_DIRECTORY = "chroma_db"

# --- 2. DEFINE THE PROMPT TEMPLATE ---

prompt_template = """
You are an AI assistant for answering questions about a set of documents.
You are given the following extracted parts of a long document and a question. Provide a conversational answer.
Use the context below to answer the question.
If you don't know the answer, just say "I'm sorry, I cannot find that information in the provided documents." Don't try to make up an answer.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""
PROMPT = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)

# --- 3. INITIALIZE THE RAG COMPONENTS (Global Instance) ---

print("Initializing RAG chain...")
try:
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    db = Chroma(
        persist_directory=PERSIST_DIRECTORY,
        embedding_function=embeddings
    )
    retriever = db.as_retriever(search_kwargs={"k": 3})
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    chain_type_kwargs = {"prompt": PROMPT}
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs=chain_type_kwargs,
        return_source_documents=True
    )
    print("RAG chain initialized successfully.")
except Exception as e:
    print(f"Error initializing RAG chain: {e}")
    qa_chain = None

# --- 4. CREATE THE FLASK API ---

app = Flask(__name__)

@app.route('/ask', methods=['POST'])
def ask_question():
    """
    API endpoint to receive a question and return an answer from the chatbot.
    """
    if not qa_chain:
        return jsonify({"error": "Chatbot is not ready."}), 503

    data = request.get_json()
    question = data.get("question")

    if not question:
        return jsonify({"error": "No question provided."}), 400

    try:
        result = qa_chain.invoke(question)
        answer = result["result"]
        source_docs = [
            {"source": doc.metadata.get('source', 'N/A'), "page": doc.metadata.get('page', 'N/A')}
            for doc in result["source_documents"]
        ]
        return jsonify({
            "answer": answer,
            "sources": source_docs
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Run the Flask app on localhost, port 5000
    app.run(debug=True, host='127.0.0.1', port=5000)
