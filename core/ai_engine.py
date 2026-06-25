import google.generativeai as genai

class GenerativeAI:
    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        # Use the gemini-2.5-flash model for fast, accurate conversational responses
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
    def ask(self, query):
        """
        Sends the user's spoken words to Gemini and returns a short, conversational text response.
        """
        try:
            # We instruct the model to keep its answers brief and conversational
            # since the response will be read aloud by the Text-to-Speech engine.
            prompt = f"You are Jarvis, a helpful, conversational voice assistant. Keep your response short, conversational, and easy to understand when spoken aloud. Do not use markdown, bullet points, or complex formatting. Answer this query: {query}"
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            print(f"[AI Engine Error]: {e}")
            return "I'm having trouble connecting to my AI brain right now."
