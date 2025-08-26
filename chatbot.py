import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
# Updated Chroma import to follow the latest best practices
from langchain_community.vectorstores import Chroma 
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# --- 1. SET UP YOUR ENVIRONMENT ---

# Load environment variables from a .env file
load_dotenv()

# Ensure your GOOGLE_API_KEY is set
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found. Please set it in your environment or a .env file.")

# Specify the directory of the persistent ChromaDB database
PERSIST_DIRECTORY = "chroma_db"

# --- 2. DEFINE THE PROMPT TEMPLATE ---

# This template is crucial for instructing the LLM on how to behave.
# It tells the model to answer based *only* on the provided context.
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

# --- 3. INITIALIZE THE RAG COMPONENTS ---

def get_rag_chain():
    """
    Initializes and returns a RetrievalQA chain.
    """
    # Initialize the embedding model
    print("Initializing embedding model...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

    # Load the persistent vector store
    print(f"Loading vector store from: {PERSIST_DIRECTORY}")
    if not os.path.exists(PERSIST_DIRECTORY):
        raise FileNotFoundError(
            f"The directory '{PERSIST_DIRECTORY}' does not exist. "
            "Please run the 'process_documents.py' script first to create the database."
        )
    
    db = Chroma(
        persist_directory=PERSIST_DIRECTORY, 
        embedding_function=embeddings
    )

    # Create the retriever
    # 'k=3' means it will retrieve the top 3 most relevant chunks.
    retriever = db.as_retriever(search_kwargs={"k": 3})
    print("Retriever created.")

    # Initialize the LLM for generation
    print("Initializing LLM...")
    # FIX: Changed model name from "gemini-pro" to the correct "gemini-1.0-pro"
    # and removed a deprecated parameter.
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

    # Create the RetrievalQA chain
    # This chain combines the retriever and the LLM with the custom prompt.
    chain_type_kwargs = {"prompt": PROMPT}
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs=chain_type_kwargs,
        return_source_documents=True # This allows us to see which chunks were used
    )
    
    print("RAG chain created successfully.")
    return qa_chain

# --- 4. CREATE THE INTERACTIVE CHAT LOOP ---

def main():
    """
    Main function to run the interactive chatbot.
    """
    try:
        qa = get_rag_chain()
        print("\n--- Chatbot is Ready ---")
        print("Ask a question about your documents. Type 'exit' to quit.")

        while True:
            # Use invoke instead of the deprecated __call__ method
            query = input("\nYour Question: ")
            if query.lower() == 'exit':
                print("Exiting chatbot. Goodbye!")
                break
            
            if query.strip() == "":
                continue

            # Process the query through the RAG chain
            print("\nThinking...")
            result = qa.invoke(query) # Use .invoke() for the latest LangChain version
            
            # Print the answer
            print("\nAnswer:")
            print(result["result"])
            
            # (Optional) Print the source documents that were retrieved
            print("\n--- Sources ---")
            for doc in result["source_documents"]:
                print(f"Source: {doc.metadata.get('source', 'Unknown')}, Page: {doc.metadata.get('page', 'N/A')}")
                # print(f"Content: {doc.page_content[:200]}...") # Uncomment to see content snippets
            print("---------------")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()