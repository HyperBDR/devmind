"""
API Response Constants

This module defines constants used for standardizing API response formats.
These constants are used by custom renderers and views to ensure consistent
response structure across the API.

Constants:
    SUCCESS_CODE: HTTP status code for successful responses (0)
    SUCCESS_MESSAGE: Message string for successful responses ("success")
    FAILED_MESSAGE: Message string for failed responses ("failed")
"""

# Success response code
# Used in API responses to indicate successful operations
# Note: 0 is used instead of HTTP 200 to distinguish from HTTP status codes
SUCCESS_CODE = 0

# Success response message
# Standard message for successful API responses
SUCCESS_MESSAGE = "success"

# Failed response message
# Standard message for failed API responses
FAILED_MESSAGE = "failed"

# ============================
# Base Filter Words Constants
# ============================
# These are the base filter words used across all content collection
# systems (Google News, GitHub Trending, etc.)
# Users can add custom filter words in their Settings
# (google_news_config or github_config), which will be merged with these
# base words (with deduplication)

BASE_FILTER_WORDS = [
    # VPN and proxy tools (circumvention tools) - English
    "vpn",
    "vmess",
    "v2ray",
    "v2rayx",
    "shadowrocket",
    "shadowsocks",
    "wireguard",
    "openvpn",
    "quantumult",
    "quantumultx",
    "proxifier",
    "fqrouter",
    "psiphon",
    "tor browser",
    # VPN and proxy tools - Chinese
    "翻墙",
    "科学上网",
    "梯子",
    "代理",
    "VPN",
    "V2Ray",
    "Shadowsocks",
    "WireGuard",
    "OpenVPN",
    "Quantumult",
    "QuantumultX",
    "Shadowrocket",
    # Adult/sexual content keywords - English
    "sexy",
    "porn",
    "pornography",
    "nsfw",
    "adult content",
    "erotic",
    "nude",
    "naked",
    # Adult/sexual content keywords - Chinese
    "色情",
    "黄色",
    "成人",
    "性爱",
    "情色",
    "裸露",
    "三级",
    # Political sensitive keywords (China-related) - English
    "tiananmen",
    "tiananmen square",
    "june 4",
    "falun gong",
    "falungong",
    "free tibet",
    "tibet independence",
    "xinjiang",
    "east turkestan",
    "hong kong independence",
    "hongkong independence",
    "taiwan independence",
    "taiwanese independence",
    "china democracy",
    "chinese democracy",
    "chinese communist party",
    "communist party of china",
    # Political sensitive keywords (China-related) - Chinese
    "天安门",
    "六四",
    "法轮功",
    "法轮大法",
    "藏独",
    "西藏独立",
    "新疆",
    "东突",
    "东突厥斯坦",
    "港独",
    "香港独立",
    "台独",
    "台湾独立",
    "民运",
    "民主运动",
    "中共",
    "中国共产党",
    # Chinese leaders names - English
    "xi jinping",
    "xi jin ping",
    "jiang zemin",
    "jiang ze min",
    "hu jintao",
    "hu jin tao",
    "wen jiabao",
    "wen jia bao",
    "li peng",
    "zhao ziyang",
    "zhao zi yang",
    "deng xiaoping",
    "deng xiao ping",
    "mao zedong",
    "mao ze dong",
    # Chinese leaders names - Chinese
    "习近平",
    "江泽民",
    "胡锦涛",
    "温家宝",
    "李鹏",
    "赵紫阳",
    "邓小平",
    "毛泽东",
    "李克强",
    "王岐山",
    "汪洋",
    "栗战书",
    "韩正",
    "王沪宁",
    "赵乐际",
]

