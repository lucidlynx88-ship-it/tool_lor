# -*- coding: utf-8 -*-
import os
import json
import math
import threading
import datetime
import sys
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor
import customtkinter as ctk
from tkinter import ttk
from io import BytesIO
try:
    from PIL import Image
    PIL_OK = True
except Exception:
    Image = None
    PIL_OK = False

def gps_debug_log(msg):
    try:
        with open("gps_debug.log", "a", encoding="utf-8") as f:
            f.write(datetime.datetime.now().strftime("%H:%M:%S") + " | " + str(msg) + "\n")
    except Exception:
        pass

def ensure_pillow():
    """Bảo đảm có Pillow để đọc JPG avatar. Nếu máy thiếu thì thử cài tự động."""
    global Image, PIL_OK
    if PIL_OK and Image is not None:
        return True
    try:
        from PIL import Image as _Image
        Image = _Image
        PIL_OK = True
        return True
    except Exception:
        pass
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        from PIL import Image as _Image
        Image = _Image
        PIL_OK = True
        return True
    except Exception:
        PIL_OK = False
        return False

URL_GUILD  = "https://cmangax17.com/api/score_list?type=guild_battle_player&limit=1000"
URL_GUILD_MEMBER = "https://cmangax17.com/api/game_guild_member?waiting=0&guild={guild}"
URL_MINE   = "https://cmangax17.com/api/score_list?type=battle_mine_target&target={target}"
URL_ENERGY = "https://cmangax17.com/api/character_energy_mine?character={character}"
URL_EXP    = "https://cmangax17.com/api/data?data=game_exp"
URL_CHAR   = "https://cmangax17.com/api/get_data_by_id?table=game_character&data=info,data,other&id={id}"
URL_LANG   = "https://cmangax17.com/assets/json/lang.json?v=1v11"
URL_MARKET = "https://cmangax17.com/api/game_market?page={page}&limit={limit}&sort={sort}&type={type_filter}&special_level={special_level}&special_data={special_data}&special_type={special_type}&sign={sign_filter}&status={status}&owner={owner}"
URL_AVATAR_CANDIDATES = [
    "https://cmangax17.com/assets/tmp/avatar/{avatar}",
    "https://cmangax17.com/user/game/assets/tmp/avatar/{avatar}",
    "https://cmangax17.com/{avatar}",
]
GPS_SAVE_FILE = "gps_saved.json"
AVATAR_CACHE = {}

RARE_LABEL = {1: "Trắng", 2: "Xanh lam", 3: "Tím", 4: "Đỏ"}
DAN_EXP = {
    "Đan 1 (500 EXP)": 500,
    "Đan 2 (1000 EXP)": 1000,
    "Đan 3 (2000 EXP)": 2000,
    "Đan 4 (4000 EXP)": 4000,
    "Đan 5 (8000 EXP)": 8000,
    "Đan 6 (16000 EXP)": 16000,
    "Đan 7 (32000 EXP)": 32000,
    "Đan 8 (64000 EXP)": 64000,
    "Đan 9 (128000 EXP)": 128000,
}
PB_KTL = {"PB2": 40, "PB3": 80, "PB4": 160, "PB5": 320, "PB6": 640, "PB7": 1280, "PB8": 2560, "PB9": 5120, "PB9 rã đặc biệt": 12800}

_REALMS = ["Luyện Khí", "Trúc Cơ", "Kim Đan", "Nguyên Anh", "Hóa Thần", "Luyện Hư", "Hợp Thể", "Đại Thừa", "Độ Kiếp", "Chân Tiên", "Ngọc Tiên", "Đại La", "Đạo Tổ"]
_MINIS = ["Tầng 1", "Tầng 2", "Tầng 3", "Tầng 4", "Tầng 5", "Tầng 6", "Tầng 7", "Tầng 8", "Tầng 9", "Đỉnh Phong"]
LEVELS = [r + " " + m for r in _REALMS for m in _MINIS]
exp_map = {lvl: 0 for lvl in LEVELS}
exp_loaded = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
app = ctk.CTk()
app.title("tool lỏ")
app.geometry("1100x760")
app.minsize(1000, 680)

# ---------------- UI helpers ----------------
BG_CARD = "#1c1c1c"
BG_CARD2 = "#242424"
BORDER = "#343434"
BLUE = "#2d8cff"
YELLOW = "#ffcc33"
RED = "#ff6666"
MUTED = "#aeb8c2"

style = ttk.Style()
try: style.theme_use("clam")
except: pass
style.configure("Dark.TCombobox", fieldbackground="#2b2f33", background="#1f6aa5", foreground="white", bordercolor="#565b5e", arrowcolor="white", padding=8)
style.map("Dark.TCombobox", fieldbackground=[("readonly", "#2b2f33")], foreground=[("readonly", "white")], selectbackground=[("readonly", "#2b2f33")], selectforeground=[("readonly", "white")])

def clear(frame):
    for w in frame.winfo_children():
        w.destroy()

def card(parent, **kw):
    f = ctk.CTkFrame(parent, fg_color=kw.get("fg", BG_CARD), corner_radius=16, border_width=1, border_color=kw.get("border", BORDER))
    f.pack(fill="x", padx=12, pady=8)
    return f

def label(parent, text, size=15, weight="normal", color="white", **pack):
    l = ctk.CTkLabel(parent, text=text, font=("Arial", size, weight), text_color=color, anchor="w", justify="left")
    l.pack(**({"anchor":"w", "padx":16, "pady":4} | pack))
    return l

def empty_card(parent, text):
    clear(parent)
    c = card(parent)
    label(c, text, 16, "bold", MUTED, pady=18)


def copy_to_clipboard(text):
    try:
        app.clipboard_clear()
        app.clipboard_append(str(text))
        return True
    except Exception:
        return False


def make_selectable_box(parent, text, height=420, font_size=15):
    """Khung text có thể bôi đen, Ctrl+A, Ctrl+C nhưng không cho sửa nội dung."""
    box = ctk.CTkTextbox(
        parent,
        height=height,
        fg_color=BG_CARD,
        text_color="white",
        border_width=1,
        border_color=BORDER,
        corner_radius=14,
        font=("Consolas", font_size),
        wrap="none"
    )
    box.pack(fill="both", expand=True, padx=12, pady=8)
    box.insert("1.0", text)
    box.configure(state="disabled")

    def select_all(event=None):
        box.configure(state="normal")
        box.tag_add("sel", "1.0", "end-1c")
        box.configure(state="disabled")
        return "break"

    def copy_text(event=None):
        try:
            selected = box.get("sel.first", "sel.last")
        except Exception:
            selected = box.get("1.0", "end-1c")
        app.clipboard_clear()
        app.clipboard_append(selected)
        return "break"

    box.bind("<Control-a>", select_all)
    box.bind("<Control-A>", select_all)
    box.bind("<Control-c>", copy_text)
    box.bind("<Control-C>", copy_text)
    return box

def center_crop_square(img):
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))

def make_avatar_cover(img, size=112, radius=16, border=2, border_color="#c99600", bg_color="#2b2b2b"):
    """Tạo avatar fit kín khung, bo góc và giữ viền vàng."""
    if img is None or not ensure_pillow():
        return None
    try:
        from PIL import ImageDraw
        img = center_crop_square(img.convert("RGBA")).resize((size - border * 2, size - border * 2), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=bg_color, outline=border_color, width=border)

        mask = Image.new("L", (size - border * 2, size - border * 2), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, size - border * 2 - 1, size - border * 2 - 1), radius=max(1, radius - border), fill=255)
        canvas.paste(img, (border, border), mask)
        # vẽ lại viền để ảnh không che mất border
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, outline=border_color, width=border)
        return canvas
    except Exception:
        return img

def fetch_avatar_pil(avatar, author=None):
    # Avatar chỉ tải theo thời điểm bấm nút, có cache để bấm lại không phải tải lại.
    if not ensure_pillow():
        return None

    avatar = str(avatar or "").strip().lstrip("/")
    author = str(author or "").strip()
    cache_key = avatar or author
    if cache_key and cache_key in AVATAR_CACHE:
        return AVATAR_CACHE[cache_key]

    candidates = []
    if avatar:
        # Ưu tiên đúng URL API trả về.
        candidates.append(avatar)
        if "?" in avatar:
            candidates.append(avatar.split("?", 1)[0])
    if author:
        candidates.append(f"{author}.jpg")

    seen = set()
    clean_candidates = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            clean_candidates.append(item)

    # Path đúng đang dùng trên web là assets/tmp/avatar.
    # Chỉ thử thêm path phụ khi URL chính fail để tránh chờ lâu.
    urls = []
    for item in clean_candidates:
        if item.startswith(("http://", "https://")):
            urls.append(item)
        else:
            urls.append(URL_AVATAR_CANDIDATES[0].format(avatar=item))
            if item.endswith(".jpg") and author:
                pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://cmangax17.com/user/game/dashboard",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    for url in urls:
        try:
            r = requests.get(url, timeout=2.5, headers=headers, allow_redirects=True)
            ctype = (r.headers.get("Content-Type") or "").lower()
            if r.status_code != 200 or not r.content:
                continue
            if ("image" not in ctype) and (r.content[:20].lower().startswith(b"<!doctype") or r.content[:20].lower().startswith(b"<html")):
                continue
            img = Image.open(BytesIO(r.content)).convert("RGBA")
            img = center_crop_square(img)
            if cache_key:
                AVATAR_CACHE[cache_key] = img
            return img
        except Exception:
            continue
    return None

def stat_box(parent, title, value, color=BLUE, width=180):
    f = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=12)
    f.pack(side="left", fill="both", expand=True, padx=6, pady=8)
    label(f, title, 13, "normal", MUTED, padx=14, pady=(12,0))
    label(f, str(value), 24, "bold", color, padx=14, pady=(0,12))
    return f

def mine_stat_box(parent, title, value, color=BLUE):
    # Box nhỏ riêng cho card Mỏ hiện tại để không bị cắt chữ trong layout dọc.
    f = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=10)
    f.pack(side="left", fill="both", expand=True, padx=4, pady=6)
    label(f, title, 12, "normal", MUTED, padx=10, pady=(8,0))
    text = str(value)
    size = 18
    if len(text) > 18:
        size = 15
    if len(text) > 26:
        size = 13
    label(f, text, size, "bold", color, padx=10, pady=(0,8))
    return f


def _walk_find_value(obj, names):
    """Tìm giá trị theo nhiều tên key trong dict/list lồng nhau."""
    names = {str(x).lower() for x in names}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in names and v not in (None, "", [], {}):
                return v
        for v in obj.values():
            found = _walk_find_value(v, names)
            if found not in (None, "", [], {}):
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _walk_find_value(v, names)
            if found not in (None, "", [], {}):
                return found
    return None

def _format_short_time(ts):
    try:
        ts = int(float(ts))
        return datetime.datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")
    except Exception:
        return ""

def _format_duration(seconds):
    try:
        seconds = int(float(seconds))
    except Exception:
        return ""
    if seconds < 0:
        seconds = 0
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d}n {h}g {m}p"
    if h:
        return f"{h}g {m}p"
    return f"{m}p"


def _fmt_number_vn(value):
    try:
        f = float(value)
        if f.is_integer():
            return str(int(f))
        return (f"{f:.2f}").rstrip("0").rstrip(".")
    except Exception:
        return str(value)

def get_mine_time_text(mine):
    """Thời gian mỏ lấy đúng từ key times nằm cùng lớp với reward trong data của API.
    Ví dụ: {"reward": {...}, "times": 26} => 26 phút.
    Không quét sâu bừa bãi vì trong battle/equipment có nhiều key times khác.
    """
    raw_times = None

    if isinstance(mine, dict):
        # Giá trị này được gắn khi parse row["data"] trong fetch_mine_worker.
        raw_times = mine.get("_mine_times")

        # Nếu mine chính là inner data và times > 0 thì dùng.
        # Không lấy times=0 vì API có key times=0 ở cuối object.
        if raw_times in (None, "", [], {}):
            try:
                direct_times = mine.get("times")
                if direct_times not in (None, "", [], {}) and float(direct_times) > 0:
                    raw_times = direct_times
            except Exception:
                pass

        # Nếu lỡ truyền outer row thì parse data rồi lấy times của inner data.
        if raw_times in (None, "", [], {}):
            data_obj = _parse_reward_obj(mine.get("data"))
            if isinstance(data_obj, dict):
                raw_times = data_obj.get("times")

    try:
        if raw_times not in (None, "", [], {}):
            minutes = float(raw_times)
            if minutes <= 0:
                return "0 phút"
            if minutes.is_integer():
                minutes = int(minutes)
            if isinstance(minutes, int):
                if minutes >= 60:
                    h, m = divmod(minutes, 60)
                    return f"{h} giờ {m} phút" if m else f"{h} giờ"
                return f"{minutes} phút"
            return f"{_fmt_number_vn(minutes)} phút"
    except Exception:
        pass

    return "Không có"

