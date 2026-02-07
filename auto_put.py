import requests, os, math, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# ===== 配置部分 =====
# 从浏览器中提取这两个 Cookie 值（DevTools -> Storage -> Cookies -> Request Cookies）
CIVITAI_TOKEN = "YOUR_CIVITAI_TOKEN_HERE"
CSRF_TOKEN = "YOUR_CSRF_TOKEN_HERE"
VERSION_ID = "YOUR_MODEL_VERSION_ID_HERE"

# ⚠️ 如果步骤 B 返回 500 或 UNAUTHORIZED，将此改为从抓包中找到的 UUID（例如 f5ebae8f-xxxx-xxxx-xxxx-xxxxxxxxxxxx）
# 默认为 None 时会自动使用 init_res 中的 uuid 或 uploadId
HARDCODED_UUID = None

FILE_PATH = "YOUR_FILE_PATH"
FILE_NAME = os.path.basename(FILE_PATH)
FILE_SIZE = os.path.getsize(FILE_PATH)

# 创建干净的 Session 和手动精准设置关键 Cookie，其他的让它保持干净
client = requests.Session()
# 清除旧的 cookies 确保干净状态
client.cookies.clear()
# 只注入最基础的身份凭证
client.cookies.set('__Secure-civitai-token', CIVITAI_TOKEN, domain='civitai.com')
client.cookies.set('__Host-next-auth.csrf-token', CSRF_TOKEN, domain='civitai.com')

# 设置请求头（使用现代 Chrome User-Agent）
client.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "x-trpc-source": "react",
    "Origin": "https://civitai.com",
    "Referer": f"https://civitai.com/models/2365409?modelVersionId={VERSION_ID}",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})

def prepare_upload():
    """
    第一步：握手准备（分配专属路由）
    - 通过访问模型页面获取服务器分配的"专属路由"（civitai-route）
    - 服务器返回 Set-Cookie 响应，安全地添加路由到 Session
    
    原理: CivitAI 为每个用户IP分配一个唯一的"房间号"(civitai-route)
         后续上传操作都必须使用这个路由，否则会碰到 500 错误
    """
    print("📡 正在从服务器获取分配的专属路由...")
    try:
        # 访问模型页面，让服务器为你分配唯一的"房间号"
        # 这个请求会让服务器返回 Set-Cookie: civitai-route
        r = client.get(f"https://civitai.com/models/2365409?modelVersionId={VERSION_ID}", timeout=10)
        
        if r.status_code == 200:
            route = client.cookies.get('civitai-route')
            print(f"✅ 握手完成！分配的专属路由: {route}")
            return True
        else:
            print(f"⚠️ 握手返回异常状态码: {r.status_code}，但将继续尝试...")
            return False
    except Exception as e:
        print(f"⚠️ 握手过程中发生错误: {e}，但将继续尝试...")
        return False

def sync_cookie():
    """在关键步骤前同步最新的路由标识，确保不产生重复的 civitai-route 在 cookies 中"""
    print("🔄 正在同步最新的路由标识...")
    try:
        # 使用 API 调用，这个请求会返回最新的 civitai-route
        # 请求头中已经包含了所有必要的 cookies
        r = client.get("https://civitai.com/api/v1/models?limit=1", timeout=10)
        if r.status_code == 200:
            route = client.cookies.get('civitai-route')
            print(f"📡 当前路由: {route}")
            return True
        else:
            print(f"⚠️ 同步路由返回状态码: {r.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ 同步路由时出错: {e}")

def debug_complete_upload(upload_id, key, etags_list):
    # 物理合并 Payload (严格按照你抓到的格式：无嵌套、全小写字段)
    payload = {
        "bucket": "civitai-delivery-worker-prod",
        "key": key,
        "type": "Model", 
        "uploadId": upload_id,
        "parts": etags_list 
    }

    # 暴力清理 Cookie 冲突
    target_route = None
    for cookie in client.cookies:
        if cookie.name == 'civitai-route':
            target_route = cookie.value
            break
    client.cookies.clear()
    client.cookies.set('__Secure-civitai-token', CIVITAI_TOKEN, domain='civitai.com')
    client.cookies.set('__Host-next-auth.csrf-token', CSRF_TOKEN, domain='civitai.com')
    if target_route:
        client.cookies.set('civitai-route', target_route, domain='civitai.com')

    print("\n📦 步骤 A: 正在物理合并分块...")
    # 注意：这个接口通常是 /api/upload/complete
    res = client.post("https://civitai.com/api/upload/complete", json=payload)
    print(f"🚩 合并状态: {res.status_code}, 内容: {res.text}")
    return res.status_code in [200, 201, 204]

