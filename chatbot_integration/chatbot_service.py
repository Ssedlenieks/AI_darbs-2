import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient


class ChatbotService:
    def __init__(self):
        """Inicializē ChatbotService ar Hugging Face API"""
        #viss strada

        # 1. SOLIS - API atslēgas ielāde
        load_dotenv()  # Ielādē no .env failā ROOT direktorijā
        api_key = os.getenv('HUGGINGFACE_API_KEY')

        if not api_key:
            print("DEBUG: ✗ No API key found in .env file")
            self.client = None
            self.api_key = None
            return

        print("DEBUG: ✓ API key loaded successfully")

        # 2. SOLIS - Hugging Face klienta inicializācija ar PAREIZO modeli
        self.api_key = api_key
        try:
            self.client = InferenceClient(
                model="katanemo/Arch-Router-1.5B",  # ✓ PAREIZAIS MODELIS
                token=api_key
            )
            print("DEBUG: ✓ InferenceClient initialized with katanemo/Arch-Router-1.5B")
        except Exception as e:
            print(f"DEBUG: ✗ Failed to initialize InferenceClient: {e}")
            self.client = None

        # 3. SOLIS - Sistēmas instrukcijas definēšana
        self.system_instruction = (
            "You are a helpful e-shop assistant. Answer user questions concisely using only the provided product information. "
            "If asked about anything else, politely decline and redirect to shop topics."
        )

    def get_chatbot_response(self, user_message, chat_history=None, extra_products_text=None):
        """
        Iegūst chatbot atbildi no Hugging Face API

        Args:
            user_message (str): Lietotāja jautājums
            chat_history (list): Iepriekšējā saruna (default: [])
            extra_products_text (str): Produktu informācija (optional)

        Returns:
            dict: {"response": "AI atbilde"}
        """

        if chat_history is None:
            chat_history = []

        print(f"DEBUG: get_chatbot_response called with: '{user_message}'")
        print(f"DEBUG: Chat history length: {len(chat_history)}")

        if not self.client:
            return {"response": "⚠️ AI service not available. Check your API key."}

        # 4. SOLIS - Ziņojumu saraksta izveide
        messages = [{"role": "system", "content": self.system_instruction}]

        # Pievienot produktu informāciju ja ir pieejama
        if extra_products_text:
            messages.append({
                "role": "system",
                "content": f"Available products:\n{extra_products_text}"
            })

        # Pievienot iepriekšējo sarunas vēsturi
        messages.extend(chat_history)

        # Pievienot pēdējo lietotāja ziņu
        messages.append({"role": "user", "content": user_message})

        print(f"DEBUG: Total messages: {len(messages)}")

        # 5. SOLIS - Hugging Face API izsaukums ar error handling
        try:
            print("DEBUG: Calling Hugging Face API...")

            response = self.client.chat_completion(
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            )

            print("DEBUG: ✓ API response received")

            # Iegūt tekstu no atbildes
            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                assistant_message = response.choices[0].message.content
                print(f"DEBUG: Response: {assistant_message[:50]}...")
                return {"response": assistant_message.strip()}
            else:
                print("DEBUG: ✗ Empty response")
                return {"response": "Sorry, I couldn't generate a response."}

        except Exception as e:
            print(f"DEBUG: ✗ Exception: {type(e).__name__}")
            print(f"DEBUG: Message: {str(e)}")

            error_str = str(e).lower()
            if "not supported" in error_str or "model" in error_str:
                return {"response": "⚙️ Model not available. Try again later."}
            elif "rate_limit" in error_str:
                return {"response": "🔄 Too many requests. Wait a moment."}
            elif "unauthorized" in error_str:
                return {"response": "🔐 API authentication error. Check .env"}
            else:
                return {"response": f"❌ Error: {str(e)[:80]}"}