def _parse_reward_obj(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value

def extract_mine_reward_times_raw(data_raw):
    """Lấy đúng reward/times thật từ chuỗi data_raw, không dùng regex.

    API có key trùng:
      "reward": {"gold":..., "mine_ore":...}, "times": 26, ... "reward": [], "times": 0
    json.loads() sẽ lấy key cuối, nên phải lấy đoạn reward/times thật trước khi parse JSON.
    """
    if not isinstance(data_raw, str) or not data_raw:
        return None, None

    def find_matching_brace(s, open_pos):
        depth = 0
        in_str = False
        esc = False
        for i in range(open_pos, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    # Tìm reward thật có gold/mine_ore. Không đụng reward=[] ở cuối.
    key_positions = []
    for key in ['"reward":{"gold"', '"reward": {"gold"', '"reward":{"mine_ore"', '"reward": {"mine_ore"']:
        pos = data_raw.find(key)
        if pos != -1:
            key_positions.append(pos)
    if not key_positions:
        return None, None

    reward_key_pos = min(key_positions)
    colon_pos = data_raw.find(":", reward_key_pos)
    if colon_pos == -1:
        return None, None

    open_pos = data_raw.find("{", colon_pos)
    if open_pos == -1:
        return None, None

    close_pos = find_matching_brace(data_raw, open_pos)
    if close_pos == -1:
        return None, None

    reward_raw = data_raw[open_pos:close_pos + 1]
    try:
        reward_obj = json.loads(reward_raw)
    except Exception:
        reward_obj = None

    # Lấy times ngay sau reward object bằng find, không regex.
    times_raw = None
    search_from = close_pos + 1
    times_key = '"times"'
    times_pos = data_raw.find(times_key, search_from, search_from + 200)
    if times_pos != -1:
        colon = data_raw.find(":", times_pos)
        if colon != -1:
            j = colon + 1
            while j < len(data_raw) and data_raw[j] in " \t\r\n":
                j += 1
            k = j
            while k < len(data_raw) and (data_raw[k].isdigit() or data_raw[k] == "."):
                k += 1
            if k > j:
                times_raw = data_raw[j:k]

    return reward_obj, times_raw

def get_mine_reward_values(mine):
    """Lấy gold.amount và mine_ore.amount đúng từ reward cùng lớp với times."""
    reward = None
    if isinstance(mine, dict):
        reward = mine.get("_mine_reward")
        if reward in (None, "", [], {}):
            reward = mine.get("reward")
        if reward in (None, "", [], {}):
            data_obj = _parse_reward_obj(mine.get("data"))
            if isinstance(data_obj, dict):
                reward = data_obj.get("reward")

    if reward in (None, "", [], {}):
        reward = _walk_find_value(mine, ["reward", "rewards"])

    reward = _parse_reward_obj(reward)

    gold_amount = None
    ore_amount = None
    extra_parts = []

    if isinstance(reward, dict):
        gold = reward.get("gold")
        ore = reward.get("mine_ore")
        if isinstance(gold, dict) and gold.get("amount") not in (None, ""):
            gold_amount = _fmt_number_vn(gold.get("amount"))
        if isinstance(ore, dict) and ore.get("amount") not in (None, ""):
            ore_amount = _fmt_number_vn(ore.get("amount"))

        for key, val in reward.items():
            if key in ("gold", "mine_ore"):
                continue
            if isinstance(val, dict):
                amount = val.get("amount") or val.get("num") or val.get("count") or ""
                sign = val.get("sign") or val.get("id") or val.get("name") or key
                extra_parts.append(f"{sign} x{_fmt_number_vn(amount)}" if amount not in (None, "") else str(sign))
            elif val not in (None, "", [], {}):
                extra_parts.append(f"{key}: {val}")

    return gold_amount, ore_amount, extra_parts


def reward_value_box(parent, title, value, icon, value_color, bg_color):
    box = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=12, border_width=1, border_color=BORDER)
    box.pack(side="left", fill="both", expand=True, padx=5, pady=6)
    label(box, f"{icon} {title}", 12, "normal", MUTED, padx=12, pady=(8, 0))
    label(box, value if value not in (None, "") else "0", 19, "bold", value_color, padx=12, pady=(0, 10))
    return box


def get_mine_material_text(mine):
    """Hiển thị reward của mỏ: gold = vàng, mine_ore = khoáng."""
    reward = None
    if isinstance(mine, dict):
        reward = mine.get("reward")
    if reward in (None, "", [], {}):
        reward = _walk_find_value(mine, ["reward", "rewards"])
    reward = _parse_reward_obj(reward)

    if isinstance(reward, dict):
        parts = []
        gold = reward.get("gold")
        ore = reward.get("mine_ore")
        if isinstance(gold, dict) and gold.get("amount") not in (None, ""):
            parts.append(f"{_fmt_number_vn(gold.get('amount'))} vàng")
        if isinstance(ore, dict) and ore.get("amount") not in (None, ""):
            parts.append(f"{_fmt_number_vn(ore.get('amount'))} khoáng")

        # Nếu sau này có item/random reward, hiện thêm gọn nhưng không làm lỗi app.
        extra_parts = []
        for key, val in reward.items():
            if key in ("gold", "mine_ore"):
                continue
            if isinstance(val, dict):
                amount = val.get("amount") or val.get("num") or val.get("count") or ""
                sign = val.get("sign") or val.get("id") or val.get("name") or key
                if amount not in (None, ""):
                    extra_parts.append(f"{sign} x{_fmt_number_vn(amount)}")
                else:
                    extra_parts.append(str(sign))
            elif val not in (None, "", [], {}):
                extra_parts.append(f"{key}: {val}")
        if extra_parts:
            parts.append("Item: " + ", ".join(extra_parts[:2]))
        return " • ".join(parts) if parts else "Không có"

    if isinstance(reward, list):
        parts = []
        for item in reward[:3]:
            item = _parse_reward_obj(item)
            if isinstance(item, dict):
                sign = item.get("sign") or item.get("id") or item.get("name") or item.get("key")
                amount = item.get("amount") or item.get("num") or item.get("count") or ""
                if sign:
                    parts.append(f"{sign} x{_fmt_number_vn(amount)}" if amount not in (None, "") else str(sign))
            elif item not in (None, "", [], {}):
                parts.append(str(item))
        return ", ".join(parts) if parts else "Không có"

    # Fallback cũ nếu API đổi tên field.
    value = _walk_find_value(mine, [
        "material", "materials", "resource", "resources", "ore", "ores",
        "item", "items", "drop", "drops", "product", "sign"
    ])
    if isinstance(value, dict):
        sign = value.get("sign") or value.get("id") or value.get("key") or value.get("name")
        return str(sign or value)[:40]
    if isinstance(value, list):
        return ", ".join(str(x) for x in value[:3]) or "Không có"
    if value not in (None, "", [], {}):
        return str(value)[:40]
    return "Không có"

def run_ui(fn):
    app.after(0, fn)

def btn_state(btn, state):
    run_ui(lambda: btn.configure(state=state))


class ScrollableDropdown(ctk.CTkFrame):
    """Dropdown dark kiểu CTkOptionMenu nhưng có thanh cuộn và lăn chuột."""
    def __init__(self, parent, variable, values, width=260, height=38, max_height=360, command=None):
        super().__init__(parent, fg_color="transparent")
        self.variable = variable
        self.values = list(values)
        self.width = width
        self.height = height
        self.max_height = max_height
        self.command = command
        self.popup = None
        self.button = ctk.CTkButton(
            self,
            text=self._short_text(variable.get()),
            width=width,
            height=height,
            anchor="w",
            fg_color="#1f6aa5",
            hover_color="#155b93",
            text_color="white",
            corner_radius=8,
            font=("Arial", 13),
            command=self.toggle,
        )
        self.button.pack(fill="x")
        self.arrow = ctk.CTkLabel(self.button, text="⌄", font=("Arial", 18, "bold"), text_color="white")
        self.arrow.place(relx=0.94, rely=0.48, anchor="center")
        self.variable.trace_add("write", self._sync_text)

    def _short_text(self, text):
        text = str(text or "")
        return text if len(text) <= 34 else text[:31] + "..."

    def _sync_text(self, *args):
        try:
            self.button.configure(text=self._short_text(self.variable.get()))
        except Exception:
            pass

    def configure_values(self, values):
        self.values = list(values)
        if self.variable.get() not in self.values and self.values:
            self.variable.set(self.values[0])

    def close(self, event=None):
        if self.popup is not None:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None

    def toggle(self):
        if self.popup is not None:
            self.close(); return
        self.open()

    def open(self):
        self.close()
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 4
        popup_h = min(self.max_height, max(90, len(self.values) * 36 + 14))
        self.popup = ctk.CTkToplevel(self)
        self.popup.overrideredirect(True)
        self.popup.attributes("-topmost", True)
        self.popup.geometry(f"{self.width}x{popup_h}+{x}+{y}")
        outer = ctk.CTkFrame(self.popup, fg_color="#111111", corner_radius=10, border_width=1, border_color="#2d8cff")
        outer.pack(fill="both", expand=True)
        scroll = ctk.CTkScrollableFrame(
            outer,
            width=self.width - 10,
            height=popup_h - 10,
            fg_color="#111111",
            scrollbar_button_color="#1f6aa5",
            scrollbar_button_hover_color="#2d8cff",
        )
        scroll.pack(fill="both", expand=True, padx=5, pady=5)

        def wheel(e):
            try:
                scroll._parent_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except Exception:
                pass
            return "break"

        scroll.bind("<MouseWheel>", wheel)
        scroll.bind("<Button-4>", lambda e: scroll._parent_canvas.yview_scroll(-1, "units"))
        scroll.bind("<Button-5>", lambda e: scroll._parent_canvas.yview_scroll(1, "units"))

        cur = self.variable.get()
        for val in self.values:
            selected = (val == cur)
            b = ctk.CTkButton(
                scroll,
                text=val,
                height=32,
                anchor="w",
                fg_color="#1f6aa5" if selected else "transparent",
                hover_color="#26384a",
                text_color="white",
                corner_radius=6,
                font=("Arial", 13),
                command=lambda v=val: self.select(v),
            )
            b.pack(fill="x", padx=2, pady=1)
            b.bind("<MouseWheel>", wheel)
        self.popup.bind("<Escape>", self.close)
        self.popup.focus_force()
        self.popup.bind("<FocusOut>", lambda e: self.after(120, self.close))

    def select(self, value):
        self.variable.set(value)
        self.close()
        if self.command:
            self.command(value)


def vn_key(text):
    rep = {
        "à":"a","á":"a","ạ":"a","ả":"a","ã":"a","â":"a","ầ":"a","ấ":"a","ậ":"a","ẩ":"a","ẫ":"a","ă":"a","ằ":"a","ắ":"a","ặ":"a","ẳ":"a","ẵ":"a",
        "è":"e","é":"e","ẹ":"e","ẻ":"e","ẽ":"e","ê":"e","ề":"e","ế":"e","ệ":"e","ể":"e","ễ":"e",
        "ì":"i","í":"i","ị":"i","ỉ":"i","ĩ":"i",
        "ò":"o","ó":"o","ọ":"o","ỏ":"o","õ":"o","ô":"o","ồ":"o","ố":"o","ộ":"o","ổ":"o","ỗ":"o","ơ":"o","ờ":"o","ớ":"o","ợ":"o","ở":"o","ỡ":"o",
        "ù":"u","ú":"u","ụ":"u","ủ":"u","ũ":"u","ư":"u","ừ":"u","ứ":"u","ự":"u","ử":"u","ữ":"u",
        "ỳ":"y","ý":"y","ỵ":"y","ỷ":"y","ỹ":"y","đ":"d",
    }
    text = str(text or "").lower().strip()
    return "".join(rep.get(ch, ch) for ch in text)

def level_aliases(level):
    k = vn_key(level)
    aliases = {k, k.replace(" tang ", " ").replace(" dinh phong", " dp")}
    parts = level.split()
    if len(parts) >= 3:
        realm = " ".join(parts[:-2]) if parts[-2] == "Tầng" else " ".join(parts[:-2])
    realm_name = level.rsplit(" ", 2)[0] if "Tầng" in level else level.replace(" Đỉnh Phong", "")
    realm_words = vn_key(realm_name).split()
    initials = "".join(w[0] for w in realm_words if w)
    if "Tầng" in level:
        num = level.split("Tầng")[-1].strip()
        aliases.add(f"{initials}{num}")
        aliases.add(f"{vn_key(realm_name)} {num}")
    elif "Đỉnh Phong" in level:
        aliases.add(f"{initials}dp")
        aliases.add(f"{vn_key(realm_name)} dp")
        aliases.add(f"{vn_key(realm_name)} dinh phong")
    return aliases

LEVEL_SEARCH = {lvl: level_aliases(lvl) for lvl in LEVELS}

class LevelSearchBox(ctk.CTkFrame):
    """Ô nhập tìm cấp độ: gõ không dấu/viết tắt, Enter chọn gợi ý đầu."""
    def __init__(self, parent, variable, values, width=260, placeholder="VD: chân tiên 1 / ct1"):
        super().__init__(parent, fg_color="transparent")
        self.variable = variable
        self.values = list(values)
        self.width = width
        self.suggestions = []
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            width=width,
            height=40,
            fg_color="#2b2f33",
            border_color="#565b5e",
            text_color="white",
        )
        self.entry.pack(fill="x")
        self.entry.insert(0, variable.get())
        self.box = ctk.CTkFrame(self, fg_color="#111111", corner_radius=10, border_width=1, border_color="#2d8cff")
        self.entry.bind("<KeyRelease>", self.on_type)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.bind("<FocusIn>", self.on_type)
        self.entry.bind("<Escape>", lambda e: self.hide())
        self.entry.bind("<FocusOut>", lambda e: self.after(180, self.hide))

    def hide(self):
        self.box.pack_forget()

    def match_values(self, query):
        q = vn_key(query)
        if not q:
            return []
        scored = []
        for lvl in self.values:
            aliases = LEVEL_SEARCH.get(lvl) or level_aliases(lvl)
            best = 999
            for a in aliases:
                if a == q:
                    best = 0; break
                if a.startswith(q):
                    best = min(best, 1)
                elif q in a:
                    best = min(best, 2)
            if best < 999:
                scored.append((best, self.values.index(lvl), lvl))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [x[2] for x in scored[:6]]

    def on_type(self, event=None):
        # Khi Enter/Escape thì không render lại gợi ý.
        if event is not None and getattr(event, "keysym", "") in ("Return", "Escape"):
            return
        q = self.entry.get().strip()
        self.suggestions = self.match_values(q)
        clear(self.box)
        if not self.suggestions:
            self.hide(); return
        self.box.pack(fill="x", pady=(6, 0))
        for idx, lvl in enumerate(self.suggestions):
            b = ctk.CTkButton(
                self.box,
                text=lvl,
                width=self.width - 12,
                height=30,
                anchor="w",
                fg_color="#1f6aa5" if idx == 0 else "transparent",
                hover_color="#26384a",
                text_color="white",
                corner_radius=6,
                font=("Arial", 13),
                command=lambda v=lvl: self.select(v),
            )
            b.pack(fill="x", padx=6, pady=(6 if idx == 0 else 1, 1))

    def on_enter(self, event=None):
        typed = self.entry.get().strip()
        if typed in self.values:
            self.select(typed)
        elif self.suggestions:
            self.select(self.suggestions[0])
        else:
            matches = self.match_values(typed)
            if matches:
                self.select(matches[0])
        return "break"

    def select(self, value):
        self.variable.set(value)
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.hide()

