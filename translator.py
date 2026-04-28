import deepl
import os

LANGUAGE_MAP = {
    "en": "EN-US",
    "es": "ES",
    "fr": "FR",
    "de": "DE",
    "it": "IT",
    "pt": "PT-BR",
    "ja": "JA",
    "ko": "KO",
    "zh": "ZH",
    "ru": "RU",
    "ar": "AR",
    "nl": "NL",
    "pl": "PL",
    "sv": "SV",
    "tr": "TR",
}

LANGUAGE_INFO = {
    "en": {"name": "English",    "flag": "🇬🇧"},
    "es": {"name": "Spanish",    "flag": "🇪🇸"},
    "fr": {"name": "French",     "flag": "🇫🇷"},
    "de": {"name": "German",     "flag": "🇩🇪"},
    "it": {"name": "Italian",    "flag": "🇮🇹"},
    "pt": {"name": "Portuguese", "flag": "🇧🇷"},
    "ja": {"name": "Japanese",   "flag": "🇯🇵"},
    "ko": {"name": "Korean",     "flag": "🇰🇷"},
    "zh": {"name": "Chinese",    "flag": "🇨🇳"},
    "ru": {"name": "Russian",    "flag": "🇷🇺"},
    "ar": {"name": "Arabic",     "flag": "🇸🇦"},
    "nl": {"name": "Dutch",      "flag": "🇳🇱"},
    "pl": {"name": "Polish",     "flag": "🇵🇱"},
    "sv": {"name": "Swedish",    "flag": "🇸🇪"},
    "tr": {"name": "Turkish",    "flag": "🇹🇷"},
}

class Translator:
    def __init__(self):
        api_key = os.environ.get("DEEPL_API_KEY")
        if not api_key:
            raise ValueError("DEEPL_API_KEY environment variable not set.")
        self.client = deepl.Translator(api_key)

    def translate(self, text: str, target_lang: str) -> str:
        if not text or not text.strip():
            return text
        deepl_lang = LANGUAGE_MAP.get(target_lang.lower(), target_lang.upper())
        try:
            result = self.client.translate_text(text, target_lang=deepl_lang)
            return result.text
        except Exception as e:
            print(f"[Translator] Error translating to {target_lang}: {e}")
            return text

def get_language_info(code: str) -> dict:
    return LANGUAGE_INFO.get(code.lower(), {"name": code.upper(), "flag": "🌐"})
