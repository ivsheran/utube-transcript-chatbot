import gradio as gr
from langchain_ollama import OllamaLLM
from langchain_core.messages import HumanMessage, AIMessage
from chatbot import (
    get_transcript,
    build_vectorstore,
    create_summary_prompt,
    create_summary_chain,
    create_qa_prompt,
    create_qa_chain,
    generate_answer,
    get_full_transcript
)
from drive import save_transcript_to_drive
from config import AVAILABLE_MODELS, DEFAULT_MODEL, OLLAMA_BASE_URL

# --- Global state ---
faiss_index = None
qa_chain = None
summary_chain = None
chat_history = []
video_duration = None
current_url = None

def ash_says(text):
    return f"🐾 **Ash:** {text}"

ASH_GREETING = ash_says("Hi! I'm Ash 🐾 Load a video and I'll answer any questions about it!")

def load_video(url, model_name):
    global faiss_index, qa_chain, summary_chain, chat_history, video_duration, current_url

    if not url.strip():
        return "⚠️ Please insert a YouTube link.", [{"role": "assistant", "content": ASH_GREETING}]

    try:
        transcript = get_transcript(url)
        if transcript is None:
            return "❌ No English transcript found for this video.", [{"role": "assistant", "content": ASH_GREETING}]

        faiss_index, video_duration = build_vectorstore(transcript)

        llm = OllamaLLM(model=model_name, base_url=OLLAMA_BASE_URL)
        qa_chain = create_qa_chain(llm, create_qa_prompt())
        summary_chain = create_summary_chain(llm, create_summary_prompt())

        chat_history = []
        current_url = url

        return "✅ Video loaded! Ask Ash anything about it.", [{"role": "assistant", "content": ASH_GREETING}]

    except Exception as e:
        return f"❌ Error: {str(e)}", [{"role": "assistant", "content": ASH_GREETING}]

def ask_question(question, history):
    global faiss_index, qa_chain, chat_history, video_duration

    if not question.strip():
        return history, ""

    if faiss_index is None or qa_chain is None:
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": ash_says("⚠️ Please load a YouTube video first.")})
        return history, ""

    try:
        answer = generate_answer(question, faiss_index, qa_chain, chat_history, video_duration)

        chat_history.append(HumanMessage(content=question))
        chat_history.append(AIMessage(content=answer))

        from config import MAX_HISTORY_TURNS
        if len(chat_history) > MAX_HISTORY_TURNS * 2:
            chat_history = chat_history[-MAX_HISTORY_TURNS * 2:]

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": ash_says(answer)})
        return history, ""

    except Exception as e:
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": ash_says(f"❌ Error: {str(e)}")})
        return history, ""

def clear_chat():
    global chat_history
    chat_history = []
    return [{"role": "assistant", "content": ASH_GREETING}], ""

def new_video():
    global faiss_index, qa_chain, summary_chain, chat_history, video_duration
    faiss_index = None
    qa_chain = None
    summary_chain = None
    chat_history = []
    video_duration = None
    return "", "🔄 Ready for a new video.", [{"role": "assistant", "content": ASH_GREETING}], ""

def save_transcript():
    global current_url
    if current_url is None:
        return "⚠️ Please load a YouTube video first."
    try:
        transcript_text = get_full_transcript(current_url)
        link = save_transcript_to_drive(transcript_text, current_url)
        return f"✅ Transcript saved to Google Drive: {link}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- Gradio UI ---
with gr.Blocks(title="YouTube Chatbot") as demo:
    gr.Markdown("# 🎬 YouTube Chatbot")
    gr.Markdown("Transcribes, summarises and answers questions about any YouTube video.")

    with gr.Row():
        url_input = gr.Textbox(
            label="Insert your YouTube link",
            placeholder="https://www.youtube.com/watch?v=...",
            scale=4
        )
        model_dropdown = gr.Dropdown(
            choices=AVAILABLE_MODELS,
            value=DEFAULT_MODEL,
            label="Model",
            scale=1
        )

    load_btn = gr.Button("Load Video", variant="primary")
    status = gr.Textbox(label="Status", interactive=False)

    save_btn = gr.Button("💾 Save Transcript to Drive")
    drive_status = gr.Textbox(label="Drive Status", interactive=False)

    chatbot = gr.Chatbot(
        label="Ash 🐾",
        value=[{"role": "assistant", "content": ASH_GREETING}],
        height=400
    )

    question_input = gr.Textbox(
        label="Ask your question on a video",
        placeholder="Type your question here..."
    )

    with gr.Row():
        ask_btn = gr.Button("Ask", variant="primary")
        clear_btn = gr.Button("Clear Chat")
        new_video_btn = gr.Button("New Video")

    # --- Event handlers ---
    load_btn.click(
        load_video,
        inputs=[url_input, model_dropdown],
        outputs=[status, chatbot]
    )
    ask_btn.click(
        ask_question,
        inputs=[question_input, chatbot],
        outputs=[chatbot, question_input]
    )
    question_input.submit(
        ask_question,
        inputs=[question_input, chatbot],
        outputs=[chatbot, question_input]
    )
    clear_btn.click(
        clear_chat,
        outputs=[chatbot, question_input]
    )
    new_video_btn.click(
        new_video,
        outputs=[url_input, status, chatbot, question_input]
    )

    save_btn.click(
        save_transcript,
        inputs=[],
        outputs=drive_status
        )

if __name__ == "__main__":
    demo.launch(share=True)


 #https://www.youtube.com/watch?v=WSPChlfxJyA for testing   