def parse_info(raw):
    if isinstance(raw, str):
        try: return json.loads(raw)
        except: return {}
    return raw or {}

def level_name(num):
    # API game_exp bắt đầu từ key Lv.2, nhưng level.num trong info của nhân vật
    # đang lệch so với index cũ. Anh báo Lv.90 = Chân Tiên 1, nên phần hiển thị
    # GPS dùng index = level.num để khớp cảnh giới trong game.
    try:
        i = int(num)
        if 0 <= i < len(LEVELS):
            return f"{LEVELS[i]} (Lv.{num})"
    except Exception:
        pass
    return f"Lv.{num}"

ctk.CTkLabel(app, text="Tool lỏ", font=("Arial", 32, "bold")).pack(pady=(18, 8))
tab_view = ctk.CTkTabview(app, width=1040, height=660)
tab_view.pack(padx=18, pady=0, fill="both", expand=True)
tab0 = tab_view.add("Danh Sách Tông")
tab1 = tab_view.add("Điểm Tông Môn Chiến")
tab2 = tab_view.add("GPS Khoáng")
tab3 = tab_view.add("Tính EXP")
tab4 = tab_view.add("Tính KTL")
tab5 = tab_view.add("Chợ")

# ---------------- TAB 0 ----------------
frame0_top = ctk.CTkFrame(tab0, fg_color="transparent")
frame0_top.pack(pady=10)
list_guilds = ctk.CTkScrollableFrame(tab0, width=990, height=540, fg_color="transparent")
list_guilds.pack(fill="both", expand=True, padx=8, pady=8)

