# -*- coding: utf-8 -*-
import os
import json
import math
import threading
import datetime
import sys
import subprocess
import requests
import customtkinter as ctk
from tkinter import ttk
from io import BytesIO
try:
    from PIL import Image
    PIL_OK = True
except Exception:
    Image = None
    PIL_OK = False

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
URL_AVATAR_CANDIDATES = [
    "https://cmangax17.com/assets/tmp/avatar/{avatar}",
    "https://cmangax17.com/user/game/assets/tmp/avatar/{avatar}",
    "https://cmangax17.com/{avatar}",
]
GPS_SAVE_FILE = "gps_saved.json"

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

def center_crop_square(img):
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))

def fetch_avatar_pil(avatar, author=None):
    # JPG avatar cần Pillow. Nếu thiếu, thử cài Pillow tự động khi bấm Tải dữ liệu.
    if not ensure_pillow():
        return None

    candidates = []
    avatar = str(avatar or "").strip().lstrip("/")
    author = str(author or "").strip()

    # API có thể trả avatar dạng "48675.jpg?v=...". Một số acc dùng author làm tên file.
    if avatar:
        candidates.append(avatar)
        # Link ảnh vẫn chạy khi bỏ ?v=..., thêm bản bỏ query để dự phòng cache/CDN.
        if "?" in avatar:
            candidates.append(avatar.split("?", 1)[0])
    if author:
        candidates.append(f"{author}.jpg")

    # Khử trùng lặp nhưng giữ thứ tự ưu tiên: avatar từ API trước, author sau.
    seen = set()
    clean_candidates = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            clean_candidates.append(item)

    urls = []
    for item in clean_candidates:
        if item.startswith(("http://", "https://")):
            urls.append(item)
        else:
            for tpl in URL_AVATAR_CANDIDATES:
                urls.append(tpl.format(avatar=item))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://cmangax17.com/user/game/dashboard",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    for url in urls:
        try:
            r = requests.get(url, timeout=12, headers=headers, allow_redirects=True)
            ctype = (r.headers.get("Content-Type") or "").lower()
            if r.status_code != 200 or not r.content:
                continue
            # Nếu server trả HTML lỗi thì bỏ qua.
            if ("image" not in ctype) and (r.content[:20].lower().startswith(b"<!doctype") or r.content[:20].lower().startswith(b"<html")):
                continue
            img = Image.open(BytesIO(r.content)).convert("RGBA")
            return center_crop_square(img)
        except Exception:
            continue
    return None

def stat_box(parent, title, value, color=BLUE, width=180):
    f = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=12)
    f.pack(side="left", fill="both", expand=True, padx=6, pady=8)
    label(f, title, 13, "normal", MUTED, padx=14, pady=(12,0))
    label(f, str(value), 24, "bold", color, padx=14, pady=(0,12))
    return f

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

# ---------------- TAB 0 ----------------
frame0_top = ctk.CTkFrame(tab0, fg_color="transparent")
frame0_top.pack(pady=10)
list_guilds = ctk.CTkScrollableFrame(tab0, width=990, height=540, fg_color="transparent")
list_guilds.pack(fill="both", expand=True, padx=8, pady=8)

def render_guilds(items):
    clear(list_guilds)
    head = card(list_guilds)
    label(head, f"Danh sách tông môn — tìm thấy {len(items)} tông", 18, "bold", BLUE, pady=12)
    for gid, name in items:
        c = card(list_guilds)
        row = ctk.CTkFrame(c, fg_color="transparent"); row.pack(fill="x", padx=14, pady=12)
        label(row, name, 17, "bold", YELLOW, side="left", padx=0, pady=0)
        label(row, f"ID: {gid}", 15, "bold", MUTED, side="right", padx=0, pady=0)