def run_mission():
    # 第 0 步：握手 - 从服务器获取分配的专属路由
    prepare_upload()
    
    # 第 1 步：初始化上传，获得 uploadId/key/S3 块地址
    print("📡 正在初始化上传，申请上传轨道...")
    init_res = client.post(
        "https://civitai.com/api/upload", 
        json={
            "filename": FILE_NAME, 
            "size": FILE_SIZE, 
            "type": "Model", 
            "modelVersionId": VERSION_ID
        },
        timeout=30
    ).json()
    
    uid = init_res['uploadId']
    key = init_res['key']
    urls = init_res['urls']
    chunk_size = math.ceil(FILE_SIZE / len(urls))
    etags = [None] * len(urls)

    # 第 2 步：多线程上传分块（带自动重试）
    print(f"🚀 开始上传文件 (4线程 + 自动重试)...")
    pbar = tqdm(total=FILE_SIZE, unit='B', unit_scale=True)

    def upload_worker(i, url_info):
        for attempt in range(5):  # 最多重试 5 次
            try:
                start = i * chunk_size
                end = min(start + chunk_size, FILE_SIZE)
                with open(FILE_PATH, 'rb') as f:
                    f.seek(start)
                    data = f.read(end - start)
                    r = client.put(url_info['url'], data=data, timeout=30)
                    if r.status_code == 200:
                        etags[i] = r.headers.get('ETag').replace('"', '')
                        pbar.update(len(data))
                        return True
            except Exception:
                time.sleep(2 ** (attempt + 1))  # 指数退避重试
        return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(upload_worker, i, u) for i, u in enumerate(urls)]
        for f in as_completed(futures):
            if not f.result():
                print("\n⚠️ 某个分块永久性失败，请重启脚本")

    pbar.close()

    # 构造 ETag 列表
    # 确保 ETag 只有一层双引号
    parts = [{"ETag": f'"{etag.strip(chr(34))}"', "PartNumber": i + 1} for i, etag in enumerate(etags)]

    # 优先寻找 uuid 字段，Civitai 的 create 接口通常更喜欢这个
    # 如果设置了 HARDCODED_UUID，使用它；否则自动从 init_res 中获取
    if HARDCODED_UUID:
        upload_uuid = HARDCODED_UUID
        print(f"📍 使用硬编码 UUID: {upload_uuid}")
    else:
        upload_uuid = init_res.get('uuid', uid)

    # 第 3 步：物理合并
    success = debug_complete_upload(uid, key, parts)

    if success:
        print("✅ 物理文件合并成功！")
        
        print("\n📝 步骤 B: 正在同步到数据库...")
        create_payload = {
            "json": {
                "authed": True,
                "bucket": "civitai-delivery-worker-prod",
                "key": key,
                "metadata": {
                    "format": "SafeTensor",
                    "fp": "fp16",
                    "size": "pruned"
                },
                "modelVersionId": int(VERSION_ID),
                "name": FILE_NAME,
                "sizeKB": FILE_SIZE / 1024,
                "type": "Model",
                "url": f"https://civitai-delivery-worker-prod.s3.amazonaws.com/{key}",
                "uuid": upload_uuid
            },
            "meta": {
                "values": {
                    "metadata.format": ["undefined"],
                    "metadata.fp": ["undefined"],
                    "metadata.size": ["undefined"]
                }
            }
        }
        
        # 这个请求走 trpc 路径，需要带上身份 header
        res_create = client.post(
            "https://civitai.com/api/trpc/modelFile.create", 
            json=create_payload,
            headers={"x-trpc-source": "react"}
        )
        print(f"🚩 注册状态: {res_create.status_code}, 内容: {res_create.text}")
        
        if "result" in res_create.text:
            print("✨✨ 所有操作已完成！请去网页端查看模型。")
    else:
        print("❌ 物理合并失败，请检查上传记录或 ETag。")

if __name__ == "__main__":
    run_mission()