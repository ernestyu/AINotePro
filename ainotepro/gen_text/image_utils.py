
import base64
import json
import requests
import os
import time
import openai
from openai import OpenAI


def upload_to_img_hosting(image_path, img_hosting_api_key, upload_url):
    """上传图片到指定的 Hosting 平台，并返回外链 URL"""

    # 读取本地文件并转换为 Base64
    with open(image_path, "rb") as image_file:
        base64_data = base64.b64encode(image_file.read()).decode("utf-8").replace("\n", "")

    # 构建请求数据
    data = {
        "key": img_hosting_api_key,
        "source": base64_data,
        "filename": os.path.basename(image_path)
    }

    headers = {"Content-Type": "application/json"}

    # 发送 POST 请求
    response = requests.post(upload_url, headers=headers, data=json.dumps(data))

    # 解析响应
    if response.status_code == 200:
        result = response.json()
        if result.get("status") == 200:
            return result["original"]["url"]
        else:
            raise Exception(f"上传失败: {result.get('message', '未知错误')}")
    else:
        raise Exception(f"HTTP 请求失败, 状态码: {response.status_code}")



def generate_with_img(img_url, model_name, api_key, base_url, prompt):
    """
    使用 Claude 3 处理图片，并生成描述。
    - `img_url`: 上传后的图片 URL
    - `api_key`: OpenAI API Key
    - `base_url`: OpenAI API Base URL
    - `prompt`: 用户输入的 Prompt
    """
    if not api_key or not base_url:
        print("⚠️ OpenAI API Key 或 Base URL 为空，无法请求。")
        return "API Key 或 Base URL 未设置，请检查设置。"

    if not prompt:
        print("⚠️ Prompt 为空，请输入提示词。")
        return "Prompt 不能为空，请输入提示词。"

    print(f"📌 发送请求到 {base_url}, 使用 API Key: {api_key[:5]}****")

    # **重试次数**
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # **调用 OpenAI API**
            client = OpenAI(api_key=api_key, base_url=base_url)

            response = client.chat.completions.create(
                model= model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": img_url}},
                            {"type": "text", "text": prompt}  # ✅ 使用界面 Prompt
                        ]
                    }
                ],
                stream=True
            )

            # **拼接返回内容**
            result_text = ""
            for chunk in response:
                chunk_message = chunk.choices[0].delta.content

                # ✅ **修复：跳过 `None` 值，避免 TypeError**
                if chunk_message is None:
                    print("⚠️ API 返回 `None`，跳过该段内容。")
                    continue

                # ✅ **尝试强制转换为 UTF-8，防止乱码**
                try:
                    chunk_message = chunk_message.encode("utf-8").decode("utf-8")
                except Exception as e:
                    print(f"⚠️ 文本解码错误: {e}")
                    continue

                result_text += chunk_message
                print(chunk_message, end='', flush=True)

            return result_text if result_text else "⚠️ API 没有返回有效内容，请检查日志。"

        except openai.BadRequestError as e:
            # **解析 API 响应**
            error_message = str(e)
            print(f"❌ API 失败: {error_message}")

            # **如果是 400 错误，重试**
            if "Error code: 400" in error_message:
                if attempt < max_retries - 1:
                    print(f"🔄 API 过载，等待 1 秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(1)
                else:
                    print("❌ API 仍然返回 400，放弃重试。")
                    return f"⚠️ API 过载错误 (400)，请稍后再试。"
            else:
                # **其他错误直接返回**
                return f"⚠️ API 失败: {error_message}"

        except Exception as e:
            print(f"⚠️ 未知错误: {e}")
            return f"⚠️ 发生未知错误: {str(e)}"

    return "⚠️ API 无法返回有效内容，请稍后再试。"


