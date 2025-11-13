import os
import requests
from dotenv import load_dotenv
import openai


class ChatbotService:
    def __init__(self):
        # 1. SOLIS - API atslēgas ielāde
        load_dotenv()
        # Expect user to set HUGGINGFACE_API_KEY in .env
        raw_key = os.getenv('HUGGINGFACE_API_KEY') or os.getenv('HF_API_KEY')
        # strip accidental whitespace/newlines
        self.hf_api_key = raw_key.strip() if isinstance(raw_key, str) else raw_key

        # 2. SOLIS - OpenAI-compatible client: not initialized here. We'll use OpenAI package as a fallback if
        # OPENAI_API_KEY is set. For HF OpenAI-compatible bases, user can configure OPENAI_API_BASE and
        # OPENAI_API_KEY in .env and the OpenAI fallback will be attempted later.
        self.client = None

        # Model to use on Hugging Face — switch to a public, small model to ensure availability
        # Primary model (public): distilgpt2 — fallback models used if primary is unavailable
        self.model = "distilgpt2"
        self.fallback_models = ["gpt2"]

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

        # Try primary model first, then fallbacks
        models_to_try = [self.model] + self.fallback_models
        headers = {"Authorization": f"Bearer {self.hf_api_key}", "Content-Type": "application/json"}
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 200, "temperature": 0.2},
        }

        last_err = None
        for m in models_to_try:
            hf_url = f"https://api-inference.huggingface.co/models/{m}"
            try:
                r = requests.post(hf_url, headers=headers, json=payload, timeout=30)
                r.raise_for_status()
                data = r.json()
                # Data can be a list or dict depending on the HF endpoint
                if isinstance(data, list) and len(data) > 0:
                    generated = data[0].get('generated_text') or data[0].get('generated_texts') or ''
                elif isinstance(data, dict):
                    # Some models return {'generated_text': '...'} or {'generated_texts': ['...']}
                    generated = data.get('generated_text') or (data.get('generated_texts') and data.get('generated_texts')[0]) or ''
                else:
                    generated = ''

                if isinstance(generated, list):
                    generated = generated[0]
                if isinstance(generated, str) and prompt in generated:
                    generated = generated.split(prompt, 1)[-1].strip()

                return {"response": generated, "model_used": m}
            except requests.HTTPError as he:
                last_err = he
                # If model is not available (e.g., 410 Gone), try next fallback
                print(f"HF inference request for model {m} failed: {he}")
                continue
            except Exception as e:
                last_err = e
                print(f"HF inference request failed for model {m}: {e}")
                continue

        # If we get here, all models failed
        print(f"All HF model requests failed, last error: {last_err}")
        # Try OpenAI API as a fallback if configured
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            try:
                openai.api_key = openai_key
                messages = [
                    {"role": "system", "content": self.system_instruction},
                ]
                messages.extend(chat_history)
                messages.append({"role": "user", "content": user_message})

                resp = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages, max_tokens=200)
                if resp and resp.choices:
                    text = resp.choices[0].message.get('content') if hasattr(resp.choices[0], 'message') else resp.choices[0].get('message', {}).get('content')
                    return {"response": text or "", "model_used": "openai:gpt-3.5-turbo"}
            except Exception as e:
                print(f"OpenAI fallback failed: {e}")

        # Final simple fallback: return product list or a helpful message so chat still works offline
        if extra_products_text:
            return {"response": f"AI services are unavailable right now. Here are the available products:\n\n{extra_products_text}"}

        return {"response": "AI services are currently unavailable. Please try again later.", "error": str(last_err)}
