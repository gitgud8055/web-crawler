import random
import string
import gradio as gr
import asyncio
import re

from RAG import rag_retrieval_qa
from lambda_stream.producer import publish_chat_event
from lambda_batch.producer import run_produce_async

answer_format = """🧠 Answer:
{}

⏳ URL:
{}

"""
temp_history = []

def crawler(http, depth, chatbot, userId): 
    print(f"HTTP: {http}\nDEPTH: {depth} of user_id: {userId}")
    try:
        urls = re.findall(r'\bhttps?://[^\s<>"]+|www\.[^\s<>"]+\b', http)
        asyncio.run(run_produce_async(urls, int(depth), userId))
        output = "Crawled from {}\n".format("\n".join(urls))
        chatbot.append({"role": "user", "content": ""})
        chatbot.append({"role": "assistant", "content": output})
    except Exception as e:
        print(f"Error: {e}")
    return chatbot

def get_answer(query, history, chatbot, userId, useServer):
    print(userId, useServer)
    output = ""
    # print(history)
    # crawler(http, depth)
    
    if len(query) != 0:
        answer, retrieved_chunks, retrieved_url = rag_retrieval_qa(query, history, "" if useServer else userId)
        publish_chat_event(query, answer)
        
        # output += answer_format.format(answer, "\n".join(retrieved_url), "\n".join(retrieved_chunks))
        chatbot.append({"role": "assistant", "content": "\n".join(retrieved_chunks), "metadata": {"title": "🛠️ EVIDENCE"}})
        chatbot.append({"role": "assistant", "content": answer_format.format(answer, "\n".join(retrieved_url))})
        temp_history = history
    else:
        # output += "Please ask something!"
        chatbot.append({"role": "assistant", "content": "Please ask something!"})
    # return  output
    return "", chatbot

def test(http, depth):
    print("HTTP: ", http)
    print("DEPTH: ", depth)

with gr.Blocks(fill_height=True) as demo:
    userId = gr.State("")
    with gr.Row():
        http = gr.Textbox(label="url to crawl", scale=10)
        button = gr.Button("Crawl", variant="primary")
    depth = gr.Textbox("1", label="depth")
    useServer = gr.Checkbox(label="Yes", info="Do you want to use all server's datas to improve your answer?")

    chatbot = gr.Chatbot(label="Chatbot",scale=1,type="messages")
    
    gr.ChatInterface(
        get_answer, 
        additional_inputs=[chatbot, userId, useServer], 
        type="messages",
        additional_outputs=[chatbot],
        chatbot=chatbot,
        concurrency_limit=None
    )
    # def shorten(L):
    #     return list(map(lambda x: {"role": x["role"], "content": x["content"][:10]}, L))
    @chatbot.retry(inputs=[chatbot, userId, useServer], outputs=[chatbot])
    def retry(chatbot, userId, useServer):
        while len(chatbot) > 0:
            last = chatbot[-1]
            if (last["role"] == "user"):
                yield chatbot
                _, chatbot = get_answer(last["content"], temp_history, chatbot, userId, useServer)
                break
            chatbot.pop()
        yield chatbot
        
    @demo.load(outputs=[userId])
    def genSession():
        generated = "".join(random.choices(string.ascii_letters + string.digits, k=15))
        print("User joined: ", generated)
        return generated
    button.click(crawler, inputs=[http, depth, chatbot, userId], outputs=chatbot, concurrency_limit=None)

demo.launch(share=True)