def load_all_guilds_worker():
    run_ui(lambda: empty_card(list_guilds, "Đang tải danh sách tông môn..."))
    try:
        rows = requests.get(URL_GUILD, timeout=20).json().get("data", [])
        guild_map = {}
        for row in rows:
            info = parse_info(row.get("info", "{}"))
            g = info.get("guild") or {}
            gid, name = str(g.get("id", "")), g.get("name", "Unknown")
            if gid: guild_map[gid] = name
        items = sorted(guild_map.items(), key=lambda x: x[1].lower())
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
    h = card(list_score)
    row = ctk.CTkFrame(h, fg_color="transparent"); row.pack(fill="x", padx=16, pady=12)
    label(row, guild_name, 20, "bold", YELLOW, side="left", padx=0, pady=0)
    label(row, f"Guild ID: {guild_id}    Thành viên: {len(result)}", 15, "bold", MUTED, side="right", padx=0, pady=0)
    for i, p in enumerate(result, 1):
        c = card(list_score)
        row = ctk.CTkFrame(c, fg_color="transparent"); row.pack(fill="x", padx=16, pady=10)
        label(row, f"#{i}", 16, "bold", BLUE, side="left", padx=(0,12), pady=0)
        label(row, p["name"], 16, "bold", "white", side="left", padx=0, pady=0)
        label(row, f'{p["score"]:,} điểm', 18, "bold", YELLOW, side="right", padx=0, pady=0)

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
    cp = (char.get("cp") or {}).get("total", "?") if isinstance(char.get("cp"), dict) else "?"
    current = energy.get("current", "?") if energy else "?"
    ts = energy.get("time") if energy else None
    dt = datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M:%S") if ts else "Không rõ"
    top = card(right_gps)
    row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=18, pady=16)
    ava = ctk.CTkFrame(row, width=112, height=112, corner_radius=16, border_width=2, border_color="#c99600", fg_color="#2b2b2b")
    ava.pack(side="left", padx=(0,18)); ava.pack_propagate(False)
    if avatar_img is not None:
        try:
            avatar_ctk = ctk.CTkImage(light_image=avatar_img, dark_image=avatar_img, size=(108,108))
            avatar_label = ctk.CTkLabel(ava, text="", image=avatar_ctk)
            avatar_label.image = avatar_ctk
            avatar_label.pack(expand=True)
        except Exception:
            ctk.CTkLabel(ava, text="👤", font=("Arial", 42)).pack(expand=True)
    else:
        ctk.CTkLabel(ava, text="👤", font=("Arial", 42)).pack(expand=True)
    mid = ctk.CTkFrame(row, fg_color="transparent"); mid.pack(side="left", fill="both", expand=True)
    label(mid, name, 30, "bold", YELLOW, padx=0, pady=(2,4))
    label(mid, "⚙ Cấp độ: " + level, 17, "normal", "white", padx=0, pady=2)
    badges = ctk.CTkFrame(mid, fg_color="transparent"); badges.pack(anchor="w", pady=8)
    ctk.CTkLabel(badges, text=f"ID: {cid_info}", fg_color="#333333", corner_radius=8, font=("Arial",14,"bold"), padx=10, pady=5).pack(side="left", padx=(0,8))
    ctk.CTkLabel(badges, text=f"🎟 Vé ĐHĐ: {dhd_energy}/1500", fg_color="#333333", corner_radius=8, font=("Arial",14,"bold"), padx=10, pady=5).pack(side="left", padx=(0,8))
    if saved_name: ctk.CTkLabel(badges, text=saved_name, fg_color="#0b61c9", corner_radius=8, font=("Arial",14,"bold"), padx=10, pady=5).pack(side="left", padx=(0,8))
    right = ctk.CTkFrame(row, fg_color="transparent", width=180); right.pack(side="right", fill="y")
    label(right, "⚔ Lực chiến", 16, "bold", RED, padx=0, pady=(16,0))
    label(right, str(cp), 32, "bold", RED, padx=0, pady=4)
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
        label(c, f"Mỏ #{idx}", 17, "bold", "white", pady=(12,0))
        row = ctk.CTkFrame(c, fg_color="transparent"); row.pack(fill="x", padx=10, pady=6)
        stat_box(row, "Tầng", area, BLUE)
        stat_box(row, "Độ hiếm", f"{rare_text} (Cấp {rare})", RED if rare == 4 else YELLOW)
        stat_box(row, "Đang khai", f"{miner_name} (Lv.{level_num})" if miner_name != "Trống" else "Trống", BLUE)

def fetch_mine_worker():
    target = entry_mine.get().strip()
    if not target:
        run_ui(lambda: empty_card(right_gps, "Vui lòng nhập Nhân vật ID.")); btn_state(btn_mine,"normal"); return
    run_ui(lambda: empty_card(right_gps, "Đang tải dữ liệu cho ID " + target + "..."))
    try:
        char = {}
        avatar_img = None
        dhd_energy = 0
        try:
            char_resp = requests.get(URL_CHAR.format(id=target), timeout=15).json()
            if char_resp.get("status") == 1:
                data_block = char_resp.get("data", {})
                char = parse_info(data_block.get("info", "{}"))
                other = parse_info(data_block.get("other", "{}"))
                try:
                    dhd_energy = int(((other.get("friend") or {}).get("energy") or 0))
                except Exception:
                    dhd_energy = 0
                avatar_img = fetch_avatar_pil(char.get("avatar"), char.get("author"))
        except Exception:
            pass
        er = requests.get(URL_ENERGY.format(character=target), timeout=15).json(); energy = er.get("data", {}) if er.get("status") == 1 else {}
        mr = requests.get(URL_MINE.format(target=target), timeout=15).json()
        mines = []
        if mr.get("status") == 1:
            for row in mr.get("data", []): mines.append(parse_info(row.get("data", "{}")))
        else:
            run_ui(lambda: empty_card(right_gps, "Lỗi API mỏ: " + mr.get("message", "Không rõ"))); btn_state(btn_mine,"normal"); return
        saved = gps_saved.get(target, "")
        run_ui(lambda: render_gps(char, energy, mines, saved, avatar_img, dhd_energy))
    except Exception as e:
        run_ui(lambda: empty_card(right_gps, "Lỗi kết nối: " + str(e)))
    btn_state(btn_mine,"normal")
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

app.mainloop()
