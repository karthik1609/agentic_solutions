import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load env vars
load_dotenv()

DATA_PATH = r"validation_policies"
CHROMA_PATH = r"chroma_db"

# Load PDFs
loader = PyPDFDirectoryLoader(DATA_PATH)
raw_documents = loader.load()

# Split into chunks (~500 tokens each)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    length_function=len
)
chunks = text_splitter.split_documents(raw_documents)

# Initialize embeddings
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create or load a persistent vector store
vectorstore = Chroma(
    collection_name="validation_policy",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH
)

# Add documents to the vector store
vectorstore.add_documents(chunks)

print(f"✅ Added {len(chunks)} chunks to ChromaDB at {CHROMA_PATH}")