# ============================
# Content Review Prompt Constants
# ============================
# Legality check instructions used by both Google News and GitHub
LEGALITY_CHECK_INSTRUCTIONS = (
    "You must check if the content contains **severe** "
    "prohibited content.\n\n"
    "**Prohibited Content Categories**:\n\n"
    "1. **Politically Sensitive Content** (MUST mark as illegal):\n"
    "   - **ALL political topics and discussions** must be marked as "
    "illegal\n"
    "   - Content related to political parties, political movements, or\n"
    "     political ideologies\n"
    "   - Content that violates political regulations\n"
    "   - Hate speech or incitement to violence\n"
    "   - Clearly illegal political activities\n"
    "   - Any content that primarily focuses on political topics, "
    "regardless\n"
    "     of whether it promotes or opposes any political view\n\n"
    "2. **China-Specific Sensitive Content** (MUST mark as illegal):\n"
    "   - **Taiwan-Related Issues** (台湾问题):\n"
    "     * Content that promotes \"Taiwan independence\" (台独), "
    "\"Taiwanese\n"
    "       independence\", or any content that challenges the One-China\n"
    "       principle\n"
    "     * Content that refers to Taiwan as a country or uses terms "
    "like\n"
    "       \"Republic of China\" in a political context\n"
    "     * Content that supports Taiwan independence movements or "
    "separatist\n"
    "       activities\n"
    "   - **Hong Kong and Macau Issues** (香港、澳门问题):\n"
    "     * Content that promotes \"Hong Kong independence\" (港独) or "
    "\"Macau\n"
    "       independence\"\n"
    "     * Content that supports Hong Kong or Macau independence "
    "movements,\n"
    "       separatist activities, or challenges Chinese sovereignty over\n"
    "       these regions\n"
    "   - **Chinese Leaders' Names** (国家领导人名字):\n"
    "     * Content that contains defamatory, slanderous, or "
    "disrespectful\n"
    "       content about Chinese leaders (e.g., Xi Jinping, Jiang Zemin, "
    "Hu\n"
    "       Jintao, Wen Jiabao, Li Peng, Zhao Ziyang, Deng Xiaoping, Mao\n"
    "       Zedong, Li Keqiang, Wang Qishan, Wang Yang, Li Zhanshu, Han\n"
    "       Zheng, Wang Huning, Zhao Leji, etc.)\n"
    "     * Content that uses Chinese leaders' names in a context that\n"
    "       violates Chinese laws or political regulations\n"
    "   - **Circumvention Tools** (翻墙工具):\n"
    "     * Content whose primary purpose is to provide VPN, proxy, or "
    "other\n"
    "       tools for circumventing China's internet regulations (翻墙, "
    "科学上网,\n"
    "       梯子, etc.)\n"
    "     * Content that explicitly promotes or facilitates bypassing "
    "Chinese\n"
    "       internet censorship or firewall restrictions\n"
    "     * Content that is a circumvention tool (e.g., V2Ray, "
    "Shadowsocks,\n"
    "       Clash, Trojan, WireGuard, OpenVPN, Surge, Quantumult,\n"
    "       Shadowrocket, etc.) designed primarily for bypassing Chinese\n"
    "       internet controls\n"
    "   - **Events Detrimental to China** (不利于中国的事件):\n"
    "     * Content that promotes or supports events that are detrimental "
    "to\n"
    "       China's interests, including but not limited to:\n"
    "       - Tiananmen Square related content (天安门, 六四, June 4, 6.4, "
    "64)\n"
    "       - Falun Gong related content (法轮功, 法轮大法)\n"
    "       - Tibet independence content (藏独, 西藏独立)\n"
    "       - East Turkestan content (东突, 东突厥斯坦)\n"
    "       - Content promoting \"democracy movements\" that challenge "
    "Chinese\n"
    "         political system (民运, 民主运动)\n"
    "       - Content that explicitly challenges the Chinese Communist "
    "Party\n"
    "         or Chinese political system (中共, 中国共产党)\n\n"
    "3. **Violent Content**:\n"
    "   - Explicit promotion of violence\n"
    "   - Graphic descriptions of violence\n"
    "   - Tools/methods for harmful acts\n\n"
    "4. **Adult/Sexual Content**:\n"
    "   - Explicit sexual descriptions\n"
    "   - Pornography\n"
    "   - Clearly inappropriate sexual material\n\n"
    "5. **Illegal Activities**:\n"
    "   - Primary purpose is to facilitate illegal activities\n"
    "   - Hacking tools for malicious purposes\n"
    "   - Tools for circumventing laws\n\n"
    "**Important Guidelines**:\n"
    "- **Political Content**: ALL content that primarily focuses on "
    "political\n"
    "  topics, discussions, or content MUST be marked as illegal "
    "(`is_legal`\n"
    "  = false), regardless of the political stance or viewpoint.\n"
    "- **China-Specific Content**: ALL content related to Taiwan "
    "independence,\n"
    "  Hong Kong/Macau independence, disrespectful use of Chinese "
    "leaders'\n"
    "  names, circumvention tools, and events detrimental to China MUST "
    "be\n"
    "  marked as illegal.\n"
    "- For other content categories, use a **lenient and reasonable "
    "standard**.\n"
    "  Only mark content as illegal if it is **clearly and primarily**\n"
    "  violating regulations.\n"
    "- When in doubt for non-political and non-China-specific content, "
    "err on\n"
    "  the side of **allowing the content** (`is_legal` = true).\n"
    "- Normal technical tools and educational resources that do NOT "
    "focus on\n"
    "  political topics or China-specific sensitive content should "
    "generally\n"
    "  be marked as legal, even if they touch on sensitive topics.\n"
    "- Set `is_legal` to `false` for ALL political content, ALL "
    "China-specific\n"
    "  sensitive content, and for other content that is **obviously and\n"
    "  primarily** prohibited. Otherwise, set it to `true`.\n"
)

# Unified content review prompt template used for all apps
CONTENT_REVIEW_PROMPT_TEMPLATE = (
    "## Task Overview\n\n"
    "You are a **content review assistant** for content collection "
    "systems.\n"
    "Your task is to review the content and determine if it contains\n"
    "illegal or prohibited content.\n\n"
    "---\n\n"
    "## Content Information\n\n"
    "{content_info}\n\n"
    "---\n\n"
    "## Legality Check Instructions\n\n"
    + LEGALITY_CHECK_INSTRUCTIONS +
    "\n\n---\n\n"
    "## Output Format\n\n"
    "Return a JSON object with the following structure:\n\n"
    "{{\n"
    "  \"is_legal\": true/false,\n"
    "  \"review_reason\": \"Brief reason if is_legal is false, empty "
    "string if true\"\n"
    "}}\n\n"
    "**Note**: Only set `is_legal` to `false` if the content is "
    "**clearly and\n"
    "primarily** violating regulations. For all other cases, including "
    "ambiguous\n"
    "situations, set `is_legal` to `true`.\n"
)
