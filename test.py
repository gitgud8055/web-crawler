import gradio as gr
import asyncio

def async_process_prompt(prompt):
    asyncio.sleep(4) # async simulation
    return prompt

def process_prompt(prompt):
    for i in range(10 ** 8):
        a = 1
    return prompt
    # try:
    #     return await asyncio.wait_for(async_process_prompt(prompt), timeout=6)
    # except asyncio.TimeoutError:
    #     return "Processing timed out."

iface = gr.Interface(
    fn=process_prompt,
    inputs="text",
    outputs="text",
    title="Async Prompt Processor with Timeout",
    description="Enter a prompt to process asynchronously. Times out after 5 seconds.",
    concurrency_limit=None
)

iface.launch()