# ============================================================
# 账号 & API Key 配置 —— 示例文件
# ============================================================
# 复制此文件为 keys_config.py 并填入真实 API Key
# keys_config.py 已加入 .gitignore，不会被提交

# —— 东方财富模拟交易 ——
DONGFANG_APIKEY = "your_dongfang_apikey"
DONGFANG_NAME = "东方财富"

# —— 华泰证券杯 · 账户1（7493）——
HT_7493_APIKEY = "your_ht_7493_apikey"
HT_7493_NAME = "华泰-7493"

HT_8268_APIKEY = "your_ht_8268_apikey"
HT_8268_NAME = "华泰-8268"

# ============================================================
# 统一查询入口（内部使用，不要改）
# ============================================================
KEY_MAP = {
    "dongfang": DONGFANG_APIKEY,
    "ht_7493": HT_7493_APIKEY,
    "ht_8268": HT_8268_APIKEY,
}

def get_key(account_id):
    return KEY_MAP.get(account_id, "")

def is_pending(account_id):
    return get_key(account_id) == "PENDING_USER_INPUT"
