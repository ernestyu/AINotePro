import os
import requests
import time
import random
import urllib.parse  # ✅ 进行 URL 编码

def supports_customization():
    """
    Pollinations 允许部分 API 配置，但不需要 Base URL 和 API Key。
    """
    return {
        "base_url": False,
        "api_key": False,
        "model": False
    }

def generate_image(prompt, output_path, width=1024, height=1024, seed=100, model="flux", nologo=True):
    """
    发送请求至 Pollinations API，生成图片并下载到指定路径。

    :param prompt: 生成图片的文本描述
    :param output_path: 图片保存路径
    :param width: 图片宽度
    :param height: 图片高度
    :param seed: 随机种子
    :param model: 生成模型
    :param nologo: 是否去掉水印
    :return: 下载的图片文件名（成功）或 None（失败）
    """
    if not prompt or not isinstance(prompt, str) or prompt.strip() == "":
        print("[Pollinations] Error: Prompt is empty or invalid.")
        return None

    # ✅ **进行 URL 编码**
    encoded_prompt = urllib.parse.quote(prompt)

    try:
        # ✅ **随机延迟 1~5 秒，避免 API 频繁请求**
        delay = random.uniform(1, 5)
        print(f"[Pollinations] Delaying for {delay:.2f} seconds to avoid rate limiting...")
        time.sleep(delay)

        # ✅ 使用正确的 Pollinations API 地址
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&seed={seed}&model={model}&nologo={str(nologo).lower()}"
        )

        print(f"[Pollinations] Requesting image from: {url}")

        response = requests.get(url, stream=True, timeout=15)

        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                file.write(response.content)
            print(f"[Pollinations] Image saved to {output_path}")
            return os.path.basename(output_path)
        else:
            print(f"[Pollinations] Failed - HTTP {response.status_code}: {response.reason}")

        return None
    except requests.Timeout:
        print("[Pollinations] Error: Request timed out.")
    except requests.RequestException as e:
        print(f"[Pollinations] Error during request: {e}")
    except Exception as e:
        print(f"[Pollinations] Unexpected error: {e}")

    return None