def render_guilds(items):
    clear(list_guilds)
    head = card(list_guilds)
    header_row = ctk.CTkFrame(head, fg_color="transparent")
    header_row.pack(fill="x", padx=16, pady=(12, 10))
    ctk.CTkLabel(
        header_row,
        text=f"Danh sách tông môn — {len(items)} tông",
        font=("Arial", 19, "bold"),
        text_color=BLUE,
        anchor="w"
    ).pack(side="left", fill="x", expand=True)
    ctk.CTkLabel(
        header_row,
        text="Mỗi dòng có nút Copy ID ở cuối.",
        font=("Arial", 13),
        text_color=MUTED,
        anchor="e"
    ).pack(side="right")

    if not items:
        empty_card(list_guilds, "Không có dữ liệu tông môn.")
        return

    for item in items:
        # item = (guild_id, guild_tag, guild_name). Tương thích ngược nếu thiếu tag.
        if len(item) == 3:
            gid, tag, name = item
        else:
            gid, name = item
            tag = ""
        gid = str(gid).strip()
        tag = str(tag).strip()
        name = str(name).strip() or "Unknown"
        # Dòng tên vàng chỉ hiển thị tên tông môn; tag viết tắt đã có badge riêng bên dưới.
        display_name = name

        row = ctk.CTkFrame(list_guilds, fg_color=BG_CARD, corner_radius=15, border_width=1, border_color=BORDER)
        row.pack(fill="x", padx=12, pady=6)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=16, pady=12)

        ctk.CTkLabel(
            left,
            text=display_name,
            font=("Arial", 17, "bold"),
            text_color=YELLOW,
            anchor="w"
        ).pack(anchor="w")

        meta = ctk.CTkFrame(left, fg_color="transparent")
        meta.pack(anchor="w", pady=(6, 0))
        if tag:
            ctk.CTkLabel(meta, text=tag, fg_color="#0b61c9", corner_radius=8,
                         font=("Arial", 12, "bold"), text_color="white", padx=9, pady=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(meta, text=f"ID tông: {gid}", fg_color="#303236", corner_radius=8,
                     font=("Arial", 12, "bold"), text_color="#dfe9f3", padx=9, pady=3).pack(side="left")

        ctk.CTkButton(
            row,
            text="Copy ID",
            width=86,
            height=34,
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            command=lambda x=gid: copy_to_clipboard(x)
        ).pack(side="right", padx=16, pady=12)

def load_all_guilds_worker():
    run_ui(lambda: empty_card(list_guilds, "Đang tải danh sách tông môn..."))
    try:
        rows = requests.get(URL_GUILD, timeout=20).json().get("data", [])
        guild_map = {}
        for row in rows:
            info = parse_info(row.get("info", "{}"))
            g = info.get("guild") or {}
            gid = str(g.get("id", ""))
            name = g.get("name", "Unknown")
            tag = g.get("tag") or g.get("short_name") or g.get("short") or g.get("sign") or ""
            if gid:
                guild_map[gid] = (gid, str(tag).strip(), name)
        items = sorted(guild_map.values(), key=lambda x: x[2].lower())
        run_ui(lambda: render_guilds(items) if items else empty_card(list_guilds, "Không lấy được danh sách tông."))
    except Exception as e:
        run_ui(lambda: empty_card(list_guilds, "Lỗi kết nối: " + str(e)))
    btn_state(btn_load_guilds, "normal")

def load_all_guilds():
    btn_load_guilds.configure(state="disabled")
    threading.Thread(target=load_all_guilds_worker, daemon=True).start()
btn_load_guilds = ctk.CTkButton(frame0_top, text="Tải danh sách tông", width=190, height=40, command=load_all_guilds)
btn_load_guilds.pack(padx=10)
empty_card(list_guilds, "Bấm tải để xem danh sách tông môn.")

# ---------------- TAB 1 ----------------
frame1_top = ctk.CTkFrame(tab1, fg_color="transparent")
frame1_top.pack(pady=10)
entry_guild = ctk.CTkEntry(frame1_top, placeholder_text="Nhập Guild ID", width=260, height=40)
entry_guild.pack(side="left", padx=8)
list_score = ctk.CTkScrollableFrame(tab1, width=990, height=540, fg_color="transparent")
list_score.pack(fill="both", expand=True, padx=8, pady=8)

def render_scores(guild_name, guild_id, result):
    clear(list_score)

    copy_lines = [f"{p.get('id', '')} - {p.get('name', '')}" for p in result]
    copy_payload = "\n".join(copy_lines)

    head = card(list_score)
    top = ctk.CTkFrame(head, fg_color="transparent")
    top.pack(fill="x", padx=16, pady=(12, 8))
    ctk.CTkLabel(
        top,
        text=str(guild_name),
        font=("Arial", 20, "bold"),
        text_color=YELLOW,
        anchor="w"
    ).pack(side="left", fill="x", expand=True)
    ctk.CTkButton(
        top,
        text="Copy ID + tên toàn bộ",
        width=180,
        height=34,
        fg_color="#3a3a3a",
        hover_color="#4a4a4a",
        command=lambda text=copy_payload: copy_to_clipboard(text)
    ).pack(side="right")

    info = ctk.CTkFrame(head, fg_color="transparent")
    info.pack(fill="x", padx=16, pady=(0, 12))
    ctk.CTkLabel(info, text=f"Guild ID: {guild_id}", fg_color="#303236", corner_radius=8,
                 font=("Arial", 13, "bold"), text_color="#dfe9f3", padx=10, pady=4).pack(side="left", padx=(0, 8))
    ctk.CTkLabel(info, text=f"Thành viên: {len(result)}", fg_color="#0b61c9", corner_radius=8,
                 font=("Arial", 13, "bold"), text_color="white", padx=10, pady=4).pack(side="left")

    if not result:
        empty_card(list_score, "Không có dữ liệu thành viên.")
        return

    for i, p in enumerate(result, 1):
        if i == 1:
            rank_text, rank_color, border = "🥇 #1", "#ffcc33", "#9b7a11"
        elif i == 2:
            rank_text, rank_color, border = "🥈 #2", "#d9d9d9", "#777777"
        elif i == 3:
            rank_text, rank_color, border = "🥉 #3", "#cd7f32", "#7b4c1f"
        else:
            rank_text, rank_color, border = f"#{i}", MUTED, BORDER

        row = ctk.CTkFrame(list_score, fg_color=BG_CARD, corner_radius=15, border_width=1, border_color=border)
        row.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(row, text=rank_text, width=78, anchor="w",
                     font=("Arial", 16, "bold"), text_color=rank_color).pack(side="left", padx=(16, 8), pady=12)

        mid = ctk.CTkFrame(row, fg_color="transparent")
        mid.pack(side="left", fill="x", expand=True, pady=10)
        ctk.CTkLabel(mid, text=str(p.get('name', 'Unknown')), anchor="w",
                     font=("Arial", 16, "bold"), text_color="white").pack(anchor="w")
        ctk.CTkLabel(mid, text=f"ID: {p.get('id', '')}", anchor="w",
                     font=("Arial", 13, "bold"), text_color="#dfe9f3").pack(anchor="w", pady=(3, 0))

        ctk.CTkLabel(row, text=f"{int(p.get('score', 0)):,} điểm", anchor="e",
                     font=("Arial", 15, "bold"), text_color=BLUE).pack(side="right", padx=16)

def fetch_guild_worker():
    q = entry_guild.get().strip()
    if not q:
        run_ui(lambda: empty_card(list_score, "Vui lòng nhập Guild ID.")); btn_state(btn_guild,"normal"); return
    if not q.isdigit():
        run_ui(lambda: empty_card(list_score, "Hiện tại chỉ hỗ trợ tìm bằng Guild ID.")); btn_state(btn_guild,"normal"); return
    run_ui(lambda: empty_card(list_score, "Đang tải điểm tông môn chiến..."))
    try:
        guild_id = q
        members_raw = requests.get(URL_GUILD_MEMBER.format(guild=guild_id), timeout=15).json().get("data", [])
        if not members_raw:
            run_ui(lambda: empty_card(list_score, "Không tìm thấy thành viên guild.")); btn_state(btn_guild,"normal"); return
        score_raw = requests.get(URL_GUILD, timeout=15).json().get("data", [])
        score_map = {}
        for row in score_raw:
            info = parse_info(row.get("info", "{}")); cid = str(info.get("id", ""))
            if cid: score_map[cid] = int(row.get("score", 0) or 0)
        result, guild_name = [], "Unknown"
        for mem in members_raw:
            mdata = parse_info(mem.get("info", "{}"))
            cid = str(mem.get("character") or mdata.get("id", ""))
            name = mdata.get("name") or mdata.get("nickname") or mem.get("name") or "Unknown"
            if mdata.get("guild"): guild_name = mdata["guild"].get("name", guild_name)
            result.append({"id": cid, "name": name, "score": score_map.get(cid, 0)})
        result.sort(key=lambda x: x["score"], reverse=True)
        run_ui(lambda: render_scores(guild_name, guild_id, result))
    except Exception as e:
        run_ui(lambda: empty_card(list_score, "Lỗi kết nối: " + str(e)))
    btn_state(btn_guild,"normal")

def search_guild():
    btn_guild.configure(state="disabled")
    threading.Thread(target=fetch_guild_worker, daemon=True).start()
btn_guild = ctk.CTkButton(frame1_top, text="Tìm Guild", command=search_guild, height=40, width=120)
btn_guild.pack(side="left", padx=8)
empty_card(list_score, "Nhập Guild ID rồi bấm tìm.")

# ---------------- TAB 2 GPS ----------------
gps_saved = {}; gps_choice_var = ctk.StringVar(value="")
def load_gps_saved():
    global gps_saved
    try:
        with open(GPS_SAVE_FILE, "r", encoding="utf-8") as f: gps_saved = json.load(f)
    except: gps_saved = {}
def save_gps_saved():
    try:
        with open(GPS_SAVE_FILE, "w", encoding="utf-8") as f: json.dump(gps_saved, f, ensure_ascii=False, indent=2)
    except: pass
def refresh_gps_menu():
    vals = [f"{cid} - {name}" for cid, name in gps_saved.items()] or ["Chưa có dữ liệu lưu"]
    gps_menu.configure(values=vals); gps_choice_var.set(vals[0])
def select_saved_gps(choice):
    if choice and choice != "Chưa có dữ liệu lưu":
        entry_mine.delete(0,"end"); entry_mine.insert(0, choice.split(" - ")[0].strip())

panel_gps = ctk.CTkFrame(tab2, fg_color="transparent")
panel_gps.pack(fill="both", expand=True)
left_gps = ctk.CTkFrame(panel_gps, width=310, fg_color="transparent")
left_gps.pack(side="left", fill="y", padx=(8,4), pady=8)
right_gps = ctk.CTkScrollableFrame(panel_gps, width=690, height=560, fg_color="transparent")
right_gps.pack(side="left", fill="both", expand=True, padx=(4,8), pady=8)

c_in = card(left_gps)
label(c_in, "GPS Khoáng", 20, "bold", BLUE, pady=(14,4))
label(c_in, "Nhân vật ID", 14, "bold", MUTED, pady=(8,0))
entry_mine = ctk.CTkEntry(c_in, placeholder_text="VD: 20389", width=240, height=40); entry_mine.pack(padx=16, pady=6)
btn_mine = ctk.CTkButton(c_in, text="Tải dữ liệu", height=40, width=240, command=lambda: search_mine()); btn_mine.pack(padx=16, pady=(6,14))
c_save = card(left_gps)
label(c_save, "Lưu nhanh", 16, "bold", BLUE, pady=(14,4))
entry_mine_name = ctk.CTkEntry(c_save, placeholder_text="Tên lưu", width=240, height=38); entry_mine_name.pack(padx=16, pady=6)
def add_gps_saved():
    cid = entry_mine.get().strip(); name = entry_mine_name.get().strip() or "Không tên"
    if not cid: empty_card(right_gps, "Vui lòng nhập ID nhân vật trước khi lưu."); return
    gps_saved[cid] = name; save_gps_saved(); refresh_gps_menu(); empty_card(right_gps, f"Đã lưu {name} ({cid}).")
def delete_gps_saved():
    choice = gps_choice_var.get()
    if not choice or choice == "Chưa có dữ liệu lưu": empty_card(right_gps, "Chưa chọn nhân vật để xóa."); return
    cid = choice.split(" - ")[0].strip(); name = gps_saved.pop(cid, "")
    save_gps_saved(); refresh_gps_menu(); empty_card(right_gps, f"Đã xóa {name} ({cid}).")
row_btn = ctk.CTkFrame(c_save, fg_color="transparent"); row_btn.pack(padx=16, pady=8)
ctk.CTkButton(row_btn, text="Lưu ID", width=112, height=36, command=add_gps_saved).pack(side="left", padx=(0,8))
ctk.CTkButton(row_btn, text="Xóa", width=112, height=36, fg_color="#b73a43", hover_color="#96313a", command=delete_gps_saved).pack(side="left")
label(c_save, "Đã lưu", 14, "bold", MUTED, pady=(6,0))
gps_menu = ctk.CTkOptionMenu(c_save, variable=gps_choice_var, values=["Chưa có dữ liệu lưu"], command=select_saved_gps, width=240, height=38)
gps_menu.pack(padx=16, pady=(6,16))

def render_gps(char, energy, mines, saved_name="", avatar_img=None, dhd_energy=0):
    clear(right_gps)
    name = char.get("name") or saved_name or "Không rõ"
    cid_info = char.get("id") or "?"
    level = level_name((char.get("level") or {}).get("num", "?")) if isinstance(char.get("level"), dict) else "?"
    cp_obj = char.get("cp") if isinstance(char.get("cp"), dict) else {}
    cp = cp_obj.get("total", "?")
    cp_data = cp_obj.get("data", {}) if isinstance(cp_obj.get("data"), dict) else {}
    cp_main = cp_data.get("character", "?")
    cp_pet = cp_data.get("pet", "?")
    cp_friend = cp_data.get("friend", "?")
    guild_obj = char.get("guild") if isinstance(char.get("guild"), dict) else {}
    guild_tag = (guild_obj.get("tag") or guild_obj.get("short_name") or guild_obj.get("short") or guild_obj.get("sign") or "")
    guild_name = (guild_obj.get("name") or "")
    guild_badge = str(guild_tag).strip() or str(guild_name).strip()
    current = energy.get("current", "?") if energy else "?"
    ts = energy.get("time") if energy else None
    dt = datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M:%S") if ts else "Không rõ"
    top = card(right_gps)
    row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=18, pady=16)
    ava = ctk.CTkFrame(row, width=112, height=112, corner_radius=16, border_width=0, fg_color="transparent")
    ava.pack(side="left", padx=(0,18)); ava.pack_propagate(False)
    if avatar_img is not None:
        try:
            avatar_cover = make_avatar_cover(avatar_img, size=112, radius=16, border=2)
            avatar_ctk = ctk.CTkImage(light_image=avatar_cover, dark_image=avatar_cover, size=(112,112))
            avatar_label = ctk.CTkLabel(ava, text="", image=avatar_ctk, width=112, height=112)
            avatar_label.image = avatar_ctk
            avatar_label.pack(fill="both", expand=True)
        except Exception:
            fallback = ctk.CTkFrame(ava, width=112, height=112, corner_radius=16, border_width=2, border_color="#c99600", fg_color="#2b2b2b")
            fallback.pack(fill="both", expand=True); fallback.pack_propagate(False)
            ctk.CTkLabel(fallback, text="👤", font=("Arial", 42)).pack(expand=True)
    else:
        fallback = ctk.CTkFrame(ava, width=112, height=112, corner_radius=16, border_width=2, border_color="#c99600", fg_color="#2b2b2b")
        fallback.pack(fill="both", expand=True); fallback.pack_propagate(False)
        ctk.CTkLabel(fallback, text="👤", font=("Arial", 42)).pack(expand=True)
    mid = ctk.CTkFrame(row, fg_color="transparent"); mid.pack(side="left", fill="both", expand=True)
    label(mid, name, 30, "bold", YELLOW, padx=0, pady=(2,4))
    label(mid, "⚙ Cấp độ: " + level, 17, "normal", "white", padx=0, pady=2)
    badges = ctk.CTkFrame(mid, fg_color="transparent"); badges.pack(anchor="w", pady=8)
    ctk.CTkLabel(badges, text=f"ID: {cid_info}", fg_color="#333333", corner_radius=8, font=("Arial",14,"bold"), padx=10, pady=5).pack(side="left", padx=(0,8))
    ctk.CTkLabel(badges, text=f"🎟 Vé ĐHĐ: {dhd_energy}/1500", fg_color="#333333", corner_radius=8, font=("Arial",14,"bold"), padx=10, pady=5).pack(side="left", padx=(0,8))
    if guild_badge:
        ctk.CTkLabel(badges, text=guild_badge, fg_color="#0b61c9", corner_radius=8, font=("Arial",14,"bold"), padx=10, pady=5).pack(side="left", padx=(0,8))
    if saved_name: ctk.CTkLabel(badges, text=saved_name, fg_color="#3a3a3a", corner_radius=8, font=("Arial",14,"bold"), padx=10, pady=5).pack(side="left", padx=(0,8))
    right = ctk.CTkFrame(row, fg_color="transparent", width=180); right.pack(side="right", fill="y")
    label(right, "⚔ Lực chiến tổng", 16, "bold", RED, padx=0, pady=(10,0))
    label(right, str(cp), 32, "bold", RED, padx=0, pady=(2,6))
    cp_detail = ctk.CTkFrame(right, fg_color="transparent")
    cp_detail.pack(anchor="e", padx=0, pady=(0,2))
    label(cp_detail, f"Nhân vật: {cp_main}", 18, "bold", "#dbeafe", padx=0, pady=(0,1))
    label(cp_detail, f"Pet: {cp_pet}", 18, "bold", "#ffd36a", padx=0, pady=(0,1))
    label(cp_detail, f"Đồng Hành: {cp_friend}", 18, "bold", "#d66a6a", padx=0, pady=(0,1))
    stats = ctk.CTkFrame(top, fg_color="transparent"); stats.pack(fill="x", padx=12, pady=(0,12))
    stat_box(stats, "⛏ Lượt khoáng còn lại", current, BLUE)
    stat_box(stats, "🕒 Cập nhật lúc", dt, "white")
    h = card(right_gps)
    label(h, "💎 Mỏ hiện tại", 20, "bold", BLUE, pady=(16,6))
    if not mines:
        label(h, "Không thấy mỏ đang khai thác.", 15, "normal", MUTED, pady=(0,16))
    for idx, mine in enumerate(mines[:1], 1):
        area = mine.get("area", "?"); rare = mine.get("rare", "?"); rare_text = RARE_LABEL.get(rare, str(rare))
        miner_info = ((mine.get("miner") or {}).get("info") or {})
        miner_name = miner_info.get("name") or "Trống"
        level_num = (miner_info.get("level") or {}).get("num", "?") if isinstance(miner_info.get("level"), dict) else "?"
        c = card(right_gps, fg=BG_CARD2)

        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(head, text=f"Mỏ #{idx}", font=("Arial", 22, "bold"),
                     text_color="white", anchor="w").pack(side="left", padx=(0, 8), pady=0)

        rare_color = RED if rare == 4 else YELLOW
        rare_bg = "#2a1f1f" if rare == 4 else "#2c2617"
        ctk.CTkLabel(head, text=f"{rare_text} • Tầng {area}", fg_color=rare_bg,
                     corner_radius=10, text_color=rare_color,
                     font=("Arial", 13, "bold"), padx=12, pady=6).pack(side="right", padx=(8, 0), pady=0)

        row_info = ctk.CTkFrame(c, fg_color="transparent")
        row_info.pack(fill="x", padx=8, pady=(4, 2))
        mine_stat_box(row_info, "Đang khai", f"{miner_name} (Lv.{level_num})" if miner_name != "Trống" else "Trống", BLUE)
        mine_stat_box(row_info, "Thời gian", get_mine_time_text(mine), YELLOW)

        gold_amount, ore_amount, extra_parts = get_mine_reward_values(mine)
        reward_wrap = ctk.CTkFrame(c, fg_color="#1f2228", corner_radius=12, border_width=1, border_color=BORDER)
        reward_wrap.pack(fill="x", padx=12, pady=(8, 12))
        label(reward_wrap, "Phần thưởng khai khoáng", 13, "bold", MUTED, padx=12, pady=(8, 0))

        reward_row = ctk.CTkFrame(reward_wrap, fg_color="transparent")
        reward_row.pack(fill="x", padx=8, pady=(0, 8))
        reward_value_box(reward_row, "Vàng", gold_amount, "🪙", "#f4d35e", "#2b2415")
        reward_value_box(reward_row, "Khoáng", ore_amount, "⛏", "#8ecbff", "#162638")

        if extra_parts:
            ctk.CTkLabel(reward_wrap, text="🎁 " + ", ".join(extra_parts[:2]),
                         text_color="#a4e5a0", font=("Arial", 13, "bold"),
                         anchor="w").pack(anchor="w", padx=14, pady=(0, 10))

