import os
import json
from openai import OpenAI

def classify_text(text):

    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

    prompt = f"""
You are an academic classifier.

Extract:
- subject_code
- semester
- unit

Return JSON only.

Text:
{text}
"""

    response = client.chat.completions.create(
        model="arcee-ai/trinity-large-preview:free",  # FREE MODEL
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    output = response.choices[0].message.content.strip()

    # Clean markdown JSON if model wraps it
    output = output.replace("```json", "").replace("```", "").strip()

    return json.loads(output)