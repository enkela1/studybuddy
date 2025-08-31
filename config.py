"""
Configuration settings for Study Buddy application.
"""

# Supported file extensions for file_search/vector stores
SUPPORTED_EXTS = {
    "pdf", "txt", "md", "docx", "pptx", "csv", "json", "html",
    "py", "java", "rb", "tex", "c", "cpp"
}

# OpenAI model configuration
OPENAI_MODEL = "gpt-4-1106-preview"

# Timeout settings (in seconds)
QUIZ_GENERATION_TIMEOUT = 120
CHAT_RESPONSE_TIMEOUT = 120

# File size limits
MAX_FILE_SIZE_MB = 200

# Assistant instructions
ASSISTANT_INSTRUCTIONS = """You are a helpful study assistant. When the user asks to 'teach', 'summarize', or similar, 
respond immediately with a concise, well-structured summary of the uploaded document: 
- 5–8 bullet key points
- Main definitions/terms
- Any notable figures/examples. 
Use the file_search tool to ground answers in the uploaded document. Provide citations inline as [1], [2] when available. 
Only ask clarifying questions if the request is ambiguous or requires user preference. Be direct and avoid back-and-forth."""

# Quiz generation prompt
QUIZ_GENERATION_PROMPT = """Using the uploaded document(s) attached to this assistant via file_search, 
generate a multiple-choice quiz with 3 questions. For each question, provide 4 options 
and indicate the correct answer. Respond with STRICT JSON only in the format:
[
  {
    "question": "<question text>",
    "options": ["option1", "option2", "option3", "option4"],
    "correct": "<correct option>"
  }
]
Do not include any prose or code fences.""" 