def fetch_mine_worker():
    target = entry_mine.get().strip()
    if not target:
        run_ui(lambda: empty_card(right_gps, "Vui lòng nhập Nhân vật ID."))
        btn_state(btn_mine, "normal")
        return

    # Chỉ call API một lần tại thời điểm bấm nút. Không có vòng lặp realtime.
    run_ui(lambda: empty_card(right_gps, "Đang tải dữ liệu cho ID " + target + "..."))
    try:
        char = {}
        avatar_img = None
        dhd_energy = 0
        energy = {}
        mr = {}

        def get_json(url, timeout=6):
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://cmangax17.com/user/game/dashboard",
                    "Accept": "application/json,text/plain,*/*",
                }
                return requests.get(url, timeout=(3, timeout), headers=headers).json()
            except Exception:
                return {}

        # Gọi song song 3 API chính để không phải chờ tuần tự.
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_char = ex.submit(get_json, URL_CHAR.format(id=target), 5)
            f_energy = ex.submit(get_json, URL_ENERGY.format(character=target), 5)
            f_mine = ex.submit(get_json, URL_MINE.format(target=target), 5)

            char_resp = f_char.result()
            er = f_energy.result()
            mr = f_mine.result()

        if char_resp.get("status") == 1:
            data_block = char_resp.get("data", {})
            char = parse_info(data_block.get("info", "{}"))
            other = parse_info(data_block.get("other", "{}"))
            try:
                dhd_energy = int(((other.get("friend") or {}).get("energy") or 0))
            except Exception:
                dhd_energy = 0

            # Avatar tải sau cùng, timeout ngắn + cache. Fail thì vẫn render card, không treo app.
            try:
                avatar_img = fetch_avatar_pil(char.get("avatar"), char.get("author"))
            except Exception:
                avatar_img = None

        energy = er.get("data", {}) if er.get("status") == 1 else {}

        mines = []
        if mr.get("status") == 1:
            for row in mr.get("data", []):
                data_raw = row.get("data", "{}") if isinstance(row, dict) else "{}"

                # Lấy reward/times thật từ chuỗi raw trước.
                # API có duplicate key: reward/times thật nằm trước, reward=[]/times=0 nằm cuối.
                real_reward, real_times = extract_mine_reward_times_raw(data_raw)

                mine_obj = parse_info(data_raw)
                if not isinstance(mine_obj, dict):
                    mine_obj = {}

                if real_times not in (None, "", [], {}):
                    mine_obj["_mine_times"] = real_times
                elif mine_obj.get("times") not in (None, "", [], {}):
                    try:
                        if float(mine_obj.get("times") or 0) > 0:
                            mine_obj["_mine_times"] = mine_obj.get("times")
                    except Exception:
                        pass

                if real_reward not in (None, "", [], {}):
                    mine_obj["_mine_reward"] = real_reward
                elif mine_obj.get("reward") not in (None, "", [], {}):
                    mine_obj["_mine_reward"] = mine_obj.get("reward")

                mines.append(mine_obj)
        else:
            msg = mr.get("message", "Không rõ") if isinstance(mr, dict) else "Không rõ"
            run_ui(lambda msg=msg: empty_card(right_gps, "Lỗi API mỏ: " + msg))
            btn_state(btn_mine, "normal")
            return

        saved = gps_saved.get(target, "")
        run_ui(lambda: render_gps(char, energy, mines, saved, avatar_img, dhd_energy))

    except Exception as e:
        err = str(e)
        gps_debug_log("GPS ERROR: " + err)
        run_ui(lambda err=err: empty_card(right_gps, "Lỗi kết nối: " + err))

    btn_state(btn_mine, "normal")

def search_mine():
    btn_mine.configure(state="disabled")
    threading.Thread(target=fetch_mine_worker, daemon=True).start()
load_gps_saved(); refresh_gps_menu(); empty_card(right_gps, "Nhập ID rồi bấm tải dữ liệu.")

# ---------------- TAB 3 EXP ----------------
start_var = ctk.StringVar(value=LEVELS[0]); target_var = ctk.StringVar(value=LEVELS[1]); dan_var3 = ctk.StringVar(value="Đan 1 (500 EXP)")
form3 = ctk.CTkFrame(tab3, fg_color="transparent"); form3.pack(side="left", fill="y", padx=8, pady=8)
out3 = ctk.CTkScrollableFrame(tab3, width=680, height=560, fg_color="transparent"); out3.pack(side="left", fill="both", expand=True, padx=8, pady=8)
fc = card(form3); label(fc, "Tính EXP", 20, "bold", BLUE, pady=(14,8))

def add_level_search(title, var):
    label(fc, title, 14, "bold", MUTED, pady=(8,0))
    box = LevelSearchBox(fc, variable=var, values=LEVELS, width=260)
    box.pack(padx=16, pady=6)
    return box

def add_combo(title, var, values):
    label(fc, title, 14, "bold", MUTED, pady=(8,0))
    cb = ScrollableDropdown(fc, variable=var, values=values, width=260, height=38, max_height=260)
    cb.pack(padx=16, pady=6)
    return cb

start_combo = add_level_search("Cấp hiện tại", start_var)
target_combo = add_level_search("Cấp mục tiêu", target_var)
label(fc, "EXP hiện có ở cấp hiện tại", 14, "bold", MUTED, pady=(8,0)); entry_current_exp = ctk.CTkEntry(fc, width=260); entry_current_exp.pack(padx=16, pady=6); entry_current_exp.insert(0,"0")
label(fc, "Buff server (%)", 14, "bold", MUTED, pady=(8,0)); entry_buff = ctk.CTkEntry(fc, width=260); entry_buff.pack(padx=16, pady=6); entry_buff.insert(0,"0")
dan_combo = add_combo("Loại đan", dan_var3, list(DAN_EXP.keys()))
label(fc, "Giá mỗi đan (tuỳ chọn)", 14, "bold", MUTED, pady=(8,0)); entry_dan_price = ctk.CTkEntry(fc, width=260); entry_dan_price.pack(padx=16, pady=6)

def try_parse_exp(character_data):
    new_map = {}
    if isinstance(character_data, dict):
        # API game_exp có key bắt đầu từ Lv.2 nhưng level.num của nhân vật
        # khớp trực tiếp với index LEVELS: Lv.90 = LEVELS[90] = Chân Tiên Tầng 1.
        # Vì vậy KHÔNG trừ min_key nữa, nếu không sẽ bị lệch 2 cấp và tính EXP ra 0/sai.
        num_keys = []
        for k in character_data.keys():
            if str(k).isdigit():
                num_keys.append(int(k))
        if num_keys:
            num_keys.sort()
            for k in num_keys:
                idx = k
                if 0 <= idx < len(LEVELS):
                    try:
                        new_map[LEVELS[idx]] = int(character_data[str(k)])
                    except Exception:
                        try:
                            new_map[LEVELS[idx]] = int(character_data[k])
                        except Exception:
                            pass
    return new_map


def load_exp_data():
    global exp_loaded, exp_map
    if exp_loaded:
        return True
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        resp = requests.get(URL_EXP, timeout=15, headers=headers).json()

        candidates = []
        if isinstance(resp, dict):
            data = resp.get("data")
            if isinstance(data, dict):
                candidates.extend([
                    data.get("character"),
                    data.get("exp"),
                    data.get("game_exp"),
                    data,
                ])
            candidates.extend([resp.get("character"), resp.get("game_exp"), resp])

        parsed = {}
        for c in candidates:
            if isinstance(c, dict):
                parsed = try_parse_exp(c)
                if parsed:
                    break

        if not parsed:
            return False

        for lvl in LEVELS:
            exp_map[lvl] = 0
        exp_map.update(parsed)
        exp_loaded = True
        return True
    except Exception:
        return False

def resolve_level_from_box(box, var):
    typed = box.entry.get().strip()
    if typed in LEVELS:
        var.set(typed); return typed
    matches = box.match_values(typed)
    if matches:
        box.select(matches[0]); return matches[0]
    return var.get()

def calc_exp():
    clear(out3)
    if not load_exp_data(): empty_card(out3, "Không tải được bảng EXP."); return
    try:
        start_level = resolve_level_from_box(start_combo, start_var)
        target_level = resolve_level_from_box(target_combo, target_var)
        si, ti = LEVELS.index(start_level), LEVELS.index(target_level)
        cur, buff = int(entry_current_exp.get() or 0), float(entry_buff.get() or 0)
        if ti <= si: empty_card(out3, "Cấp mục tiêu phải cao hơn cấp hiện tại."); return
        # exp_map[cấp] là EXP cần để qua cấp đó. Từ cấp hiện tại đến mục tiêu
        # chỉ cộng từ si -> ti-1, rồi trừ EXP hiện có ở cấp hiện tại.
        total_exp = sum(exp_map.get(LEVELS[i], 0) for i in range(si, ti))
        need_raw = max(total_exp - cur, 0)
        real_per_dan = DAN_EXP[dan_var3.get()] * (1 + buff/100)
        pills = math.ceil(need_raw / real_per_dan) if real_per_dan > 0 else 0
        c = card(out3); label(c, "Kết quả EXP", 22, "bold", BLUE, pady=(14,8))
        row = ctk.CTkFrame(c, fg_color="transparent"); row.pack(fill="x", padx=10, pady=8)
        stat_box(row, "Từ", start_level, "white"); stat_box(row, "Đến", target_level, YELLOW)
        row2 = ctk.CTkFrame(c, fg_color="transparent"); row2.pack(fill="x", padx=10, pady=8)
        stat_box(row2, "EXP còn cần", f"{need_raw:,}", BLUE); stat_box(row2, "Mỗi đan sau buff", f"{real_per_dan:,.0f}", YELLOW); stat_box(row2, "Số đan cần", f"{pills:,}", RED)
        price = entry_dan_price.get().strip()
        if price:
            stat_box(row2, "Tổng giá", f"{pills * float(price):,.0f}", "white")
    except Exception as e:
        empty_card(out3, "Lỗi tính EXP: " + str(e))
ctk.CTkButton(fc, text="Tính EXP", width=260, height=42, command=calc_exp).pack(padx=16, pady=18)
empty_card(out3, "Chọn cấp, nhập EXP hiện có rồi bấm Tính EXP.")

# ---------------- TAB 4 KTL ----------------
form4 = ctk.CTkFrame(tab4, fg_color="transparent"); form4.pack(side="left", fill="y", padx=8, pady=8)
out4 = ctk.CTkScrollableFrame(tab4, width=680, height=560, fg_color="transparent"); out4.pack(side="left", fill="both", expand=True, padx=8, pady=8)
fc4 = card(form4); label(fc4, "Tính KTL", 20, "bold", BLUE, pady=(14,8))
def add_entry4(title, default=""):
    label(fc4, title, 14, "bold", MUTED, pady=(8,0)); e=ctk.CTkEntry(fc4, width=260); e.pack(padx=16, pady=6); e.insert(0, default); return e
