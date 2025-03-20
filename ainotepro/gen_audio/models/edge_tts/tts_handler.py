import os
import sys

# 固定的 `libs` 目录
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
LIBS_DIR = os.path.join(PLUGIN_ROOT, "libs")
sys.path.insert(0, LIBS_DIR)  # 添加到 Python 路径

import json
import asyncio
import edge_tts
import html
from aqt.sound import play
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

# ✅ 创建全局 `ThreadPoolExecutor`
executor = ThreadPoolExecutor()

# 获取当前插件目录
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "config")

# 读取 JSON 文件
def load_json(file_name):
    path = os.path.join(DATA_DIR, file_name)
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

# 载入语言、声音、映射数据
TTS_LANGUAGES = load_json("tts_languages.json")
TTS_VOICES = load_json("tts_voices.json")
LANGUAGE_MAP = load_json("language_map.json")

# 语言代码 -> 语言名称的映射已经存在于 LANGUAGE_MAP
# 反向映射缓存（语言名称 -> 语言代码）
_reverse_language_map = None

# 获取 Edge-TTS 支持的语言列表（返回 {"ar": "Arabic", "de": "German"} 这样的结构）
def get_languages(tts_model):
    languages = TTS_LANGUAGES.get(tts_model, [])
    return {lang: LANGUAGE_MAP.get(lang, lang) for lang in languages}  # 语言全称

# 获取符合语言和性别的声音
def get_voices(tts_model, language, gender):
    if tts_model not in TTS_VOICES or language not in TTS_VOICES[tts_model]:
        return []
    return [voice["name"] for voice in TTS_VOICES[tts_model][language] if voice["gender"] == gender]

# 通过语言代码获取语言全称 (e.g., "fr" -> "French")
def get_language_name(lang_code):
    return LANGUAGE_MAP.get(lang_code)

# 通过语言全称获取语言代码 (e.g., "French" -> "fr")，使用缓存
def get_language_code(language_name):
    global _reverse_language_map
    if _reverse_language_map is None:  # 仅在首次调用时创建反向映射
        _reverse_language_map = {v: k for k, v in LANGUAGE_MAP.items()}
    return _reverse_language_map.get(language_name)

class HTMLStripper(HTMLParser):
    """HTML 解析器用于去除 HTML 标签"""
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_data(self):
        return ''.join(self.text)

def strip_html(text):
    """去除 HTML 标签"""
    stripper = HTMLStripper()
    stripper.feed(text)
    return stripper.get_data()

def clean_text(text):
    """清理文本：去 HTML，修正 HTML 实体，标准化符号"""
    
    print(f"🎤 TTS Original text: {repr(text)}")  # ✅ Debug 原始文本
    
    text = text.strip()  # ✅ 去除首尾空格和换行
    text = strip_html(text)  # ✅ 先去除 HTML 标签
    text = html.unescape(text)  # ✅ 修正 HTML 实体
    text = (text.replace("’", "'").replace("‘", "'")  # ✅ 统一单引号
                .replace("“", '"').replace("”", '"')  # ✅ 统一双引号
                .replace("–", "-").replace("—", "-")  # ✅ 破折号标准化
                .replace("…", "...")  # ✅ 省略号标准化
                .replace("＆", "&"))  # ✅ 修正全角＆

    print(f"✅ Cleaned text: {repr(text)}")  # ✅ Debug 处理后的文本
    return text

def generate_and_play_tts(text, voice, speed, volume, pitch, output_path, play_audio=False):
    print(f"🎙️ TTS Original text: {repr(text)}")
    """生成 TTS 语音（可选是否播放）"""
    text = clean_text(text)  # 清理文本
    if not text.strip():
        print("⚠️ No valid text after cleaning, skipping TTS.")
        return
    print(f"🎙️ TTS cleaned text: {repr(text)}")  # ✅ Debug 确保一致

    async def run_tts():
        await generate_tts_audio(text, voice, speed, volume, pitch, output_path)
        if play_audio and os.path.exists(output_path):
            play(output_path)

    try:
        loop = asyncio.get_running_loop()  # ✅ 获取当前运行中的事件循环
        loop.create_task(run_tts())  # ✅ 在已存在的事件循环中创建任务（不会阻塞 GUI）
    except RuntimeError:
        # ✅ 如果没有事件循环，则在后台线程中创建一个新事件循环
        thread_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(thread_loop)
        thread_loop.run_until_complete(run_tts())  # ✅ 运行 TTS 任务（同步方式）
        # ❌ **不要关闭 loop，否则可能导致 `Event loop is closed`**

async def generate_tts_audio(text, voice, speed, volume, pitch, output_path):
    """使用 edge-tts 生成 TTS 音频，确保 aiohttp.ClientSession 正确关闭"""
    try:
        speed_str = f"+{speed}%" if speed >= 0 else f"{speed}%"
        volume_str = f"+{volume}%" if volume >= 0 else f"{volume}%"
        pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"

        print(f"🎙️ Generating TTS: {text} → {output_path}")

        tts = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=speed_str,
            volume=volume_str,
            pitch=pitch_str,
        )
        await tts.save(output_path)

        print(f"✅ TTS generated successfully: {output_path}")

    except Exception as e:
        print(f"❌ Error generating TTS: {e}")

def play_audio(file_path):
    """使用 Anki 内置播放器 (mpv) 播放音频"""
    if os.path.exists(file_path):
        print(f"📢 Playing: {file_path}")
        play(file_path)
    else:
        print(f"⚠️ Error: File {file_path} does not exist!")

def unload():
    """确保 `ThreadPoolExecutor` 释放资源，并正确关闭 asyncio 事件循环"""
    global executor
    if executor:
        executor.shutdown(wait=False)  # ✅ 关闭线程池，释放资源
        executor = None

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.stop()
            loop.close()
    except RuntimeError:
        pass  # 可能已经被关闭

    print("✅ EchoAI plugin unloaded and executor shut down.")  # 方便调试


