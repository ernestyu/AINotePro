# openai.py

def supports_customization():
    """
    OpenAI 需要 Base URL 和 API Key，并允许选择模型。
    """
    return {
        "base_url": True,   # ✅ 需要 Base URL
        "api_key": True,    # ✅ 需要 API Key
        "model": False       # ✅ 允许选择模型
    }