entry_target_ktl = add_entry4("KTL mục tiêu", "25600")
entry_current_ktl = add_entry4("KTL hiện có", "0")
pb_var = ctk.StringVar(value="PB2")
label(fc4, "Loại PB", 14, "bold", MUTED, pady=(8,0)); ctk.CTkOptionMenu(fc4, variable=pb_var, values=list(PB_KTL.keys()), width=260).pack(padx=16, pady=6)
entry_pb_price = add_entry4("Giá mỗi PB", "5")

def calc_ktl():
    clear(out4)
    try:
        target, current = int(entry_target_ktl.get() or 0), int(entry_current_ktl.get() or 0)
        val, price = PB_KTL[pb_var.get()], float(entry_pb_price.get() or 0)
        lack = max(target-current, 0); need = math.ceil(lack / val) if val else 0
        c=card(out4); label(c, "Kết quả KTL", 22, "bold", BLUE, pady=(14,8))
        row=ctk.CTkFrame(c, fg_color="transparent"); row.pack(fill="x", padx=10, pady=8)
        stat_box(row, "Còn thiếu", f"{lack:,} KTL", RED); stat_box(row, "Quy đổi", f"1 {pb_var.get()} = {val:,} KTL", YELLOW)
        row2=ctk.CTkFrame(c, fg_color="transparent"); row2.pack(fill="x", padx=10, pady=8)
        stat_box(row2, "Số PB cần", f"{need:,}", BLUE); stat_box(row2, "Tổng LT", f"{need*price:,.0f}", "white")
    except Exception as e: empty_card(out4, "Lỗi tính KTL: " + str(e))
ctk.CTkButton(fc4, text="Tính KTL", width=260, height=42, command=calc_ktl).pack(padx=16, pady=18)
empty_card(out4, "Nhập KTL mục tiêu, KTL hiện có rồi bấm Tính KTL.")


# ---------------- TAB 5 CHỢ ----------------
# Bộ lọc chợ mô phỏng filter.php của game:
# status, sort, type, special_type, special_level, special_data, sign, owner.
MARKET_ITEM_LIST = [
    "item_box_treasure_1",
    "item_box_treasure_2",
    "item_box_treasure_3",
    "item_box_treasure_4",
    "item_box_treasure_5",
    "item_box_treasure_6",
    "item_box_treasure_7",
    "item_box_treasure_8",
    "item_box_treasure_9",
    "item_box_weapon_1",
    "item_box_weapon_2",
    "item_box_weapon_3",
    "item_box_weapon_4",
    "item_box_weapon_5",
    "item_box_weapon_6",
    "item_box_weapon_7",
    "item_box_weapon_8",
    "item_box_weapon_9",
    "item_box_armor_1",
    "item_box_armor_2",
    "item_box_armor_3",
    "item_box_armor_4",
    "item_box_armor_5",
    "item_box_armor_6",
    "item_box_armor_7",
    "item_box_armor_8",
    "item_box_armor_9",
    "item_box_accessory_1",
    "item_box_accessory_2",
    "item_box_accessory_3",
    "item_box_accessory_4",
    "item_box_accessory_5",
    "item_box_accessory_6",
    "item_box_accessory_7",
    "item_box_accessory_8",
    "item_box_accessory_9",
    "item_potion_1",
    "item_potion_2",
    "item_potion_3",
    "item_potion_4",
    "item_potion_5",
    "item_potion_6",
    "item_potion_7",
    "item_potion_8",
    "item_skill_1_1",
    "item_skill_1_2",
    "item_skill_1_3",
    "item_skill_1_4",
    "item_skill_1_5",
    "item_skill_2_1",
    "item_skill_2_2",
    "item_skill_2_3",
    "item_skill_2_4",
    "item_skill_2_5",
    "item_skill_3_1",
    "item_skill_3_2",
    "item_skill_3_3",
    "item_skill_3_4",
    "item_skill_3_5",
    "item_skill_4_1",
    "item_skill_4_2",
    "item_skill_4_3",
    "item_skill_4_4",
    "item_skill_4_5",
    "item_medicinal_exp_1",
    "item_medicinal_exp_2",
    "item_medicinal_exp_3",
    "item_medicinal_exp_4",
    "item_medicinal_exp_5",
    "item_medicinal_exp_6",
    "item_medicinal_exp_7",
    "item_medicinal_exp_8",
    "item_medicinal_exp_9",
    "item_medicinal_exp_10",
    "item_medicinal_upgrade_1",
    "item_medicinal_upgrade_2",
    "item_medicinal_upgrade_3",
    "item_medicinal_upgrade_4",
    "item_medicinal_upgrade_5",
    "item_medicinal_upgrade_6",
    "item_medicinal_upgrade_7",
    "item_medicinal_upgrade_8",
    "item_medicinal_upgrade_9",
    "item_medicinal_point_plus",
    "material_ore_weapon_1",
    "material_ore_weapon_2",
    "material_ore_weapon_3",
    "material_ore_weapon_4",
    "material_ore_weapon_5",
    "material_ore_weapon_6",
    "material_ore_weapon_7",
    "material_ore_weapon_8",
    "material_ore_weapon_9",
    "material_ore_armor_1",
    "material_ore_armor_2",
    "material_ore_armor_3",
    "material_ore_armor_4",
    "material_ore_armor_5",
    "material_ore_armor_6",
    "material_ore_armor_7",
    "material_ore_armor_8",
    "material_ore_armor_9",
    "material_ore_accessory_1",
    "material_ore_accessory_2",
    "material_ore_accessory_3",
    "material_ore_accessory_4",
    "material_ore_accessory_5",
    "material_ore_accessory_6",
    "material_ore_accessory_7",
    "material_ore_accessory_8",
    "material_ore_accessory_9",
    "material_herb_1",
    "material_herb_2",
    "material_herb_3",
    "material_herb_4",
    "material_herb_5",
    "material_herb_6",
    "material_herb_7",
    "material_herb_8",
    "material_herb_9",
    "material_herb_upgrade_1",
    "material_herb_upgrade_2",
    "material_herb_upgrade_3",
    "material_herb_upgrade_4",
    "material_herb_upgrade_5",
    "material_herb_upgrade_6",
    "material_herb_upgrade_7",
    "material_herb_upgrade_8",
    "material_herb_upgrade_9",
    "material_death_soul_1",
    "material_death_soul_2",
    "material_death_soul_3",
    "material_death_soul_4",
    "material_death_soul_5",
    "material_death_soul_6",
    "material_death_soul_7",
    "material_death_soul_8",
    "material_death_soul_9",
    "material_guild_ore",
    "material_equipment_upgrade_1",
    "material_equipment_upgrade_2",
    "material_equipment_upgrade_3",
    "material_add_option",
    "material_job_exp_1",
    "material_job_exp_2",
    "material_job_exp_3",
    "material_job_exp_4",
    "item_medicinal_upgrade_king",
    "item_medicinal_talent_plus",
    "material_guild_quest_bar",
    "material_guild_quest_ore",
    "material_guild_quest_cloth",
    "material_guild_quest_wood",
    "material_guild_quest_fish",
    "material_guild_quest_vegetable",
    "material_guild_quest_meat",
    "material_guild_quest_seed",
    "item_guild_boss_1",
    "item_guild_boss_2",
    "item_box_book_1",
    "item_box_book_2",
    "item_box_book_3",
    "item_medicinal_level_4",
    "item_medicinal_level_5",
    "item_medicinal_level_6",
    "material_egg_normal",
    "material_egg_rare",
    "material_egg_legendary",
    "item_pet_exp_chest",
    "material_pet_evolve_1",
    "material_pet_evolve_2",
    "material_pet_evolve_3",
    "material_pet_evolve_4",
    "material_pet_skill_1",
    "material_pet_skill_2",
    "material_pet_skill_3",
    "material_pet_skill_4",
    "item_box_pet_equipment_1",
    "item_box_pet_equipment_2",
    "item_box_pet_equipment_3",
    "item_box_pet_equipment_4",
    "item_box_pet_equipment_5",
    "item_box_pet_equipment_6",
    "item_box_pet_equipment_7",
    "item_box_pet_equipment_8",
    "item_box_pet_equipment_9",
    "material_egg_mystic",
    "item_pet_heart_bag",
    "item_wanted_order",
    "material_egg_super_fragment",
    "material_soul_blossom"
]
MARKET_EQUIPMENT_TYPES = [
    "weapon", "armor", "helmet", "gloves", "boots", "ring", "amulet", "belt", "pedant", "treasure", "book",
    "pet_head", "pet_body_top", "pet_body_bottom", "pet_foot_right", "pet_foot_left", "pet_tail", "pet_hand_left", "pet_hand_right"
]
MARKET_BOOK_WEAPONS = ["battle_axe","bow","claw","crescents","dual_sword","fan","flute","harp","lute","medium_scimitar","mini_scimitar","moon_blade","pen","robot","rope_whip","scimitar","spear","stick","sword","umbrella","zither"]
MARKET_ELEMENTS = ["metal","natural","fire","water","earth","wind","ice","thunder","light","dark"]

lang_cache = {"loaded": False, "raw": {}, "flat": {}, "by_key": {}}
market_items_cache = []

def _flatten_lang(obj, path=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            np = f"{path}.{key}" if path else key
            if isinstance(v, str):
                out[np] = v
            else:
                out.update(_flatten_lang(v, np))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten_lang(v, f"{path}.{i}" if path else str(i)))
    return out

def _index_lang_keys(obj):
    idx = {}
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                idx.setdefault(str(k), []).append(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return idx

def load_lang_data():
    if lang_cache["loaded"]:
        return True
    try:
        r = requests.get(URL_LANG, timeout=20, headers={"User-Agent":"Mozilla/5.0", "Accept":"application/json"})
        raw = r.json()
        lang_cache["raw"] = raw
        lang_cache["flat"] = _flatten_lang(raw)
        lang_cache["by_key"] = _index_lang_keys(raw)
        lang_cache["loaded"] = True
        return True
    except Exception:
        lang_cache["loaded"] = True
        lang_cache["raw"] = {}
        lang_cache["flat"] = {}
        lang_cache["by_key"] = {}
        return False

def lang_text(key, fallback=""):
    load_lang_data()
    key = str(key or "")
    for v in lang_cache.get("by_key", {}).get(key, []):
        n = _name_from_value(v)
        if n:
            return n
    return fallback or key

def _name_from_value(v, level=None):
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        lv = str(level or "")
        if lv:
            for k in (lv, f"level_{lv}", f"lv_{lv}"):
                if k in v:
                    n = _name_from_value(v.get(k), level)
                    if n:
                        return n
        for k in ("name", "title", "text", "vi", "label"):
            if k in v and isinstance(v.get(k), str):
                return v.get(k)
        for child in v.values():
            n = _name_from_value(child, level)
            if n:
                return n
    return ""

def market_lang_keys_for_api_item(item_type=None, special_type=None, sign=None, level=None):
    typ = str(item_type or "").strip()
    sp = str(special_type or "").strip()
    sign = str(sign or "").strip()
    lv = str(level or "").strip()
    keys = []
    if not sign:
        return keys

    # API chợ trả sign dạng rút gọn: box_weapon_2, medicinal_exp_2, egg_super_fragment, helmet_basic...
    # lang.json/filter.php lại thường dùng key đầy đủ: item_box_weapon_2, material_egg_super_fragment...
    if typ == "item":
        keys += [f"item_{sign}", sign]
    elif typ == "material":
        keys += [f"material_{sign}", sign]
    elif typ == "equipment":
        # Trang bị/pháp bảo thường nằm theo nhánh + sign + level.
        if sp and lv:
            keys += [f"equipment_{sp}_{sign}_{lv}", f"{sp}_{sign}_{lv}", f"{sign}_{lv}"]
        if sp:
            keys += [f"equipment_{sp}_{sign}", f"{sp}_{sign}"]
        keys += [sign]
    else:
        keys += [f"item_{sign}", f"material_{sign}"]
        if sp and lv:
            keys += [f"equipment_{sp}_{sign}_{lv}", f"{sp}_{sign}_{lv}"]
        if lv:
            keys += [f"{sign}_{lv}"]
        keys += [sign]

    seen = set()
    return [k for k in keys if k and not (k in seen or seen.add(k))]

def market_item_name(item_type=None, sign=None, level=None, special_type=None):
    load_lang_data()
    typ = str(item_type or "").strip()
    sp = str(special_type or "").strip()
    sign = str(sign or "").strip()
    lv = str(level or "").strip()
    if not sign and not typ:
        return "Không rõ"

    key_candidates = market_lang_keys_for_api_item(typ, sp, sign, lv)
    if sign in MARKET_ITEM_LIST:
        key_candidates.insert(0, sign)
    # Dự phòng cho kiểu cũ.
    if typ and sign and lv:
        key_candidates += [f"{typ}_{sign}_{lv}", f"{typ}_{sign}{lv}"]
    if typ and sign:
        key_candidates += [f"{typ}_{sign}"]
    if sign and lv:
        key_candidates += [f"{sign}_{lv}", f"{sign}{lv}"]
    if sign:
        key_candidates += [sign]
    if typ:
        key_candidates += [typ]
    seen = set()
    key_candidates = [k for k in key_candidates if not (k in seen or seen.add(k))]

    by_key = lang_cache.get("by_key", {})
    for key in key_candidates:
        for v in by_key.get(key, []):
            n = _name_from_value(v, lv)
            if n:
                return n
    flat = lang_cache.get("flat", {})
    for key in key_candidates:
        if key in flat:
            return flat[key]
    candidates = []
    sign_key = vn_key(sign)
    for path, val in flat.items():
        pk = vn_key(path)
        if sign_key and sign_key in pk:
            score = 0
            if typ and typ not in path:
                score += 2
            if sp and sp not in path:
                score += 1
            if lv and not (f"_{lv}" in path or path.endswith(lv)):
                score += 1
            candidates.append((score, len(path), val))
    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][2]
    raw = "_".join([x for x in (typ, sp, sign) if x])
    return f"{raw}" + (f" Lv.{lv}" if lv else "")

