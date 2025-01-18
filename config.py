from dotenv import load_dotenv
import os

load_dotenv()

OPEN_API_KEY=os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")