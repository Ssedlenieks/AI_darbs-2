import os
import os
import requests
from dotenv import load_dotenv
from openai import OpenAI


class ChatbotService:
    def __init__(self):
        # 1. SOLIS - API atslēgas ielāde
        load_dotenv()
        # Expect user to set HUGGINGFACE_API_KEY in .env
        self.hf_api_key = os.getenv('HUGGINGFACE_API_KEY') or os.getenv('HF_API_KEY')

        # 2. SOLIS - OpenAI klienta inicializācija izmantojot "katanemo/Arch-Router-1.5B" modeli
        # We attempt to use the OpenAI-compatible client first (some HF setups provide OpenAI-compatible endpoints).
        self.client = None
        self.openai_api_base = os.getenv('OPENAI_API_BASE')
        try:
            if self.openai_api_base and self.hf_api_key:
                # Initialize OpenAI client pointing to a custom base (optional)
                self.client = OpenAI(api_key=self.hf_api_key, api_base=self.openai_api_base)
        except Exception:
            # If OpenAI client initialization fails, we'll fallback to direct HF HTTP calls.
            self.client = None

        # Model to use on Hugging Face
        self.model = "katanemo/Arch-Router-1.5B"

        # 3. SOLIS - Sistēmas instrukcijas definēšana
        # Keep the assistant focused on e-shop related questions and products.
        self.system_instruction = (
            "You are an e-shop assistant for My E-Shop. Answer user questions concisely and only using information"
            " about the store, its products, prices and stock. If the user asks for something not related to the store,"
            " politely decline and offer to help with store-related information. When needed, refer to the product list"
            " provided by the server. Keep answers short (max 200 tokens) and avoid speculative or unsafe content."
        )

    def _build_prompt(self, user_message, chat_history, extra_products_text=None):
        # Flatten messages into a plain-text prompt for HF text-generation models.
        prompt_parts = [f"SYSTEM: {self.system_instruction}"]
        if extra_products_text:
            prompt_parts.append(f"PRODUCTS:\n{extra_products_text}")

        # Add conversation history
        for msg in chat_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt_parts.append(f"{role.upper()}: {content}")

        # Add latest user message
        prompt_parts.append(f"USER: {user_message}")

        # Final assistant marker
        prompt_parts.append("ASSISTANT:")
        return "\n\n".join(prompt_parts)

    def get_chatbot_response(self, user_message, chat_history=None, extra_products_text=None):
        if chat_history is None:
            chat_history = []

        # Build a single prompt combining system instruction, optional product list, history and user message
        prompt = self._build_prompt(user_message, chat_history, extra_products_text=extra_products_text)

        # First try to use OpenAI-compatible client if configured
        if self.client is not None:
            try:
                messages = [
                    {"role": "system", "content": self.system_instruction},
                ]
                # extend with chat_history expecting objects like {role, content}
                messages.extend(chat_history)
                messages.append({"role": "user", "content": user_message})

                resp = self.client.chat.completions.create(model=self.model, messages=messages, max_tokens=200)
                # OpenAI-compatible response parsing
                choices = getattr(resp, 'choices', None) or resp.get('choices')
                if choices and len(choices) > 0:
                    text = choices[0].get('message', {}).get('content') if isinstance(choices[0], dict) else None
                    if not text:
                        # Try alternative shape
                        text = choices[0].get('text') if isinstance(choices[0], dict) else None
                    return {"response": text or ""}
            except Exception as e:
                # If this fails, fallback to direct HTTP call to HF Inference API
                print(f"OpenAI-compatible client failed, falling back to HF HTTP. Error: {e}")

        # Fallback: use direct Hugging Face Inference API via HTTP
        if not self.hf_api_key:
            return {"response": "Hugging Face API key not configured."}

        hf_url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {"Authorization": f"Bearer {self.hf_api_key}", "Content-Type": "application/json"}
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 200, "temperature": 0.2},
        }

        try:
            r = requests.post(hf_url, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            # Data can be a list or dict depending on the HF endpoint
            if isinstance(data, list) and len(data) > 0:
                generated = data[0].get('generated_text') or data[0].get('generated_texts') or ''
            elif isinstance(data, dict):
                generated = data.get('generated_text') or data.get('generated_texts') or ''
            else:
                generated = ''

            # Attempt to trim assistant label if present
            if isinstance(generated, list):
                generated = generated[0]
            # Remove the prompt from the generated text if it was echoed
            if isinstance(generated, str) and prompt in generated:
                generated = generated.split(prompt, 1)[-1].strip()

            return {"response": generated}
        except Exception as e:
            print(f"HF inference request failed: {e}")
            return {"response": "An error occurred when contacting the AI service."}