def market_filter_label_sign(sign):
    return f"{market_item_name('', sign, '')}  |  {sign}"

def api_sign_from_lang_key(key):
    key = str(key or "").strip()
    for prefix in ("item_", "material_"):
        if key.startswith(prefix):
            return key[len(prefix):]
    return key

def resolve_market_item_sign(query):
    q = vn_key(query)
    if not q:
        return "all", ""
    load_lang_data()
    best = None
    for lang_key in MARKET_ITEM_LIST:
        api_sign = api_sign_from_lang_key(lang_key)
        name = lang_text(lang_key, lang_key)
        hay = vn_key(f"{lang_key} {api_sign} {name}")
        if q in (vn_key(lang_key), vn_key(api_sign), vn_key(name)):
            return api_sign, name
        if q in hay and best is None:
            best = (api_sign, name)
    return best if best else ("all", "")

def normalize_market_level_for_api(level_value):
    lv = str(level_value or "").strip()
    return "0" if lv in ("", "all", "None") else lv

def market_api_level_values(type_filter, special_level):
    # filter.php của game chỉ tạo cấp 1..10 cho equipment.
    # Tool có thêm "all", nên khi chọn all sẽ quét 1..10 để không bị API trả rỗng.
    if str(type_filter) == "equipment" and str(special_level) in ("", "all", "0"):
        return [str(i) for i in range(1, 11)]
    return [normalize_market_level_for_api(special_level)]

def get_market_item_lang_name(sign):
    # market_item_list trong filter.php là key trực tiếp trong lang.json
    return lang_text(sign, sign)

def quality_label_from_item(item):
    val = item.get("quality") or item.get("special_data") or item.get("data")
    try:
        if isinstance(val, str) and val.startswith("{"):
            val = parse_info(val).get("quality", val)
        q = float(val)
        if 0.7 <= q <= 0.95: return "Thường"
        if 0.96 <= q <= 1.09: return "Tốt"
        if 1.10 <= q <= 1.25: return "Hiếm"
        if 1.26 <= q <= 1.30: return "Hoàn Mỹ"
    except Exception:
        pass
    return ""

def extract_market_rows(payload):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    rows = []
    if isinstance(data, dict):
        for key in ("list", "items", "rows", "data", "market"):
            if isinstance(data.get(key), list):
                rows = data.get(key)
                break
        if not rows:
            vals = list(data.values())
            if vals and all(isinstance(v, dict) for v in vals):
                rows = vals
    elif isinstance(data, list):
        rows = data

    # API chợ trả mỗi dòng dạng:
    # {"id_game_market":..., "data":"{\"type\":..., \"sign\":..., \"owner\":...}"}
    # Nếu không parse chuỗi data này thì app sẽ không thấy owner/sign/price nên lọc ra 0 món.
    parsed = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("data"), str):
            inner = parse_info(row.get("data"))
            if isinstance(inner, dict):
                merged = dict(row)
                merged.pop("data", None)
                merged.update(inner)
                parsed.append(merged)
            else:
                parsed.append(row)
        else:
            parsed.append(row)
    return parsed


# ---------------- Bộ dịch nhãn chợ sang giá trị API ----------------
MARKET_STATUS_LABEL_TO_CODE = {
    "Tất cả": "all",
    "Đang bán": "selling",
    "Đã bán": "sold",
    "Hủy": "cancel",
}
MARKET_STATUS_CODE_TO_LABEL = {v: k for k, v in MARKET_STATUS_LABEL_TO_CODE.items()}

MARKET_SORT_LABEL_TO_CODE = {
    "Mới nhất": "new",
    "Thấp đến cao": "lowest",
    "Cao đến thấp": "highest",
}

MARKET_TYPE_LABEL_TO_CODE = {
    "Tất cả": "all",
    "Trang bị": "equipment",
    "Vật phẩm": "item",
}
MARKET_TYPE_CODE_TO_LABEL = {v: k for k, v in MARKET_TYPE_LABEL_TO_CODE.items()}

MARKET_SPECIAL_TYPE_LABEL_TO_CODE = {
    "Chọn nhánh": "",
    "Vũ khí": "weapon",
    "Áo giáp": "armor",
    "Mũ": "helmet",
    "Găng tay": "gloves",
    "Giày": "boots",
    "Nhẫn": "ring",
    "Phù": "amulet",
    "Đai": "belt",
    "Ngọc bội": "pedant",
    "Pháp bảo": "treasure",
    "Sách": "book",
    "Pet - Đầu": "pet_head",
    "Pet - Thân trên": "pet_body_top",
    "Pet - Thân dưới": "pet_body_bottom",
    "Pet - Chân phải": "pet_foot_right",
    "Pet - Chân trái": "pet_foot_left",
    "Pet - Đuôi": "pet_tail",
    "Pet - Tay trái": "pet_hand_left",
    "Pet - Tay phải": "pet_hand_right",
}
MARKET_SPECIAL_TYPE_CODE_TO_LABEL = {v: k for k, v in MARKET_SPECIAL_TYPE_LABEL_TO_CODE.items()}

MARKET_LEVEL_LABEL_TO_CODE = {
    "Chọn cấp": "",
    "Nhất phẩm": "1",
    "Nhị phẩm": "2",
    "Tam phẩm": "3",
    "Tứ phẩm": "4",
    "Ngũ phẩm": "5",
    "Lục phẩm": "6",
    "Thất phẩm": "7",
    "Bát phẩm": "8",
    "Cửu phẩm": "9",
    "Vương cấp": "10",
}
MARKET_LEVEL_CODE_TO_LABEL = {v: k for k, v in MARKET_LEVEL_LABEL_TO_CODE.items()}

# Dịch sách/pháp bảo nếu lang.json có tên, fallback sang code cho khỏi lỗi.
def _label_list_from_codes(prefix, codes):
    return ["Tất cả"] + [lang_text(prefix + x, x) for x in codes]

def _code_from_label(prefix, label, codes):
    if not label or label == "Tất cả":
        return ""
    for c in codes:
        if lang_text(prefix + c, c) == label:
            return c
    return label

def current_market_filters():
    type_filter = MARKET_TYPE_LABEL_TO_CODE.get(market_type_var.get(), "all")
    status = MARKET_STATUS_LABEL_TO_CODE.get(market_status_var.get(), "all")
    sort = MARKET_SORT_LABEL_TO_CODE.get(market_sort_var.get(), "new")
    special_type = "all"
    special_level = "0"
    special_data = ""
    sign_filter = "all"
    owner = "0"  # Ẩn lọc owner theo yêu cầu.
    text_filter = entry_market_filter.get().strip() if 'entry_market_filter' in globals() else ""

    if type_filter == "equipment":
        special_type = MARKET_SPECIAL_TYPE_LABEL_TO_CODE.get(market_special_type_var.get(), "")
        special_level = MARKET_LEVEL_LABEL_TO_CODE.get(market_level_var.get(), "")
        if not special_type:
            raise ValueError("Anh chọn nhánh trang bị trước đã.")
        if not special_level:
            raise ValueError("Anh chọn cấp trang bị trước đã.")
        if special_type == "book":
            weapon = _code_from_label("weapon_", market_book_weapon_var.get(), MARKET_BOOK_WEAPONS)
            element = _code_from_label("element_", market_book_element_var.get(), MARKET_ELEMENTS)
            special_data = ",".join([x for x in (weapon, element) if x])
    elif type_filter == "item":
        sign_filter, _ = resolve_market_item_sign(text_filter)

    return {
        "type_filter": type_filter,
        "status": status,
        "sort": sort,
        "special_type": special_type,
        "special_level": special_level,
        "level_values": [normalize_market_level_for_api(special_level)],
        "special_data": special_data,
        "sign_filter": sign_filter,
        "owner": owner,
        "text_filter": text_filter,
    }

last_market_display_text = ""

def market_copy_text(text):
    try:
        app.clipboard_clear()
        app.clipboard_append(text)
    except Exception:
        pass

def market_badge(parent, text, fg="#303030", color="white", width=None):
    b = ctk.CTkLabel(
        parent,
        text=text,
        text_color=color,
        fg_color=fg,
        corner_radius=8,
        font=("Arial", 12, "bold"),
        width=width or 0,
        height=26,
        padx=8,
    )
    b.pack(side="left", padx=(0, 6), pady=2)
    return b

def market_quality_color(qual):
    if not qual:
        return MUTED
    q = vn_key(str(qual))
    if "hoan my" in q:
        return "#ffcc33"
    if "hiem" in q:
        return "#77aaff"
    if "tot" in q:
        return "#55d17a"
    return MUTED

