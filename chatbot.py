# Import libraries for the YouTube bot
import re
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from config import *                                           # All constants from config.py
from langchain_core.messages import HumanMessage, AIMessage

def get_video_id(url):    
    # Regex pattern to match YouTube video URLs
    patterns = [
        r'https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',
        r'https:\/\/youtu\.be\/([a-zA-Z0-9_-]{11})'  
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript(url):
    # Extracts the video ID from the URL
    video_id = get_video_id(url)
 
    # Create a YouTubeTranscriptApi() object
    ytt_api = YouTubeTranscriptApi()
   
    # Fetch the list of available transcripts for the given YouTube video
    transcripts = ytt_api.list(video_id)
   
    transcript = ""
    for t in transcripts:
        # Check if the transcript's language is English
        if t.language_code == 'en':
            if t.is_generated:
                # If no transcript has been set yet, use the auto-generated one
                if len(transcript) == 0:
                    transcript = t.fetch()
            else:
                # If a manually created transcript is found, use it (overrides auto-generated)
                transcript = t.fetch()
                break  # Prioritize the manually created transcript, exit the loop
   
    return transcript if transcript else None

def process(transcript):
    # Initialize an empty string to hold the formatted transcript
    txt = ""
   
    # Loop through each entry in the transcript
    for i in transcript:
        try:
            # Append the text and its start time to the output string
            #txt += f"Text: {i['text']} Start: {i['start']}\n"
            txt += f"Text: {i.text} Start: {i.start}\n"
        except KeyError:
            # If there is an issue accessing 'text' or 'start', skip this entry
            pass
           
    # Return the processed transcript as a single string
    return txt

def chunk_transcript(processed_transcript, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    # Initialize the RecursiveCharacterTextSplitter with specified chunk size and overlap
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
 
    # Split the transcript into chunks
    chunks = text_splitter.split_text(processed_transcript)
    return chunks

def create_faiss_index(chunks, embedding_model):
    """
    Create a FAISS index from text chunks using the specified embedding model.
   
    :param chunks: List of text chunks
    :param embedding_model: The embedding model to use
    :return: FAISS index
    """
    # Use the FAISS library to create an index from the provided text chunks
    return FAISS.from_texts(chunks, embedding_model)
 
def perform_similarity_search(faiss_index, query, k=TOP_K_RESULTS):
    """
    Search for specific queries within the embedded transcript using the FAISS index.
   
    :param faiss_index: The FAISS index containing embedded text chunks
    :param query: The text input for the similarity search
    :param k: The number of similar results to return (default is 3)
    :return: List of similar results
    """
    # Perform the similarity search using the FAISS index
    results = faiss_index.similarity_search(query, k=k)
    return results

def get_video_duration(transcript):
    """
    Extract video duration from the last timestamp in the transcript.
    
    :param transcript: List of transcript objects
    :return: Duration as a formatted string e.g. '19:32'
    """
    last = max(transcript, key=lambda x: x.start)
    total_seconds = int(last.start)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"

def build_vectorstore(transcript):
    text = process(transcript)
    chunks = chunk_transcript(text)
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL
    )
    faiss_index = create_faiss_index(chunks, embeddings)
    video_duration = get_video_duration(transcript)
    return faiss_index, video_duration

def create_summary_prompt():
    """
    Create a PromptTemplate for summarizing a YouTube video transcript.
   
    :return: PromptTemplate object
    """
    # Define the template for the summary prompt
    prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an AI assistant tasked with summarizing YouTube video transcripts. Provide concise, informative summaries that capture the main points of the video content.
     Instructions:
     1. Summarize the transcript in a single concise paragraph.
     2. Ignore any timestamps in your summary.
     3. Focus on the spoken content (Text) of the video."""),
    ("human", "Please summarize the following YouTube video transcript:\n\n{transcript}")
    ])
    return prompt
 
def create_summary_chain(llm, prompt_template):
    """
    Create an LLMChain for generating summaries.
   
    :param llm: Language model instance
    :param prompt: PromptTemplate instance
    :return: Runnable chain
    """
    return prompt_template | llm

def create_qa_prompt():
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert assistant providing detailed and accurate answers based on the following video content. Your responses should be:
1. Precise and free from repetition
2. Consistent with the information provided in the video
3. Well-organized and easy to understand
4. Focused on addressing the user's question directly

Timestamp instructions:
- The video duration is {video_duration} (minutes:seconds)
- When answering questions about the video content, mention the timestamp where the topic is discussed e.g. 'This is discussed at around 2:30 in the video'
- If the user asks 'when is X discussed?', find the relevant timestamp from the context and return it in minutes:seconds format
- If the user asks about the video duration, return {video_duration}

You also have access to the conversation history. Use it to answer follow-up questions and references to previous exchanges directly from memory — do NOT search the video context for questions about the conversation itself.

Note: In the transcript, \"Text\" refers to the spoken words in the video, and \"start\" indicates the timestamp when that part begins in the video."""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "Relevant Video Context: {context}\n\nVideo duration: {video_duration}\n\nBased on the above context and our conversation history, please answer the following question:\n{question}")
    ])
    return prompt

def create_qa_chain(llm, prompt_template):
    """
    Create an LLMChain for question answering.
 
    Args:
        llm: Language model instance
            The language model to use in the chain (e.g., WatsonxGranite).
        prompt_template: PromptTemplate
            The prompt template to use for structuring inputs to the language model.
        verbose: bool, optional (default=True)
            Whether to enable verbose output for the chain.
 
    Returns:
        LLMChain: An instantiated LLMChain ready for question answering.
    """
   
    return prompt_template | llm

def generate_answer(question, faiss_index, qa_chain, chat_history, video_duration, k=TOP_K_RESULTS):
    """
    Retrieve relevant context and generate an answer based on user input.

    :param question: The user's question
    :param faiss_index: FAISS index containing embedded documents
    :param qa_chain: The QA chain
    :param chat_history: List of previous messages for memory
    :param video_duration: Duration of the video as a formatted string
    :param k: Number of relevant documents to retrieve
    :return: The generated answer as a string
    """
    relevant_context = perform_similarity_search(faiss_index, question, k=k)

    response = qa_chain.invoke({
        "context": relevant_context,
        "question": question,
        "chat_history": chat_history[-MAX_HISTORY_TURNS * 2:],
        "video_duration": video_duration
    })

    return response




