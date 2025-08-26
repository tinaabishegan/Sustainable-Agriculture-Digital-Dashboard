import os
from dotenv import load_dotenv
import langchain
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.document_loaders import PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata

# --- 1. SET UP YOUR ENVIRONMENT ---

# Load environment variables from a .env file (recommended)
load_dotenv()

# Ensure your GOOGLE_API_KEY is set in your environment or a .env file
# You can get your key from Google AI Studio: https://aistudio.google.com/
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found. Please set it in your environment or a .env file.")

# --- 2. CONFIGURE DOCUMENT LOADING AND PROCESSING ---

# Specify the directory where your source documents are located
SOURCE_DOCUMENTS_DIR = "source_documents"

# Specify the directory to save the persistent ChromaDB database
PERSIST_DIRECTORY = "chroma_db"

# Configure the text splitter for chunking documents
# chunk_size: The maximum number of characters in a chunk.
# chunk_overlap: The number of characters to overlap between chunks to maintain context.
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

# --- 3. LOAD AND PROCESS THE DOCUMENTS ---

def load_documents(source_dir):
    """
    Loads all documents from the source directory, supporting .pdf, .docx, and .xlsx files.
    """
    all_docs = []
    print(f"Loading documents from: {source_dir}")

    if not os.path.exists(source_dir):
        print(f"Error: Directory '{source_dir}' not found.")
        return []

    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        try:
            if filename.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                docs = loader.load()
            elif filename.endswith(".docx"):
                loader = Docx2txtLoader(file_path)
                docs = loader.load()
            elif filename.endswith(".xlsx"):
                # Using UnstructuredExcelLoader for its robustness with various Excel formats
                loader = UnstructuredExcelLoader(file_path, mode="elements")
                docs = loader.load()
            else:
                print(f"Skipping unsupported file type: {filename}")
                continue

            print(f"-> Loaded {len(docs)} document(s) from {filename}")
            all_docs.extend(docs)
        except Exception as e:
            print(f"Error loading file {filename}: {e}")

    return all_docs

def main():
    """
    Main function to run the document processing and indexing pipeline.
    """
    # Load the documents from the source directory
    documents = load_documents(SOURCE_DOCUMENTS_DIR)

    if not documents:
        print("No documents were loaded. Please check your source directory and file formats.")
        return

    # Split the loaded documents into chunks
    print("\nSplitting documents into chunks...")
    texts = text_splitter.split_documents(documents)
    print(f"Split into {len(texts)} chunks.")
    
    # --- IMPORTANT FIX: Filter out complex metadata before adding to ChromaDB ---
    # This resolves the ValueError you encountered.
    texts = filter_complex_metadata(texts)

    # --- 4. CREATE EMBEDDINGS AND STORE IN VECTOR DATABASE ---

    # Initialize the Google Generative AI embedding model
    print("\nInitializing embedding model...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

    # Create or load the Chroma vector store
    # This will save the database to the PERSIST_DIRECTORY for reuse.
    print(f"\nCreating/loading vector store at: {PERSIST_DIRECTORY}")
    db = Chroma.from_documents(
        texts,
        embeddings,
        persist_directory=PERSIST_DIRECTORY
    )

    # Persist the database to disk
    db.persist()
    print("\n--- Processing Complete ---")
    print(f"The knowledge base has been created and saved to '{PERSIST_DIRECTORY}'.")
    print("You can now use this database in your chatbot application for retrieval.")


if __name__ == "__main__":
    main()