def render_market(items, query="", owner_filter="", type_filter=""):
    global last_market_display_text
    clear(market_results)
    q = vn_key(query)
    rows = []
    normalized = []
    for it in items:
        if not isinstance(it, dict):
            continue
        owner = str(it.get("owner") or it.get("user") or it.get("author") or "")
        item_type = str(it.get("type") or it.get("item_type") or it.get("category") or "")
        special_type = str(it.get("special_type") or it.get("sub_type") or it.get("part") or "")
        sign = str(it.get("sign") or "")
        level = it.get("level") or it.get("item_level") or it.get("special_level") or ""
        price = it.get("price", "?")
        amount = it.get("amount") or it.get("num") or 1
        status_raw = str(it.get("status") or "")
        status = MARKET_STATUS_CODE_TO_LABEL.get(status_raw, status_raw)
        name = market_item_name(item_type, sign, level, special_type)
        qual = quality_label_from_item(it)
        hay = " ".join([owner, item_type, special_type, sign, str(level), name, qual, str(price), status])
        if q and q not in vn_key(hay):
            continue
        line = f"ID người bán: {owner} | {name} | x{amount} | Giá: {price} | {status}" + (f" | {qual}" if qual else "")
        rows.append(line)
        normalized.append({
            "owner": owner,
            "name": name,
            "amount": amount,
            "price": price,
            "status": status,
            "quality": qual,
            "line": line,
        })

    last_market_display_text = "\n".join(rows)

    head = ctk.CTkFrame(market_results, fg_color="#151515", corner_radius=16, border_width=1, border_color="#2f2f2f")
    head.pack(fill="x", padx=12, pady=(8, 10))
    top = ctk.CTkFrame(head, fg_color="transparent")
    top.pack(fill="x", padx=16, pady=12)
    ctk.CTkLabel(top, text=f"🛒 Kết quả chợ", text_color=BLUE, font=("Arial", 20, "bold")).pack(side="left")
    market_badge(top, f"{len(rows)} món", fg="#173b5f", color="#7ec1ff")
    if query:
        market_badge(top, f"Lọc: {query}", fg="#333333", color=MUTED)
    ctk.CTkButton(
        top,
        text="Copy tất cả",
        width=105,
        height=30,
        fg_color="#2f2f2f",
        hover_color="#3f3f3f",
        command=lambda: market_copy_text(last_market_display_text),
    ).pack(side="right")

    if not normalized:
        empty = ctk.CTkFrame(market_results, fg_color="#171717", corner_radius=16, border_width=1, border_color=BORDER)
        empty.pack(fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(empty, text="Không có vật phẩm khớp bộ lọc.", text_color=MUTED, font=("Arial", 16, "bold")).pack(anchor="center", pady=40)
        return

    for idx, row in enumerate(normalized, 1):
        item_card = ctk.CTkFrame(market_results, fg_color="#181818", corner_radius=14, border_width=1, border_color="#303030")
        item_card.pack(fill="x", padx=12, pady=6)

        line1 = ctk.CTkFrame(item_card, fg_color="transparent")
        line1.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            line1,
            text=row["name"],
            text_color=YELLOW,
            font=("Arial", 17, "bold"),
            anchor="w",
            justify="left",
            wraplength=360,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            line1,
            text=f"💰 {row['price']}",
            text_color="#ffdd66",
            font=("Arial", 16, "bold"),
            anchor="e",
            width=110,
        ).pack(side="right", padx=(8, 0))

        line2 = ctk.CTkFrame(item_card, fg_color="transparent")
        line2.pack(fill="x", padx=14, pady=(4, 10))
        market_badge(line2, f"ID: {row['owner']}", fg="#2d2d2d", color="#d6e8ff")
        market_badge(line2, f"x{row['amount']}", fg="#173b5f", color="#7ec1ff")
        status_color = "#55d17a" if row["status"] == "Đang bán" else ("#ffcc66" if row["status"] == "Đã bán" else "#ff7777")
        market_badge(line2, row["status"] or "Không rõ", fg="#2d2d2d", color=status_color)
        if row["quality"]:
            market_badge(line2, row["quality"], fg="#2d2d2d", color=market_quality_color(row["quality"]))
        ctk.CTkButton(
            line2,
            text="Copy ID",
            width=72,
            height=26,
            fg_color="#333333",
            hover_color="#464646",
            command=lambda owner=row["owner"]: market_copy_text(str(owner)),
        ).pack(side="right")

def fetch_market_worker():
    btn_state(btn_market_scan, "disabled")
    run_ui(lambda: empty_card(market_results, "Đang tải lang.json và quét chợ theo bộ lọc..."))
    try:
        load_lang_data()
        pages = int(entry_market_pages.get() or 1)
        pages = max(1, min(pages, 200))
        limit = 20
        mf = current_market_filters()
        all_items = []
        headers = {"User-Agent":"Mozilla/5.0", "Accept":"application/json"}
        for page in range(1, pages + 1):
            url = URL_MARKET.format(
                page=page,
                limit=limit,
                sort=mf["sort"],
                type_filter=mf["type_filter"],
                special_level=mf["special_level"],
                special_data=mf["special_data"],
                special_type=mf["special_type"],
                sign_filter=mf["sign_filter"],
                status=mf["status"],
                owner=mf["owner"],
            )
            resp = requests.get(url, timeout=20, headers=headers).json()
            rows = extract_market_rows(resp)
            if not rows:
                break
            all_items.extend(rows)
        dedup = []
        seen = set()
        for it in all_items:
            if isinstance(it, dict):
                k = str(it.get("id") or it.get("id_game_market") or it.get("market_id") or it.get("time") or "") + "|" + str(it.get("owner")) + "|" + str(it.get("sign")) + "|" + str(it.get("price"))
            else:
                k = repr(it)
            if k in seen:
                continue
            seen.add(k)
            dedup.append(it)
        global market_items_cache
        market_items_cache = dedup
        q = "" if (mf["type_filter"] == "item" and mf["sign_filter"] != "all") else mf["text_filter"]
        run_ui(lambda: render_market(market_items_cache, q, "", mf["type_filter"]))
    except Exception as e:
        run_ui(lambda: empty_card(market_results, "Lỗi quét chợ: " + str(e)))
    btn_state(btn_market_scan, "normal")

def scan_market():
    threading.Thread(target=fetch_market_worker, daemon=True).start()

def filter_market_cached():
    try:
        mf = current_market_filters()
        q = "" if (mf["type_filter"] == "item" and mf["sign_filter"] != "all") else mf["text_filter"]
        render_market(market_items_cache, q, "", mf["type_filter"])
    except Exception as e:
        empty_card(market_results, "Lỗi lọc: " + str(e))

def update_market_filter_ui(*args):
    typ = MARKET_TYPE_LABEL_TO_CODE.get(market_type_var.get(), "all")
    try:
        # Tách rõ: chọn Trang bị thì hiện Nhánh + Cấp; chọn Vật phẩm thì hiện ô nhập tên.
        # Cả hai nhóm luôn nằm TRÊN nút Quét chợ.
        if typ == "equipment":
            if not market_equipment_box.winfo_ismapped():
                market_equipment_box.pack(fill="x", padx=0, pady=(4, 0), before=btn_market_scan)
            market_item_box.pack_forget()
            market_item_hint.configure(text="Trang bị: chọn Nhánh trang bị → Cấp trang bị rồi bấm Quét chợ.")
            sp = MARKET_SPECIAL_TYPE_LABEL_TO_CODE.get(market_special_type_var.get(), "")
            lv = MARKET_LEVEL_LABEL_TO_CODE.get(market_level_var.get(), "")
            if sp and lv:
                btn_market_scan.configure(state="normal", fg_color="#1f7ac0")
            else:
                btn_market_scan.configure(state="disabled", fg_color="#3a3a3a")
        elif typ == "item":
            market_equipment_box.pack_forget()
            if not market_item_box.winfo_ismapped():
                market_item_box.pack(fill="x", padx=0, pady=(4, 0), before=btn_market_scan)
            market_item_hint.configure(text="Vật phẩm: nhập tên tiếng Việt để lọc; bỏ trống = tất cả vật phẩm.")
            btn_market_scan.configure(state="normal", fg_color="#1f7ac0")
        else:
            market_equipment_box.pack_forget()
            market_item_box.pack_forget()
            market_item_hint.configure(text="Tất cả: quét toàn bộ chợ theo Trạng thái và Sắp xếp.")
            btn_market_scan.configure(state="normal", fg_color="#1f7ac0")

        if typ == "equipment" and MARKET_SPECIAL_TYPE_LABEL_TO_CODE.get(market_special_type_var.get(), "") == "book":
            if not market_book_box.winfo_ismapped():
                market_book_box.pack(fill="x", padx=0, pady=0)
        else:
            market_book_box.pack_forget()
    except Exception:
        pass



def market_option(parent, variable, values, command=None, width=240):
    return ctk.CTkOptionMenu(
        parent,
        variable=variable,
        values=values,
        width=width,
        height=40,
        fg_color="#1f6fae",
        button_color="#0d4f82",
        button_hover_color="#176aa8",
        dropdown_fg_color="#191919",
        dropdown_hover_color="#1f6fae",
        dropdown_text_color="white",
        text_color="white",
        corner_radius=9,
        command=command,
    )

def market_section_label(parent, text):
    ctk.CTkLabel(parent, text=text, text_color="#d6e8ff", font=("Arial", 14, "bold"), anchor="w").pack(anchor="w", padx=16, pady=(10, 2))

market_panel = ctk.CTkFrame(tab5, fg_color="transparent")
market_panel.pack(fill="both", expand=True)
market_left = ctk.CTkScrollableFrame(market_panel, width=330, fg_color="transparent")
market_left.pack(side="left", fill="y", padx=(8, 4), pady=8)
market_results = ctk.CTkScrollableFrame(market_panel, width=680, height=560, fg_color="transparent")
market_results.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

mcard = card(market_left)
title_row = ctk.CTkFrame(mcard, fg_color="transparent")
title_row.pack(fill="x", padx=16, pady=(14, 4))
ctk.CTkLabel(title_row, text="🛒 Check Chợ", text_color=BLUE, font=("Arial", 21, "bold")).pack(side="left")
# Ẩn nhãn 20/trang theo yêu cầu; limit vẫn cố định 20 trong code
market_item_hint = ctk.CTkLabel(mcard, text="Chọn Trạng thái → Sắp xếp → Loại. Nếu là Trang bị thì chọn Nhánh + Cấp; nếu là Vật phẩm thì nhập tên bên dưới.", text_color=MUTED, font=("Arial", 12), wraplength=260, justify="left")
market_item_hint.pack(anchor="w", padx=16, pady=(0, 10))

# Ẩn ô Số trang quét và dòng 20 món/trang; vẫn mặc định quét 5 trang, mỗi trang 20 món.
entry_market_pages = ctk.CTkEntry(mcard, width=1, height=1)
entry_market_pages.insert(0, "5")

market_status_var = ctk.StringVar(value="Tất cả")
market_sort_var = ctk.StringVar(value="Mới nhất")
market_type_var = ctk.StringVar(value="Tất cả")
market_special_type_var = ctk.StringVar(value="Chọn nhánh")
market_level_var = ctk.StringVar(value="Chọn cấp")
market_book_weapon_var = ctk.StringVar(value="Tất cả")
market_book_element_var = ctk.StringVar(value="Tất cả")

label(mcard, "Trạng thái", 14, "bold", MUTED, pady=(8,0))
market_option(mcard, market_status_var, list(MARKET_STATUS_LABEL_TO_CODE.keys())).pack(padx=16, pady=6)
label(mcard, "Sắp xếp", 14, "bold", MUTED, pady=(8,0))
market_option(mcard, market_sort_var, list(MARKET_SORT_LABEL_TO_CODE.keys())).pack(padx=16, pady=6)
label(mcard, "Loại", 14, "bold", MUTED, pady=(8,0))
market_option(mcard, market_type_var, list(MARKET_TYPE_LABEL_TO_CODE.keys()), command=lambda _=None: update_market_filter_ui()).pack(padx=16, pady=6)

market_equipment_box = ctk.CTkFrame(mcard, fg_color="transparent")
label(market_equipment_box, "Nhánh trang bị", 14, "bold", MUTED, pady=(8,0))
market_option(market_equipment_box, market_special_type_var, list(MARKET_SPECIAL_TYPE_LABEL_TO_CODE.keys()), command=lambda _=None: update_market_filter_ui()).pack(padx=16, pady=6)
label(market_equipment_box, "Cấp trang bị", 14, "bold", MUTED, pady=(8,0))
market_option(market_equipment_box, market_level_var, list(MARKET_LEVEL_LABEL_TO_CODE.keys()), command=lambda _=None: update_market_filter_ui()).pack(padx=16, pady=6)
market_book_box = ctk.CTkFrame(market_equipment_box, fg_color="transparent")
label(market_book_box, "Sách: hỗ trợ vũ khí", 14, "bold", MUTED, pady=(8,0))
# Dùng tên tiếng Việt nếu lang.json tải được; fallback vẫn chạy.
market_option(market_book_box, market_book_weapon_var, ["Tất cả"] + [lang_text("weapon_" + x, x) for x in MARKET_BOOK_WEAPONS]).pack(padx=16, pady=6)
label(market_book_box, "Sách: hệ kỹ năng", 14, "bold", MUTED, pady=(8,0))
market_option(market_book_box, market_book_element_var, ["Tất cả"] + [lang_text("element_" + x, x) for x in MARKET_ELEMENTS]).pack(padx=16, pady=6)

market_item_box = ctk.CTkFrame(mcard, fg_color="transparent")
label(market_item_box, "Tên vật phẩm", 14, "bold", MUTED, pady=(8,0))
entry_market_filter = ctk.CTkEntry(market_item_box, placeholder_text="VD: đan, rương, trứng, linh hải...", width=240, height=38)
entry_market_filter.pack(padx=16, pady=6)

btn_market_scan = ctk.CTkButton(mcard, text="🔎 Quét chợ", width=240, height=42, fg_color="#1f7ac0", hover_color="#2693e6", font=("Arial", 14, "bold"), command=scan_market)
btn_market_scan.pack(padx=16, pady=(14, 8))

update_market_filter_ui()
empty_card(market_results, "Chọn bộ lọc rồi bấm Quét chợ. Kết quả chỉ hiện ID người bán, tên vật phẩm, số lượng, giá, trạng thái và phẩm chất.")


app.mainloop()
