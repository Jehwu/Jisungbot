import os
import json
import random
import asyncio
from datetime import datetime, time, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands, tasks

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------
# 1. 봇 기본 설정 및 타임존, 깃허브 이미지 Base URL
# ---------------------------------------------------------
KST = timezone(timedelta(hours=9))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "bot_data.json"

GITHUB_USERNAME = "Jehwu"
GITHUB_REPO = "Jisungbot"
GITHUB_IMG_BASE = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/images"

def get_img_url(file_name):
    return f"{GITHUB_IMG_BASE}/{file_name}"

def get_fatigue_bar(fatigue, max_fatigue=100):
    filled = max(0, min(10, int(round((fatigue / max_fatigue) * 10))))
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {fatigue}/{max_fatigue}"

# ---------------------------------------------------------
# 2. 데이터베이스 구조 및 자동 마이그레이션
# ---------------------------------------------------------
DEFAULT_MARKET = {
    "artifacts": {
        "똥먹방 비법서": {"price": 30000, "prev_price": 30000},
        "차은우지성 조각상": {"price": 50000, "prev_price": 50000},
        "170KG 비법서": {"price": 70000, "prev_price": 70000},
        "곤지암병원 지도": {"price": 100000, "prev_price": 100000},
        "L을 가져가 비법서": {"price": 150000, "prev_price": 150000}
    },
    "stocks": {
        "170kg전자": {"price": 500000, "prev_price": 500000},
        "L을가져닉스": {"price": 500000, "prev_price": 500000},
        "엔비티키퐁크": {"price": 500000, "prev_price": 500000}
    },
    "fish": {
        "붕어": {"price": 1000, "prev_price": 1000},
        "고등어": {"price": 1000, "prev_price": 1000},
        "광어": {"price": 1000, "prev_price": 1000},
        "참다랑어": {"price": 10000, "prev_price": 10000},
        "돗돔": {"price": 10000, "prev_price": 10000},
        "황금 잉어": {"price": 60000, "prev_price": 60000}
    }
}

FISH_LEVEL_REQS = [25, 50, 80, 120, 160, 225, 300, 400, 550, 700]

def update_fish_level(u):
    fc = u.get("fish_count", 0)
    lvl = 0
    for i, req in enumerate(FISH_LEVEL_REQS):
        if fc >= req:
            lvl = i + 1
    u["fish_level"] = lvl
    return lvl

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "market": DEFAULT_MARKET}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data:
                data = {"users": data, "market": DEFAULT_MARKET}
            if "market" not in data:
                data["market"] = DEFAULT_MARKET

            for cat in ["artifacts", "stocks", "fish"]:
                if cat not in data["market"]:
                    data["market"][cat] = DEFAULT_MARKET[cat]
                for k, v in data["market"][cat].items():
                    if isinstance(v, int):
                        data["market"][cat][k] = {"price": v, "prev_price": v}
            return data
    except Exception as e:
        print(f"데이터 로딩 오류: {e}")
        return {"users": {}, "market": DEFAULT_MARKET}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"데이터 저장 오류: {e}")

def get_user_data(data, user_id):
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "money": 10000,
            "fatigue": 100,
            "last_dance_time": 0,
            "last_fish_time": 0,
            "dance_count": 0,
            "dance_level": 0,
            "fish_count": 0,
            "fish_level": 0,
            "drink_used_today": 0,
            "hot6_used_today": 0,
            "remittance_count_today": 0,
            "last_check_date": "",
            "last_bankrupt_date": "",
            "cleared_dungeon_today": [],
            "dungeon_clear_date": "",
            "attendance_streak": 0,
            "inventory": {
                "똥먹방 비법서": 0, "차은우지성 조각상": 0, "170KG 비법서": 0,
                "곤지암병원 지도": 0, "L을 가져가 비법서": 0,
                "에너지드링크": 0, "핫식스 박스": 0, "유물 랜덤 상자": 0,
                "강화석": 0, "파괴 방지권": 0, "하락 방지권": 0,
                "붕어": 0, "고등어": 0, "광어": 0, "참다랑어": 0, "돗돔": 0, "황금 잉어": 0,
                "찢어진 장화": 0, "썩은 미역": 0, "빈 깡통": 0
            },
            "stocks": {"170kg전자": 0, "L을가져닉스": 0, "엔비티키퐁크": 0},
            "car_level": 0,
            "owned_rods": [0],
            "equipped_rod": 0
        }
    else:
        u = data["users"][uid]
        u.setdefault("remittance_count_today", 0)
        u.setdefault("last_check_date", "")
        u.setdefault("last_bankrupt_date", "")
        u.setdefault("attendance_streak", 0)
        u.setdefault("last_fish_time", 0)
        u.setdefault("fish_count", 0)
        u.setdefault("fish_level", 0)
        u.setdefault("cleared_dungeon_today", [])
        u.setdefault("dungeon_clear_date", "")
        u.setdefault("owned_rods", [0])
        u.setdefault("equipped_rod", 0)
        for fish_item in ["붕어", "고등어", "광어", "참다랑어", "돗돔", "황금 잉어", "찢어진 장화", "썩은 미역", "빈 깡통"]:
            u["inventory"].setdefault(fish_item, 0)
        if "car_level" not in u:
            u["car_level"] = u.pop("weapon_level", 0)
        update_fish_level(u)
    return data["users"][uid]

# ---------------------------------------------------------
# 3. 데이터 스펙 (차 & 낚싯대)
# ---------------------------------------------------------
CAR_NAMES = [
    "뚜벅이 (맨발)", "현대 아반떼", "기아 K5", "현대 그랜저", "제네시스 G80", "제네시스 G90",
    "BMW 5시리즈", "벤츠 E클래스", "아우디 A8", "벤츠 S클래스", "포르쉐 박스터",
    "포르쉐 911 카레라", "포르쉐 타이칸", "마세라티 콰트로포르테", "벤츠 AMG GT", "아우디 R8",
    "람보르기니 우라칸", "페라리 F8 트리부토", "페라리 296 GTB", "맥라렌 720S", "람보르기니 아벤타도르",
    "롤스로이스 고스트", "롤스로이스 팬텀", "벤틀리 뮬리너", "페라리 라페라리", "맥라렌 P1",
    "포르쉐 918 스파이더", "부가티 시론", "코닉세그 예스코", "파가니 와이라",
    "부가티 볼리드", "부가티 라 부아튀르 누아르"
]

ROD_DATA = {
    0: {"name": "맨손", "price": 0, "fatigue": 5, "rates": (20.0, 60.0, 16.0, 3.0, 1.0)},
    1: {"name": "대나무 낚싯대", "price": 30000, "fatigue": 7, "rates": (18.0, 58.0, 19.0, 3.5, 1.5)},
    2: {"name": "카본 낚싯대", "price": 150000, "fatigue": 9, "rates": (15.0, 55.0, 23.0, 4.5, 2.5)},
    3: {"name": "티타늄 낚싯대", "price": 500000, "fatigue": 12, "rates": (12.0, 51.0, 28.0, 6.0, 3.0)},
    4: {"name": "✨ 트라이아나", "price": 2000000, "fatigue": 15, "rates": (8.0, 46.0, 35.0, 7.0, 4.0)}
}

DUNGEON_DATA = {
    1: {
        "name": "1층: 동네 고가도로",
        "rec": "1~5강",
        "boss": "🛵 딸배왕 박씨",
        "boss_speed": 14,
        "gold": 20000,
        "stones": 2,
        "protect": 0,
        "degrade_protect": 0
    },
    2: {
        "name": "2층: 수도권 외곽순환",
        "rec": "6~10강",
        "boss": "🏎️ 야간 칼치기 폭주족",
        "boss_speed": 22,
        "gold": 50000,
        "stones": 0,
        "protect": 0,
        "degrade_protect": 1
    },
    3: {
        "name": "3층: 태백 레이스웨이",
        "rec": "11~15강",
        "boss": "🏁 프로 레이싱팀 에이스",
        "boss_speed": 31,
        "gold": 100000,
        "stones": 5,
        "protect": 0,
        "degrade_protect": 0
    },
    4: {
        "name": "4층: 영암 F1 서킷",
        "rec": "16~20강",
        "boss": "🏆 전직 F1 챔피언",
        "boss_speed": 40,
        "gold": 250000,
        "stones": 0,
        "protect": 1,
        "degrade_protect": 0
    },
    5: {
        "name": "5층: 뉘르부르크링",
        "rec": "21~25강",
        "boss": "👻 뉘르의 유령 드라이버",
        "boss_speed": 50,
        "gold": 500000,
        "stones": 0,
        "protect": 0,
        "degrade_protect": 2
    },
    6: {
        "name": "6층: 아우토반 무제한",
        "rec": "26~30강",
        "boss": "👑 속도의 신 [지성]",
        "boss_speed": 62,
        "gold": 1000000,
        "stones": 0,
        "protect": 2,
        "degrade_protect": 0
    }
}

def get_car_name(level):
    if level <= 0: return "뚜벅이 (맨발)"
    if level >= 31: return "✨ 부가티 라 부아튀르 누아르 [30(+1)강]"
    if level == 30: return f"🔥 {CAR_NAMES[30]} [30강]"
    return f"{CAR_NAMES[level]} [{level}강]"

def get_upgrade_info(level):
    gold_cost = (level + 1) * 10000
    if level < 10: stone_cost = 0
    elif level < 15: stone_cost = level - 9
    elif level < 20: stone_cost = (level - 14) * 2 + 5
    elif level < 25: stone_cost = (level - 19) * 5 + 15
    else: stone_cost = (level - 24) * 10 + 40

    if level < 5: success_rate, destroy_rate = 100 - (level * 5), 0
    elif level < 10: success_rate, destroy_rate = 70 - ((level - 5) * 5), 0
    elif level < 15: success_rate, destroy_rate = 40 - ((level - 10) * 3), 0
    elif level < 20: success_rate, destroy_rate = 20 - ((level - 15) * 2), 0
    elif level < 30: success_rate, destroy_rate = max(3, 8 - (level - 20)), 15
    else: success_rate, destroy_rate = 3, 50

    degrade_rate = 100 - success_rate - destroy_rate if success_rate + destroy_rate < 100 else 0
    return gold_cost, stone_cost, success_rate, destroy_rate, degrade_rate

# ---------------------------------------------------------
# 4. 정각 주기 스케줄러 (유물 / 주식 / 물고기 시세 변동)
# ---------------------------------------------------------
artifact_times = [time(hour=h, minute=m) for h in range(24) for m in (0, 30)]
@tasks.loop(time=artifact_times)
async def update_artifact_and_fish_prices():
    data = load_data()
    art_base = {
        "똥먹방 비법서": (30000, 6000, 90000),
        "차은우지성 조각상": (50000, 10000, 150000),
        "170KG 비법서": (70000, 14000, 210000),
        "곤지암병원 지도": (100000, 20000, 300000),
        "L을 가져가 비법서": (150000, 30000, 450000)
    }
    for item, (base, min_p, max_p) in art_base.items():
        curr_data = data["market"]["artifacts"].get(item, {"price": base, "prev_price": base})
        curr_price = curr_data["price"] if isinstance(curr_data, dict) else curr_data
        rate = random.uniform(-0.30, 0.30)
        new_price = max(min_p, min(max_p, int(curr_price * (1 + rate))))
        data["market"]["artifacts"][item] = {"price": new_price, "prev_price": curr_price}

    fish_base = {
        "붕어": (1000, 500, 2000), "고등어": (1000, 500, 2000), "광어": (1000, 500, 2000),
        "참다랑어": (10000, 5000, 20000), "돗돔": (10000, 5000, 20000),
        "황금 잉어": (60000, 30000, 120000)
    }
    for fish_item, (base, min_p, max_p) in fish_base.items():
        curr_data = data["market"]["fish"].get(fish_item, {"price": base, "prev_price": base})
        curr_price = curr_data["price"] if isinstance(curr_data, dict) else curr_data
        rate = random.uniform(-0.35, 0.35)
        new_price = max(min_p, min(max_p, int(curr_price * (1 + rate))))
        data["market"]["fish"][fish_item] = {"price": new_price, "prev_price": curr_price}

    save_data(data)

stock_times = [time(hour=h, minute=0) for h in range(24)]
@tasks.loop(time=stock_times)
async def update_stock_prices():
    data = load_data()
    for stock in data["market"]["stocks"].keys():
        curr_data = data["market"]["stocks"][stock]
        curr_price = curr_data["price"] if isinstance(curr_data, dict) else curr_data
        rate = random.uniform(-0.35, 0.35)
        new_price = max(10000, int(curr_price * (1 + rate)))
        data["market"]["stocks"][stock] = {"price": new_price, "prev_price": curr_price}
    save_data(data)

@tasks.loop(time=time(hour=15, minute=0)) # KST 00시
async def daily_reset():
    data = load_data()
    for uid, user in data["users"].items():
        user["fatigue"] = 100
        user["drink_used_today"] = 0
        user["hot6_used_today"] = 0
        user["remittance_count_today"] = 0
        user["cleared_dungeon_today"] = []
    save_data(data)

# ---------------------------------------------------------
# 5. MODAL 팝업창 (수량 직접 입력 매매용)
# ---------------------------------------------------------
class StockTradeModal(discord.ui.Modal):
    def __init__(self, mode, stock_name, user_id):
        title_str = f"📈 {stock_name} 매수" if mode == "buy" else f"📉 {stock_name} 매도"
        super().__init__(title=title_str)
        self.mode = mode
        self.stock_name = stock_name
        self.user_id = user_id
        self.qty_input = discord.ui.TextInput(label="수량 입력", placeholder="예: 5", min_length=1, max_length=6)
        self.add_item(self.qty_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty_input.value)
            if qty <= 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ 올바른 수량을 입력해주세요.", ephemeral=True)
            return

        data = load_data()
        u = get_user_data(data, self.user_id)
        st_data = data["market"]["stocks"][self.stock_name]
        price = st_data["price"] if isinstance(st_data, dict) else st_data
        total_cost = price * qty

        if self.mode == "buy":
            if u["money"] < total_cost:
                await interaction.response.send_message(f"❌ 현금이 부족합니다. (필요: {total_cost:,}원)", ephemeral=True)
                return
            u["money"] -= total_cost
            u["stocks"][self.stock_name] += qty
            msg = f"📈 [{self.stock_name}] {qty}주 매수 완료! (-{total_cost:,}원)"
        else:
            if u["stocks"].get(self.stock_name, 0) < qty:
                await interaction.response.send_message(f"❌ 소지한 [{self.stock_name}] 주식이 부족합니다.", ephemeral=True)
                return
            u["stocks"][self.stock_name] -= qty
            u["money"] += total_cost
            msg = f"📉 [{self.stock_name}] {qty}주 매도 완료! (+{total_cost:,}원)"

        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

class ArtifactSellModal(discord.ui.Modal):
    def __init__(self, art_name, user_id):
        super().__init__(title=f"🏛️ {art_name} 매도")
        self.art_name = art_name
        self.user_id = user_id
        self.qty_input = discord.ui.TextInput(label="판매 수량 입력", placeholder="예: 1", min_length=1, max_length=5)
        self.add_item(self.qty_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty_input.value)
            if qty <= 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ 올바른 수량을 입력해주세요.", ephemeral=True)
            return

        data = load_data()
        u = get_user_data(data, self.user_id)
        if u["inventory"].get(self.art_name, 0) < qty:
            await interaction.response.send_message(f"❌ 소지한 [{self.art_name}]이(가) 부족합니다.", ephemeral=True)
            return

        art_data = data["market"]["artifacts"][self.art_name]
        price = art_data["price"] if isinstance(art_data, dict) else art_data
        total = price * qty

        u["inventory"][self.art_name] -= qty
        u["money"] += total
        save_data(data)

        await interaction.response.send_message(f"✅ [{self.art_name}] {qty}개 매각 완료! (+{total:,}원)", ephemeral=True)

# ---------------------------------------------------------
# 6. UI 대시보드 컴포넌트 (/주식 /유물 /가방 /강화 /대결 /가위바위보)
# ---------------------------------------------------------

class StockView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="📈 매수", style=discord.ButtonStyle.green, row=0)
    async def buy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return
        select_view = StockSelectTradeView(self.user_id, "buy")
        await interaction.response.send_message("📈 매수할 종목을 선택하세요:", view=select_view, ephemeral=True)

    @discord.ui.button(label="📉 매도", style=discord.ButtonStyle.red, row=0)
    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return
        select_view = StockSelectTradeView(self.user_id, "sell")
        await interaction.response.send_message("📉 매도할 종목을 선택하세요:", view=select_view, ephemeral=True)

class StockSelectTradeView(discord.ui.View):
    def __init__(self, user_id, mode):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.mode = mode
        options = [
            discord.SelectOption(label="170kg전자", value="170kg전자"),
            discord.SelectOption(label="L을가져닉스", value="L을가져닉스"),
            discord.SelectOption(label="엔비티키퐁크", value="엔비티키퐁크")
        ]
        select = discord.ui.Select(placeholder="종목 선택...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        stock_name = interaction.data["values"][0]
        modal = StockTradeModal(self.mode, stock_name, self.user_id)
        await interaction.response.send_modal(modal)

def build_stock_embed(user):
    data = load_data()
    u = get_user_data(data, user.id)
    stocks = data["market"]["stocks"]
    now = datetime.now(KST)
    rem_min = 60 - now.minute if now.minute > 0 else 60

    embed = discord.Embed(title="📈 주식 대시보드", color=0x3498db)
    lines = []
    total_stock_val = 0
    for st, info in stocks.items():
        price = info["price"] if isinstance(info, dict) else info
        prev = info["prev_price"] if isinstance(info, dict) else price
        rate = ((price - prev) / prev * 100) if prev > 0 else 0
        status = f"▲+{rate:.1f}%" if rate > 0 else (f"▼{rate:.1f}%" if rate < 0 else "0.0%")

        user_qty = u["stocks"].get(st, 0)
        val = price * user_qty
        total_stock_val += val

        lines.append(f"• **{st}** | `{price:,}원` ({status}) | 보유: `{user_qty:,}주` ({val:,}원)")

    embed.description = "\n".join(lines)
    embed.add_field(name="💼 총 평가금액", value=f"**{total_stock_val:,}원**", inline=False)
    embed.set_footer(text=f"⏱️ 갱신까지 약 {rem_min}분 남음")
    return embed

class ArtifactView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="💰 유물 매도", style=discord.ButtonStyle.primary)
    async def sell_art_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return
        select_view = ArtifactSelectTradeView(self.user_id)
        await interaction.response.send_message("🏛️ 매도할 유물을 선택하세요:", view=select_view, ephemeral=True)

class ArtifactSelectTradeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        options = [
            discord.SelectOption(label="똥먹방 비법서", value="똥먹방 비법서"),
            discord.SelectOption(label="차은우지성 조각상", value="차은우지성 조각상"),
            discord.SelectOption(label="170KG 비법서", value="170KG 비법서"),
            discord.SelectOption(label="곤지암병원 지도", value="곤지암병원 지도"),
            discord.SelectOption(label="L을 가져가 비법서", value="L을 가져가 비법서")
        ]
        select = discord.ui.Select(placeholder="유물 선택...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        art_name = interaction.data["values"][0]
        modal = ArtifactSellModal(art_name, self.user_id)
        await interaction.response.send_modal(modal)

def build_artifact_embed(user):
    data = load_data()
    u = get_user_data(data, user.id)
    market = data["market"]["artifacts"]
    now = datetime.now(KST)
    rem_min = 30 - (now.minute % 30)

    embed = discord.Embed(title="🏛️ 고대 유물 대시보드", color=0xf1c40f)
    lines = []
    total_art_val = 0
    for name, info in market.items():
        price = info["price"] if isinstance(info, dict) else info
        prev = info["prev_price"] if isinstance(info, dict) else price
        rate = ((price - prev) / prev * 100) if prev > 0 else 0
        status = f"▲+{rate:.1f}%" if rate > 0 else (f"▼{rate:.1f}%" if rate < 0 else "0.0%")

        user_qty = u["inventory"].get(name, 0)
        val = price * user_qty
        total_art_val += val

        lines.append(f"• **{name}** | `{price:,}원` ({status}) | 보유: `{user_qty}개` ({val:,}원)")

    embed.description = "\n".join(lines)
    embed.add_field(name="🏛️ 총 평가금액", value=f"**{total_art_val:,}원**", inline=False)
    embed.set_footer(text=f"⏱️ 갱신까지 약 {rem_min}분 남음")
    return embed

class BagItemSelect(discord.ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [
            discord.SelectOption(label="에너지드링크", description="피로도 +30 회복 (일일 3회)", emoji="🥤", value="에너지드링크"),
            discord.SelectOption(label="핫식스 박스", description="피로도 100 완충 (일일 1회)", emoji="⚡", value="핫식스 박스"),
            discord.SelectOption(label="유물 랜덤 상자", description="고대 유물 100% 획득", emoji="📦", value="유물 랜덤 상자")
        ]
        super().__init__(placeholder="🥤 소모품 선택...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return

        item = self.values[0]
        data = load_data()
        u = get_user_data(data, interaction.user.id)

        if u["inventory"].get(item, 0) <= 0:
            await interaction.response.send_message(f"❌ 소지한 [{item}]이(가) 없습니다.", ephemeral=True)
            return

        msg = ""
        if item == "에너지드링크":
            if u["drink_used_today"] >= 3:
                await interaction.response.send_message("❌ 하루 최대 3회만 사용 가능합니다.", ephemeral=True)
                return
            u["inventory"][item] -= 1
            u["drink_used_today"] += 1
            u["fatigue"] = min(100, u["fatigue"] + 30)
            msg = f"🥤 에너지드링크 사용! (피로도: {u['fatigue']}/100)"

        elif item == "핫식스 박스":
            if u["hot6_used_today"] >= 1:
                await interaction.response.send_message("❌ 하루 최대 1회만 사용 가능합니다.", ephemeral=True)
                return
            u["inventory"][item] -= 1
            u["hot6_used_today"] += 1
            u["fatigue"] = 100
            msg = f"⚡ 핫식스 사용! 피로도가 100으로 완충되었습니다!"

        elif item == "유물 랜덤 상자":
            u["inventory"][item] -= 1
            arts = ["똥먹방 비법서", "차은우지성 조각상", "170KG 비법서", "곤지암병원 지도", "L을 가져가 비법서"]
            got = random.choice(arts)
            u["inventory"][got] += 1
            msg = f"📦 유물 상자에서 【 {got} 】을(를) 발굴했습니다!"

        save_data(data)
        embed = build_bag_embed(interaction.user, u)
        await interaction.response.edit_message(embed=embed, view=self.view)
        await interaction.followup.send(msg, ephemeral=True)

class BagRodSelect(discord.ui.Select):
    def __init__(self, user_id, owned_rods):
        self.user_id = user_id
        options = []
        for rod_id in owned_rods:
            r_info = ROD_DATA[rod_id]
            options.append(discord.SelectOption(
                label=r_info["name"],
                description=f"피로도 소모: {r_info['fatigue']}",
                emoji="🎣",
                value=str(rod_id)
            ))
        super().__init__(placeholder="🎣 낚싯대 선택...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return

        rod_id = int(self.values[0])
        data = load_data()
        u = get_user_data(data, interaction.user.id)
        u["equipped_rod"] = rod_id
        save_data(data)

        embed = build_bag_embed(interaction.user, u)
        await interaction.response.edit_message(embed=embed, view=self.view)
        await interaction.followup.send(f"🎣 낚싯대를 **[{ROD_DATA[rod_id]['name']}]**(으)로 장착했습니다!", ephemeral=True)

class BagView(discord.ui.View):
    def __init__(self, user_id, owned_rods):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.add_item(BagItemSelect(user_id))
        self.add_item(BagRodSelect(user_id, owned_rods))

    @discord.ui.button(label="🐟 물고기 전체 매도", style=discord.ButtonStyle.success, row=2)
    async def sell_all_fish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return

        data = load_data()
        u = get_user_data(data, interaction.user.id)
        fish_market = data["market"]["fish"]

        fish_list = ["붕어", "고등어", "광어", "참다랑어", "돗돔", "황금 잉어"]
        total_earned = 0
        sold_summary = []

        for f in fish_list:
            count = u["inventory"].get(f, 0)
            if count > 0:
                p_info = fish_market.get(f, {"price": 1000})
                price = p_info["price"] if isinstance(p_info, dict) else p_info
                sum_val = price * count
                total_earned += sum_val
                u["inventory"][f] = 0
                sold_summary.append(f"{f} {count}개 ({sum_val:,}원)")

        if total_earned == 0:
            await interaction.response.send_message("❌ 매각할 물고기가 없습니다.", ephemeral=True)
            return

        u["money"] += total_earned
        save_data(data)

        embed = build_bag_embed(interaction.user, u)
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"💰 **[물고기 일괄 매도 완료]**\n• 내역: {', '.join(sold_summary)}\n• 총 정산: **+{total_earned:,}원**", ephemeral=True)

def build_bag_embed(user, u):
    data = load_data()
    fish_market = data["market"]["fish"]
    eq_rod_name = ROD_DATA[u.get("equipped_rod", 0)]["name"]

    embed = discord.Embed(title=f"🎒 {user.display_name}님의 가방", color=0x9b59b6)
    embed.set_thumbnail(url=user.display_avatar.url)

    lines = [f"🎣 **장착 낚싯대:** {eq_rod_name}\n"]

    arts = [f"{k} {v}개" for k, v in u["inventory"].items() if k in DEFAULT_MARKET["artifacts"] and v > 0]
    if arts:
        lines.append(f"🏛️ **유물:** {', '.join(arts)}")

    fish_items = ["붕어", "고등어", "광어", "참다랑어", "돗돔", "황금 잉어"]
    fishes = []
    total_fish_val = 0
    for f in fish_items:
        cnt = u["inventory"].get(f, 0)
        if cnt > 0:
            p_info = fish_market.get(f, {"price": 1000})
            price = p_info["price"] if isinstance(p_info, dict) else p_info
            total_fish_val += price * cnt
            fishes.append(f"{f} {cnt}개")
    if fishes:
        lines.append(f"🐟 **해산물 ({total_fish_val:,}원 상당):** {', '.join(fishes)}")

    con = [f"{k} {v}개" for k, v in u["inventory"].items() if k in ["에너지드링크", "핫식스 박스", "유물 랜덤 상자"] and v > 0]
    if con:
        lines.append(f"🥤 **소모품:** {', '.join(con)}")

    mats = [f"{k} {v}개" for k, v in u["inventory"].items() if k in ["강화석", "파괴 방지권", "하락 방지권"] and v > 0]
    if mats:
        lines.append(f"🛡️ **강화재료:** {', '.join(mats)}")

    junk = [f"{k} {v}개" for k, v in u["inventory"].items() if k in ["찢어진 장화", "썩은 미역", "빈 깡통"] and v > 0]
    if junk:
        lines.append(f"🗑️ **잡동사니:** {', '.join(junk)}")

    if len(lines) == 1:
        lines.append("📦 소지한 아이템이 없습니다.")

    embed.description = "\n".join(lines)
    return embed

def build_upgrade_embed(user, u, last_result_msg=None):
    curr_lvl = u["car_level"]

    if curr_lvl >= 31:
        embed = discord.Embed(title="🚘 정비소", description="✨ 최고 등급 **[부가티 라 부아튀르 누아르]** 달성!", color=0xf1c40f)
        return embed

    gold_cost, stone_cost, success_rate, destroy_rate, degrade_rate = get_upgrade_info(curr_lvl)

    embed = discord.Embed(
        title="🚘 자동차 강화 정비소",
        description=f"🚗 현재: **{get_car_name(curr_lvl)}** ➔ 목표: **{get_car_name(curr_lvl + 1)}**",
        color=0x3498db
    )

    if last_result_msg:
        embed.add_field(name="📢 최근 결과", value=last_result_msg, inline=False)

    prob_str = f"• 성공: **{success_rate}%**"
    if degrade_rate > 0: prob_str += f" | 하락: **{degrade_rate}%**"
    if destroy_rate > 0: prob_str += f" | 파괴: **{destroy_rate}%**"
    embed.add_field(name="📊 확률 스펙", value=prob_str, inline=False)

    mat_str = f"• 비용: **{gold_cost:,}원** (보유: {u['money']:,}원)\n• 필요 강화석: **{stone_cost}개** (보유: {u['inventory']['강화석']}개)"
    embed.add_field(name="🛠️ 강화 재료", value=mat_str, inline=False)

    prot_str = f"• 파괴 방지권: **{u['inventory']['파괴 방지권']}개** | 하락 방지권: **{u['inventory']['하락 방지권']}개**"
    embed.add_field(name="🛡️ 안전 방지권 현황", value=prot_str, inline=False)

    return embed

class UpgradeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id

    @discord.ui.button(label="⚔️ 강화하기", style=discord.ButtonStyle.green)
    async def do_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return

        data = load_data()
        u = get_user_data(data, interaction.user.id)
        curr_lvl = u["car_level"]

        if curr_lvl >= 31:
            await interaction.response.send_message("✨ 최상위 차량을 소유 중입니다!", ephemeral=True)
            return

        gold_cost, stone_cost, success_rate, destroy_rate, degrade_rate = get_upgrade_info(curr_lvl)

        if u["money"] < gold_cost:
            await interaction.response.send_message(f"❌ 골드가 부족합니다! ({gold_cost:,}원 필요)", ephemeral=True)
            return

        if stone_cost > 0 and u["inventory"]["강화석"] < stone_cost:
            await interaction.response.send_message(f"❌ 강화석이 부족합니다! ({stone_cost}개 필요)", ephemeral=True)
            return

        u["money"] -= gold_cost
        if stone_cost > 0:
            u["inventory"]["강화석"] -= stone_cost

        rand = random.random() * 100
        if rand < success_rate:
            u["car_level"] += 1
            result_msg = f"🎉 **강화 성공!!** [{get_car_name(u['car_level'])}]"
        else:
            if destroy_rate > 0 and (random.random() * 100 < destroy_rate):
                if u["inventory"]["파괴 방지권"] > 0:
                    u["inventory"]["파괴 방지권"] -= 1
                    result_msg = "💥 **강화 실패!** (파괴 방지권으로 폐차 방지)"
                else:
                    u["car_level"] = 0
                    result_msg = "💥 **강화 실패...** (차량 대파로 뚜벅이 리셋)"
            else:
                if u["inventory"]["하락 방지권"] > 0:
                    u["inventory"]["하락 방지권"] -= 1
                    result_msg = "📉 **강화 실패!** (하락 방지권으로 강등 방지)"
                else:
                    u["car_level"] = max(0, u["car_level"] - 1)
                    result_msg = f"📉 **강화 실패...** [{get_car_name(u['car_level'])}](으)로 강등"

        save_data(data)

        if u["car_level"] >= 31:
            for item in self.children: item.disabled = True

        embed = build_upgrade_embed(interaction.user, u, last_result_msg=result_msg)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ 종료", style=discord.ButtonStyle.red)
    async def stop_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 조작할 수 있습니다.", ephemeral=True)
            return
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(content="🛑 강화를 종료했습니다.", view=self)

class DiceDuelView(discord.ui.View):
    def __init__(self, host_user, bet_amount):
        super().__init__(timeout=180)
        self.host_user = host_user
        self.bet_amount = bet_amount
        self.completed = False
        self.message = None

    async def on_timeout(self):
        if not self.completed:
            data = load_data()
            u = get_user_data(data, self.host_user.id)
            u["money"] += self.bet_amount
            save_data(data)
            for item in self.children: item.disabled = True
            if self.message:
                try:
                    await self.message.edit(embed=discord.Embed(title="⏱️ 주사위 대결 취소", description="시간 초과로 판돈이 환불되었습니다.", color=0x7f8c8d), view=self)
                except Exception: pass

    @discord.ui.button(label="⚔️ 난입하기", style=discord.ButtonStyle.green)
    async def challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host_user.id:
            await interaction.response.send_message("❌ 본인 대결에는 참여할 수 없습니다.", ephemeral=True)
            return

        data = load_data()
        challenger = get_user_data(data, interaction.user.id)

        if challenger["money"] < self.bet_amount:
            await interaction.response.send_message(f"❌ 잔액이 부족합니다! ({self.bet_amount:,}원 필요)", ephemeral=True)
            return

        challenger["money"] -= self.bet_amount
        save_data(data)

        self.completed = True
        for item in self.children: item.disabled = True

        embed = discord.Embed(title="🎲 1v1 주사위 대결", description="🎲 주사위를 굴리는 중입니다...", color=0x3498db)
        await interaction.response.edit_message(embed=embed, view=self)

        await asyncio.sleep(1.5)
        host_roll = random.randint(1, 6)
        
        embed.description = f"👑 **{self.host_user.display_name}**: 🎲 **[{host_roll}]**\n⚔️ **{interaction.user.display_name}**: 🎲 굴리는 중..."
        await interaction.message.edit(embed=embed)

        await asyncio.sleep(1.5)
        challenger_roll = random.randint(1, 6)

        host_data = get_user_data(data, self.host_user.id)
        total_pot = self.bet_amount * 2

        if host_roll > challenger_roll:
            host_data["money"] += total_pot
            res_str = f"🎉 **{self.host_user.mention} 승리!** (+{total_pot:,}원)"
            color = 0x2ecc71
        elif challenger_roll > host_roll:
            challenger["money"] += total_pot
            res_str = f"🎉 **{interaction.user.mention} 승리!** (+{total_pot:,}원)"
            color = 0x2ecc71
        else:
            host_data["money"] += self.bet_amount
            challenger["money"] += self.bet_amount
            res_str = "🤝 **무승부!** (베팅금 100% 환불)"
            color = 0x95a5a6

        save_data(data)

        final_embed = discord.Embed(title="🎲 1v1 주사위 결과", color=color)
        final_embed.add_field(name=f"👑 {self.host_user.display_name}", value=f"🎲 **[{host_roll}]**", inline=True)
        final_embed.add_field(name=f"⚔️ {interaction.user.display_name}", value=f"🎲 **[{challenger_roll}]**", inline=True)
        final_embed.add_field(name="🏆 결과", value=res_str, inline=False)
        await interaction.message.edit(embed=final_embed)

class RPSPlayView(discord.ui.View):
    def __init__(self, host_user, challenger_user, bet_amount):
        super().__init__(timeout=120)
        self.host_user = host_user
        self.challenger_user = challenger_user
        self.bet_amount = bet_amount
        self.choices = {}

    @discord.ui.button(label="✌️ 가위", style=discord.ButtonStyle.primary)
    async def sci(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "✌️")

    @discord.ui.button(label="✊ 바위", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "✊")

    @discord.ui.button(label="🖐️ 보", style=discord.ButtonStyle.primary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "🖐️")

    async def process_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id not in [self.host_user.id, self.challenger_user.id]:
            await interaction.response.send_message("❌ 당사자만 선택할 수 있습니다.", ephemeral=True)
            return

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"✅ **{choice}** 제출 완료!", ephemeral=True)

        if len(self.choices) == 2:
            for item in self.children: item.disabled = True

            h_choice = self.choices[self.host_user.id]
            c_choice = self.choices[self.challenger_user.id]
            total_pot = self.bet_amount * 2

            data = load_data()
            h_data = get_user_data(data, self.host_user.id)
            c_data = get_user_data(data, self.challenger_user.id)

            rules = {"✌️": "🖐️", "✊": "✌️", "🖐️": "✊"}

            if h_choice == c_choice:
                h_data["money"] += self.bet_amount
                c_data["money"] += self.bet_amount
                res_str = "🤝 **무승부!** (베팅금 100% 환불)"
                color = 0x95a5a6
            elif rules[h_choice] == c_choice:
                h_data["money"] += total_pot
                res_str = f"🎉 **{self.host_user.mention} 승리!** (+{total_pot:,}원)"
                color = 0x2ecc71
            else:
                c_data["money"] += total_pot
                res_str = f"🎉 **{self.challenger_user.mention} 승리!** (+{total_pot:,}원)"
                color = 0x2ecc71

            save_data(data)

            embed = discord.Embed(title="⚔️ 가위바위보 승부 결과", color=color)
            embed.add_field(name=f"👑 {self.host_user.display_name}", value=h_choice, inline=True)
            embed.add_field(name=f"⚔️ {self.challenger_user.display_name}", value=c_choice, inline=True)
            embed.add_field(name="🏆 결과", value=res_str, inline=False)
            await interaction.message.edit(content=None, embed=embed, view=self)

class RPSLobbyView(discord.ui.View):
    def __init__(self, host_user, bet_amount):
        super().__init__(timeout=180)
        self.host_user = host_user
        self.bet_amount = bet_amount

    @discord.ui.button(label="⚔️ 참가하기", style=discord.ButtonStyle.green)
    async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host_user.id:
            await interaction.response.send_message("❌ 본인 방에는 참가할 수 없습니다.", ephemeral=True)
            return

        data = load_data()
        c_data = get_user_data(data, interaction.user.id)

        if c_data["money"] < self.bet_amount:
            await interaction.response.send_message(f"❌ 잔액이 부족합니다! ({self.bet_amount:,}원 필요)", ephemeral=True)
            return

        c_data["money"] -= self.bet_amount
        save_data(data)

        play_view = RPSPlayView(self.host_user, interaction.user, self.bet_amount)
        embed = discord.Embed(
            title="⚔️ 1v1 가위바위보 대결 진행 중",
            description=f"**{self.host_user.display_name}** VS **{interaction.user.display_name}**\n판돈: **{self.bet_amount * 2:,}원**\n\n아래 버튼을 눌러 비공개로 선택하세요!",
            color=0xe67e22
        )
        await interaction.response.edit_message(embed=embed, view=play_view)

class HorseRaceView(discord.ui.View):
    def __init__(self, host_user, bet_amount):
        super().__init__(timeout=300)
        self.host_user = host_user
        self.bet_amount = bet_amount
        self.horses = {1: "지성호", 2: "떡상호", 3: "깡통호", 4: "폭주호"}
        self.participants = {}

    def build_embed(self):
        embed = discord.Embed(title="🏇 실시간 경마장 대기실", description=f"판돈: **{self.bet_amount:,}원** (최소 2명 출전 가능)", color=0xe67e22)
        for num, name in self.horses.items():
            user = self.participants.get(num)
            user_str = user.mention if user else "[ 빈자리 ]"
            embed.add_field(name=f"{num}번마 {name}", value=user_str, inline=True)
        return embed

    async def add_participant(self, interaction: discord.Interaction, horse_num: int):
        if interaction.user.id in [u.id for u in self.participants.values()]:
            await interaction.response.send_message("❌ 마권은 1장만 구매 가능합니다.", ephemeral=True)
            return

        if horse_num in self.participants:
            await interaction.response.send_message("❌ 이미 선택된 말입니다.", ephemeral=True)
            return

        data = load_data()
        u = get_user_data(data, interaction.user.id)

        if interaction.user.id != self.host_user.id:
            if u["money"] < self.bet_amount:
                await interaction.response.send_message(f"❌ 잔액이 부족합니다! ({self.bet_amount:,}원 필요)", ephemeral=True)
                return
            u["money"] -= self.bet_amount
            save_data(data)

        self.participants[horse_num] = interaction.user
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🥇 1번마", style=discord.ButtonStyle.primary, row=0)
    async def h1(self, interaction, button): await self.add_participant(interaction, 1)

    @discord.ui.button(label="🥈 2번마", style=discord.ButtonStyle.primary, row=0)
    async def h2(self, interaction, button): await self.add_participant(interaction, 2)

    @discord.ui.button(label="🥉 3번마", style=discord.ButtonStyle.primary, row=0)
    async def h3(self, interaction, button): await self.add_participant(interaction, 3)

    @discord.ui.button(label="🏅 4번마", style=discord.ButtonStyle.primary, row=0)
    async def h4(self, interaction, button): await self.add_participant(interaction, 4)

    @discord.ui.button(label="🏁 경주 시작", style=discord.ButtonStyle.green, row=1)
    async def start_race(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_user.id:
            await interaction.response.send_message("❌ 방장만 시작할 수 있습니다.", ephemeral=True)
            return

        if len(self.participants) < 2:
            await interaction.response.send_message("❌ 최소 2명 이상 참여해야 합니다!", ephemeral=True)
            return

        for item in self.children: item.disabled = True
        await interaction.response.edit_message(view=self)

        distances = {num: 0 for num in self.participants.keys()}
        total_pot = len(self.participants) * self.bet_amount
        winner_num = None

        legend_str = " | ".join([f"**{num}번**: {user.display_name}" for num, user in self.participants.items()])

        while not winner_num:
            await asyncio.sleep(1.2)
            race_str = f"🏇 **참가 선수:** {legend_str}\n\n"
            for num in self.participants.keys():
                distances[num] += random.randint(12, 28)
                dist = min(100, distances[num])
                filled = dist // 10
                bar = "─" * filled + "🏇" + "─" * (10 - filled)
                race_str += f"`{num}번` 🏁{bar} `[{dist}m]`\n"

                if dist >= 100 and not winner_num:
                    winner_num = num

            embed = discord.Embed(title="🏇 실시간 레이스 진행 중!!", description=race_str, color=0xe67e22)
            await interaction.message.edit(embed=embed)

        winner_user = self.participants[winner_num]
        data = load_data()
        w_data = get_user_data(data, winner_user.id)
        w_data["money"] += total_pot
        save_data(data)

        win_embed = discord.Embed(title="🏆 경마 종료!", color=0xf1c40f)
        win_embed.add_field(name="🥇 우승", value=f"**{winner_num}번마 {self.horses[winner_num]}** ({winner_user.mention})", inline=False)
        win_embed.add_field(name="💰 상금", value=f"총 **+{total_pot:,}원** 독식!", inline=False)
        await interaction.message.edit(embed=win_embed)

class CatchFishButton(discord.ui.Button):
    def __init__(self, user_id, target_time):
        super().__init__(label="🎣 낚아채기!", style=discord.ButtonStyle.success)
        self.user_id = user_id
        self.target_time = target_time

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인의 찌만 건질 수 있습니다.", ephemeral=True)
            return

        now = datetime.now().timestamp()
        if now > self.target_time + 3.5:
            await interaction.response.edit_message(content="🐟 반응이 늦어 물고기가 도망쳤습니다...", view=None)
            return

        data = load_data()
        u = get_user_data(data, interaction.user.id)
        rod_id = u.get("equipped_rod", 0)

        rates = ROD_DATA[rod_id]["rates"]
        trash_r, norm_r, rare_r, leg_r, box_r = rates
        rand = random.uniform(0, 100)

        embed_color = 0x2ecc71
        img_file = "낚시_붕어.png"

        if rand < box_r:
            box_rand = random.choice(["gold", "stone", "artifact"])
            if box_rand == "gold":
                g = random.randint(50000, 150000)
                u["money"] += g
                res_title = "🎁 [보물] 침몰한 보물상자"
                res_desc = f"보물상자에서 💰 **+{g:,}원** 획득!"
            elif box_rand == "stone":
                s = random.randint(3, 5)
                u["inventory"]["강화석"] += s
                res_title = "🎁 [보물] 침몰한 보물상자"
                res_desc = f"보물상자에서 ✨ **강화석 {s}개** 획득!"
            else:
                arts = ["똥먹방 비법서", "차은우지성 조각상", "170KG 비법서", "곤지암병원 지도", "L을 가져가 비법서"]
                art = random.choice(arts)
                u["inventory"][art] += 1
                res_title = "🎁 [보물] 침몰한 보물상자"
                res_desc = f"보물상자에서 🏛️ **【 {art} 】** 발굴!"
            embed_color, img_file = 0xf1c40f, "낚시_보물상자.png"

        elif rand < (box_r + leg_r):
            u["inventory"]["황금 잉어"] += 1
            res_title = "👑 [전설] 황금 잉어"
            res_desc = "황금 잉어를 낚아 가방에 보관했습니다!"
            embed_color, img_file = 0xf1c40f, "낚시_황금잉어.png"

        elif rand < (box_r + leg_r + rare_r):
            fish = random.choice(["참다랑어", "돗돔"])
            u["inventory"][fish] += 1
            res_title = f"🐠 [희귀] {fish}"
            res_desc = f"{fish}을(를) 낚아 가방에 보관했습니다!"
            embed_color = 0x3498db
            img_file = f"낚시_{fish}.png"

        elif rand < (box_r + leg_r + rare_r + norm_r):
            fish = random.choice(["붕어", "고등어", "광어"])
            u["inventory"][fish] += 1
            res_title = f"🐟 [일반] {fish}"
            res_desc = f"{fish}을(를) 낚아 가방에 보관했습니다!"
            img_file = f"낚시_{fish}.png"

        else:
            trash = random.choice(["찢어진 장화", "썩은 미역", "빈 깡통"])
            u["inventory"][trash] += 1
            res_title = f"🗑️ {trash}"
            res_desc = f"{trash}을(를) 낚았습니다..."
            embed_color = 0x95a5a6
            img_file = "낚시_쓰레기.png"

        u["fish_count"] = u.get("fish_count", 0) + 1
        update_fish_level(u)

        save_data(data)

        res_embed = discord.Embed(title=res_title, description=res_desc, color=embed_color)
        res_embed.set_image(url=get_img_url(img_file))
        res_embed.set_footer(text=f"⏱️ 남은 피로도: {u['fatigue']}/100 | 🎣 낚시 Lv.{u['fish_level']} ({u['fish_count']}회)")
        await interaction.response.edit_message(content=None, embed=res_embed, view=None)

# ---------------------------------------------------------
# 7. 봇 동기화 이벤트
# ---------------------------------------------------------
@bot.event
async def on_ready():
    if not update_artifact_and_fish_prices.is_running(): update_artifact_and_fish_prices.start()
    if not update_stock_prices.is_running(): update_stock_prices.start()
    if not daily_reset.is_running(): daily_reset.start()
    try:
        synced = await bot.tree.sync()
        print(f"✅ 동기화 완료! 총 {len(synced)}개의 슬래시 명령어가 동작 중입니다.")
    except Exception as e:
        print(f"동기화 오류: {e}")

# ---------------------------------------------------------
# 8. 전체 슬래시 명령어
# ---------------------------------------------------------

# 1) /내정보 (초슬림 개편)
@bot.tree.command(name="내정보", description="내 재산, 피로도, 차, 장착 낚싯대 및 숙련도 정보를 확인합니다.")
async def my_info(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    total_wealth = u["money"]
    for art, count in u["inventory"].items():
        if art in data["market"]["artifacts"]:
            p = data["market"]["artifacts"][art]
            price = p["price"] if isinstance(p, dict) else p
            total_wealth += price * count
    for st, count in u["stocks"].items():
        if st in data["market"]["stocks"]:
            p = data["market"]["stocks"][st]
            price = p["price"] if isinstance(p, dict) else p
            total_wealth += price * count

    embed = discord.Embed(title=f"👤 {interaction.user.display_name}님의 프로필", color=0x3498db)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    eq_rod_name = ROD_DATA[u.get("equipped_rod", 0)]["name"]

    desc = (
        f"• **현금:** {u['money']:,}원 | **총자산:** {total_wealth:,}원\n"
        f"• **피로도:** {get_fatigue_bar(u['fatigue'])}\n"
        f"• **장비:** {get_car_name(u['car_level'])} | {eq_rod_name}\n"
        f"• **숙련도:** 🕺 춤 Lv.{u['dance_level']} ({u['dance_count']}회) | 🎣 낚시 Lv.{u['fish_level']} ({u['fish_count']}회)\n"
        f"• **연속 출석:** {u['attendance_streak']}일째"
    )
    embed.description = desc
    await interaction.response.send_message(embed=embed)

# 2) /가방 (자기자신만 볼 수 있게 ephemeral=True)
@bot.tree.command(name="가방", description="소지품 확인, 소모품 사용 및 물고기 일괄 매도를 진행합니다.")
async def bag(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    embed = build_bag_embed(interaction.user, u)
    view = BagView(interaction.user.id, u.get("owned_rods", [0]))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# 3) /주식
@bot.tree.command(name="주식", description="실시간 주식 시세를 확인하고 바로 매수/매도합니다.")
async def stock_dashboard(interaction: discord.Interaction):
    embed = build_stock_embed(interaction.user)
    view = StockView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

# 4) /유물
@bot.tree.command(name="유물", description="실시간 고대 유물 시세를 확인하고 바로 매도합니다.")
async def artifact_dashboard(interaction: discord.Interaction):
    embed = build_artifact_embed(interaction.user)
    view = ArtifactView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

# 5) /출석체크
@bot.tree.command(name="출석체크", description="매일 출석체크를 하여 연속 보상을 받습니다.")
async def attendance(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    yesterday_str = (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")

    if u["last_check_date"] == today_str:
        await interaction.response.send_message("❌ 오늘은 이미 출석체크를 완료했습니다!", ephemeral=True)
        return

    if u["last_check_date"] == yesterday_str:
        u["attendance_streak"] += 1
    else:
        u["attendance_streak"] = 1

    streak = u["attendance_streak"]
    if streak in [1, 2]: reward = 5000
    elif streak in [3, 4, 5]: reward = 10000
    elif streak in [6, 7, 8, 9]: reward = 20000
    else: reward = 30000

    u["money"] += reward
    u["last_check_date"] = today_str
    save_data(data)

    embed = discord.Embed(title="📅 출석체크 완료!", color=0x2ecc71)
    embed.set_thumbnail(url=get_img_url("출석체크.png"))
    embed.description = f"• 연속 출석: **{streak}일째**\n• 보상: 💰 **+{reward:,}원** (잔액: {u['money']:,}원)"
    await interaction.response.send_message(embed=embed)

# 6) /송금
@bot.tree.command(name="송금", description="서버 유저에게 돈을 보냅니다. (10% 수수료, 하루 3회)")
async def transfer(interaction: discord.Interaction, 받으실분: discord.Member, 금액: int):
    if 금액 <= 0:
        await interaction.response.send_message("❌ 1원 이상 송금 가능합니다.", ephemeral=True)
        return
    if 받으실분.id == interaction.user.id:
        await interaction.response.send_message("❌ 자기 자신에게는 송금할 수 없습니다.", ephemeral=True)
        return
    if 받으실분.bot:
        await interaction.response.send_message("❌ 봇에게는 송금할 수 없습니다.", ephemeral=True)
        return

    data = load_data()
    sender = get_user_data(data, interaction.user.id)
    receiver = get_user_data(data, 받으실분.id)

    if sender["remittance_count_today"] >= 3:
        await interaction.response.send_message("❌ 오늘 일일 송금 횟수(3회)를 모두 사용하셨습니다.", ephemeral=True)
        return

    if sender["money"] < 금액:
        await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
        return

    fee = int(금액 * 0.10)
    actual_amount = 금액 - fee

    sender["money"] -= 금액
    receiver["money"] += actual_amount
    sender["remittance_count_today"] += 1

    save_data(data)

    embed = discord.Embed(title="💸 송금 완료", color=0x3498db)
    embed.description = (
        f"• **보낸 사람:** {interaction.user.mention} ➔ **받은 사람:** {받으실분.mention}\n"
        f"• **송금액:** {금액:,}원 (수수료 10%: -{fee:,}원)\n"
        f"• **실수령액:** **{actual_amount:,}원** (남은 송금 횟수: {3 - sender['remittance_count_today']}회)"
    )
    await interaction.response.send_message(embed=embed)

# 7) /춤추기 (Lv.5 만렙 유지)
@bot.tree.command(name="춤추기", description="춤을 춰서 돈, 유물, 강화석을 얻습니다.")
async def dance(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    cooldowns = [60, 50, 45, 40, 35, 30]
    fatigue_cost = 4 if u["dance_level"] >= 3 else 5
    cd = cooldowns[min(u["dance_level"], 5)]

    now = datetime.now().timestamp()
    if now - u["last_dance_time"] < cd:
        remain = int(cd - (now - u["last_dance_time"]))
        await interaction.response.send_message(f"⏳ 지쳤습니다! {remain}초 후 다시 가능합니다.", ephemeral=True)
        return

    if u["fatigue"] < fatigue_cost:
        await interaction.response.send_message("❌ 피로도가 부족합니다!", ephemeral=True)
        return

    u["fatigue"] -= fatigue_cost
    u["last_dance_time"] = now
    u["dance_count"] += 1

    reqs = [50, 150, 300, 500, 750]
    for i, req in enumerate(reqs):
        if u["dance_count"] >= req:
            u["dance_level"] = max(u["dance_level"], i + 1)

    rand = random.random() * 100
    msg, reward_str, embed_color, img_file = "", "", 0x2ecc71, "춤_일반.png"

    if rand < 25:
        u["money"] += 500
        msg = "소소하게 엉덩이를 털어 동전을 얻었다."
        reward_str, img_file = "💰 +500원", "춤_일반.png"
    elif rand < 60:
        u["money"] += 1000
        msg = "길거리에서 뻣뻣한 춤을 췄다."
        reward_str, img_file = "💰 +1,000원", "춤_일반.png"
    elif rand < 75:
        u["money"] += 3000
        msg = "현란한 팝핀을 선보였다!"
        reward_str, embed_color, img_file = "💰 +3,000원", 0x3498db, "춤_레어.png"
    elif rand < 85:
        u["money"] += 5000
        msg = "디스코 댄스를 폭발시켰다!"
        reward_str, embed_color, img_file = "💰 +5,000원", 0x3498db, "춤_레어.png"
    elif rand < 92:
        u["money"] += 10000
        msg = "★대폭발★ 클럽 분위기를 연출했다!"
        reward_str, embed_color, img_file = "💰 +10,000원", 0x9b59b6, "춤_에픽.png"
    elif rand < 95:
        u["money"] += 50000
        msg = "중력을 무시하는 브레이크 댄스!"
        reward_str, embed_color, img_file = "💰 +50,000원", 0x9b59b6, "춤_에픽.png"
    elif rand < 97:
        u["money"] += 100000
        msg = "✨[전설의 춤신춤왕]✨ 디스코 볼이 돈다!"
        reward_str, embed_color, img_file = "💰 +100,000원", 0xf1c40f, "춤_전설.png"
    elif rand < 98:
        u["inventory"]["강화석"] += 1
        msg = "✨ 춤추던 중 바닥에서 강화석을 주웠다!"
        reward_str, embed_color, img_file = "✨ 강화석 1개", 0xe67e22, "춤_강화석.png"
    else:
        artifacts = ["똥먹방 비법서", "차은우지성 조각상", "170KG 비법서", "곤지암병원 지도", "L을 가져가 비법서"]
        art = random.choice(artifacts)
        u["inventory"][art] += 1
        msg = f"✨ 고대의 유물 【 {art} 】을(를) 발굴했다!"
        reward_str, embed_color = f"🏛️ {art} 1개", 0xf1c40f
        art_map = {
            "똥먹방 비법서": "유물_똥먹방비법서.png",
            "차은우지성 조각상": "유물_차은우지성조각상.png",
            "170KG 비법서": "유물_170KG비법서.png",
            "곤지암병원 지도": "유물_곤지암병원지도.png",
            "L을 가져가 비법서": "유물_L을가져가비법서.png"
        }
        img_file = art_map.get(art, "춤_일반.png")

    save_data(data)
    embed = discord.Embed(title="🕺 춤추기 완료", description=f"{msg}\n• 보상: **{reward_str}**", color=embed_color)
    embed.set_image(url=get_img_url(img_file))
    embed.set_footer(text=f"남은 피로도: {u['fatigue']}/100 | 춤 Lv.{u['dance_level']}")
    await interaction.response.send_message(embed=embed)

# 8) /상점
@bot.tree.command(name="상점", description="회복제, 유물상자, 강화재료 및 낚싯대를 구매합니다.")
@app_commands.choices(품목=[
    app_commands.Choice(name="🥤 에너지드링크 (+30 피로도) - 10,000원", value="에너지드링크"),
    app_commands.Choice(name="⚡ 핫식스 박스 (+100 피로도 완충) - 30,000원", value="핫식스 박스"),
    app_commands.Choice(name="📦 유물 랜덤 상자 - 80,000원", value="유물 랜덤 상자"),
    app_commands.Choice(name="✨ 강화석 팩 (10개) - 150,000원", value="강화석 팩"),
    app_commands.Choice(name="🛡️ 파괴 방지권 - 40,000원", value="파괴 방지권"),
    app_commands.Choice(name="📉 하락 방지권 - 20,000원", value="하락 방지권"),
    app_commands.Choice(name="🎣 대나무 낚싯대 (피로도 7 소모) - 30,000원", value="대나무 낚싯대"),
    app_commands.Choice(name="🎣 카본 낚싯대 (피로도 9 소모) - 150,000원", value="카본 낚싯대"),
    app_commands.Choice(name="🎣 티타늄 낚싯대 (피로도 12 소모) - 500,000원", value="티타늄 낚싯대"),
    app_commands.Choice(name="✨ 트라이아나 (피로도 15 소모) - 2,000,000원", value="트라이아나")
])
async def shop(interaction: discord.Interaction, 품목: str, 개수: int = 1):
    if 개수 <= 0:
        await interaction.response.send_message("❌ 1개 이상 입력하세요.", ephemeral=True)
        return

    data = load_data()
    u = get_user_data(data, interaction.user.id)

    rod_buy_map = {"대나무 낚싯대": 1, "카본 낚싯대": 2, "티타늄 낚싯대": 3, "트라이아나": 4}

    if 품목 in rod_buy_map:
        rod_id = rod_buy_map[품목]
        cost = ROD_DATA[rod_id]["price"]
        if rod_id in u.get("owned_rods", [0]):
            await interaction.response.send_message("❌ 이미 소유한 낚싯대입니다!", ephemeral=True)
            return

        if u["money"] < cost:
            await interaction.response.send_message(f"❌ 소지금이 부족합니다. ({cost:,}원 필요)", ephemeral=True)
            return

        u["money"] -= cost
        u["owned_rods"].append(rod_id)
        u["equipped_rod"] = rod_id
        save_data(data)

        await interaction.response.send_message(f"🎣 **[{ROD_DATA[rod_id]['name']}]** 구매 및 자동 장착 완료!")
        return

    prices = {
        "에너지드링크": 10000, "핫식스 박스": 30000, "유물 랜덤 상자": 80000,
        "강화석 팩": 150000, "파괴 방지권": 40000, "하락 방지권": 20000
    }
    shop_img_map = {
        "에너지드링크": "상점_에너지드링크.png", "핫식스 박스": "상점_핫식스.png",
        "유물 랜덤 상자": "상점_유물상자.png", "강화석 팩": "상점_강화석.png",
        "파괴 방지권": "상점_파괴방지권.png", "하락 방지권": "상점_하락방지권.png"
    }

    cost = prices[품목] * 개수
    if u["money"] < cost:
        await interaction.response.send_message(f"❌ 소지금이 부족합니다. ({cost:,}원 필요)", ephemeral=True)
        return

    u["money"] -= cost
    if 품목 == "강화석 팩": u["inventory"]["강화석"] += 10 * 개수
    else: u["inventory"][품목] += 개수

    save_data(data)
    embed = discord.Embed(title="🛒 상점 구매 완료", description=f"[{품목}] {개수}개 구매 완료! (-{cost:,}원)", color=0x2ecc71)
    embed.set_thumbnail(url=get_img_url(shop_img_map.get(품목, "상점_강화석.png")))
    await interaction.response.send_message(embed=embed)

# 9) /도박
@bot.tree.command(name="도박", description="게임 컨셉의 도박을 진행합니다.")
@app_commands.choices(종류=[
    app_commands.Choice(name="⛏️ 마인크래프트 (초안전형)", value="마크"),
    app_commands.Choice(name="⚔️ 리그 오브 레전드 (밸런스형)", value="롤"),
    app_commands.Choice(name="🔫 발로란트 (고위험형)", value="발로란트"),
    app_commands.Choice(name="🕺 권루트 (극단적 초고위험 200배)", value="권루트")
])
async def gamble(interaction: discord.Interaction, 종류: str, 베팅금: int):
    if 베팅금 < 1000:
        await interaction.response.send_message("❌ 최소 베팅금은 **1,000원** 이상입니다.", ephemeral=True)
        return

    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if u["money"] < 베팅금:
        await interaction.response.send_message(f"❌ 현금이 부족합니다! (필요: {베팅금:,}원 / 보유: {u['money']:,}원)", ephemeral=True)
        return

    u["money"] -= 베팅금

    await interaction.response.defer()
    
    if 종류 == "마크": load_desc = "⛏️ 깊은 굴을 파고 들어가는 중..."
    elif 종류 == "롤": load_desc = "⚔️ 소환사의 협곡에 입장하는 중..."
    elif 종류 == "발로란트": load_desc = "🔫 에임 조준하는 중..."
    elif 종류 == "권루트": load_desc = "🕺 권루트 댄스를 시전하는 중..."

    loading_embed = discord.Embed(title="🎰 도박 진행 중...", description=load_desc, color=0x95a5a6)
    loading_embed.set_thumbnail(url=get_img_url(f"도박_{종류}.png"))

    msg = await interaction.followup.send(embed=loading_embed)
    await asyncio.sleep(1.5)

    rand = random.random() * 100
    mult, result_title, embed_color, img_file = 0, "", 0x2ecc71, f"도박_{종류}.png"

    if 종류 == "마크":
        if rand < 0.2: mult, result_title, embed_color, img_file = 30, "🔹 엔더드래곤", 0xf1c40f, "마크_엔더드래곤.png"
        elif rand < 4.2: mult, result_title, embed_color, img_file = 5, "🔹 네더라이트", 0x9b59b6, "마크_네더라이트.png"
        elif rand < 14.2: mult, result_title, embed_color, img_file = 2, "🔹 다이아몬드", 0x3498db, "마크_다이아.png"
        elif rand < 43.0: mult, result_title, embed_color, img_file = 1, "🔹 철 발견", 0x2ecc71, "마크_철.png"
        elif rand < 55.0: mult, result_title, embed_color, img_file = 0, "⬛ 평화로운 하루", 0x95a5a6, "마크_평화.png"
        elif rand < 84.0: mult, result_title, embed_color, img_file = -1, "🔸 크리퍼 폭발", 0xe74c3c, "마크_크리퍼.png"
        elif rand < 95.0: mult, result_title, embed_color, img_file = -2, "🔸 용암 사망", 0xe74c3c, "마크_용암.png"
        else: mult, result_title, embed_color, img_file = -5, "🔸 정전 / 엄크", 0x2c3e50, "마크_엄크.png"

    elif 종류 == "롤":
        if rand < 0.02: mult, result_title, embed_color, img_file = 100, "🔹 챌린저", 0xf1c40f, "롤_챌린저.png"
        elif rand < 0.06: mult, result_title, embed_color, img_file = 50, "🔹 그랜드마스터", 0xf1c40f, "롤_그랜드마스터.png"
        elif rand < 0.40: mult, result_title, embed_color, img_file = 20, "🔹 마스터", 0x9b59b6, "롤_마스터.png"
        elif rand < 3.00: mult, result_title, embed_color, img_file = 5, "🔹 다이아몬드", 0x3498db, "롤_다이아.png"
        elif rand < 8.00: mult, result_title, embed_color, img_file = 3, "🔹 에메랄드", 0x2ecc71, "롤_에메랄드.png"
        elif rand < 17.5: mult, result_title, embed_color, img_file = 2, "🔹 플래티넘", 0x2ecc71, "롤_플래티넘.png"
        elif rand < 45.5: mult, result_title, embed_color, img_file = 1, "🔹 골드", 0x2ecc71, "롤_골드.png"
        elif rand < 75.5: mult, result_title, embed_color, img_file = -1, "🔸 실버", 0xe74c3c, "롤_실버.png"
        elif rand < 95.5: mult, result_title, embed_color, img_file = -2, "🔸 브론즈", 0xe74c3c, "롤_브론즈.png"
        else: mult, result_title, embed_color, img_file = -5, "🔸 아이언", 0x2c3e50, "롤_아이언.png"

    elif 종류 == "발로란트":
        if rand < 0.02: mult, result_title, embed_color, img_file = 100, "🔹 레디언트", 0xf1c40f, "발로란트_레디언트.png"
        elif rand < 0.06: mult, result_title, embed_color, img_file = 50, "🔹 불멸", 0xf1c40f, "발로란트_불멸.png"
        elif rand < 0.40: mult, result_title, embed_color, img_file = 20, "🔹 초월자", 0x9b59b6, "발로란트_초월자.png"
        elif rand < 4.00: mult, result_title, embed_color, img_file = 5, "🔹 다이아몬드", 0x3498db, "롤_다이아.png"
        elif rand < 13.5: mult, result_title, embed_color, img_file = 2, "🔹 플래티넘", 0x2ecc71, "롤_플래티넘.png"
        elif rand < 45.5: mult, result_title, embed_color, img_file = 1, "🔹 골드", 0x2ecc71, "롤_골드.png"
        elif rand < 75.5: mult, result_title, embed_color, img_file = -1, "🔸 실버", 0xe74c3c, "롤_실버.png"
        elif rand < 95.5: mult, result_title, embed_color, img_file = -2, "🔸 브론즈", 0xe74c3c, "롤_브론즈.png"
        else: mult, result_title, embed_color, img_file = -5, "🔸 아이언", 0x2c3e50, "롤_아이언.png"

    elif 종류 == "권루트":
        if rand < 0.01: mult, result_title, embed_color, img_file = 200, "🔹 L을 가져가~", 0xf1c40f, "권루트_L을가져가.png"
        elif rand < 0.04: mult, result_title, embed_color, img_file = 80, "🔹 측면 대 측면", 0xf1c40f, "권루트_측면대측면.png"
        elif rand < 0.30: mult, result_title, embed_color, img_file = 30, "🔹 셀카", 0x9b59b6, "권루트_셀카.png"
        elif rand < 3.00: mult, result_title, embed_color, img_file = 10, "🔹 팁 토", 0x3498db, "권루트_팁토.png"
        elif rand < 10.0: mult, result_title, embed_color, img_file = 3, "🔹 기분에 따라", 0x2ecc71, "권루트_기분에따라.png"
        elif rand < 30.0: mult, result_title, embed_color, img_file = 1.5, "🔹 라운드 앤 라운드", 0x2ecc71, "권루트_라운드앤라운드.png"
        elif rand < 65.0: mult, result_title, embed_color, img_file = -1, "🔸 애를 가져가~", 0xe74c3c, "권루트_애를가져가.png"
        elif rand < 90.0: mult, result_title, embed_color, img_file = -3, "🔸 스텝 댄싱", 0xe74c3c, "권루트_스텝댄싱.png"
        else: mult, result_title, embed_color, img_file = -10, "💥 포탈 오류 (전재산 파산)", 0x2c3e50, "권루트_포탈오류.png"

    if mult > 0:
        payout = int(베팅금 * mult)
        u["money"] += payout
        net = payout - 베팅금
        if net > 0: res_str = f"🎉 **+{net:,}원** 이득! (당첨금: {payout:,}원)"
        elif net == 0: res_str = "⬛ **손익 없음** (원금 보존)"
        else: res_str = f"💥 **-{abs(net):,}원** 손실..."
    elif mult == 0:
        res_str = f"💥 **-{베팅금:,}원** 손실..."
    else:
        extra_loss = int(베팅금 * (abs(mult) - 1))
        u["money"] -= extra_loss
        total_loss = 베팅금 + extra_loss
        res_str = f"💥 **-{total_loss:,}원** 손실..."

    save_data(data)

    res_embed = discord.Embed(title=f"🎰 {종류} 도박 결과", description=f"결과: **{result_title}**\n• {res_str}\n• 현재 잔액: **{u['money']:,}원**", color=embed_color)
    res_embed.set_thumbnail(url=get_img_url(img_file))
    await msg.edit(embed=res_embed)

# 10) /도박확률
@bot.tree.command(name="도박확률", description="도박 종류별 당첨 확률과 배율 안내표를 확인합니다.")
async def gamble_rates(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 도박 종류별 확률 & 배율표", color=0x3498db)
    
    mc_info = (
        "• 엔더드래곤 (0.2% / x30) | 네더라이트 (4.0% / x5)\n"
        "• 다이아몬드 (10.0% / x2) | 철 발견 (28.8% / x1)\n"
        "• 평화로운 하루 (12.0% / x0) | 크리퍼 폭발 (29.0% / -x1)\n"
        "• 용암 사망 (11.0% / -x2) | 정전/엄크 (5.0% / -x5)"
    )
    lol_info = (
        "• 챌린저 (0.02% / x100) | 그랜드마스터 (0.04% / x50)\n"
        "• 마스터 (0.34% / x20) | 다이아몬드 (2.60% / x5)\n"
        "• 에메랄드 (5.00% / x3) | 플래티넘 (9.50% / x2)\n"
        "• 골드 (28.00% / x1) | 실버 (30.00% / -x1)\n"
        "• 브론즈 (20.00% / -x2) | 아이언 (4.50% / -x5)"
    )
    val_info = (
        "• 레디언트 (0.02% / x100) | 불멸 (0.04% / x50)\n"
        "• 초월자 (0.34% / x20) | 다이아몬드 (3.60% / x5)\n"
        "• 플래티넘 (9.50% / x2) | 골드 (32.00% / x1)\n"
        "• 실버 (30.00% / -x1) | 브론즈 (20.00% / -x2)\n"
        "• 아이언 (4.50% / -x5)"
    )
    kwon_info = (
        "• L을 가져가~ (0.01% / x200) | 측면 대 측면 (0.03% / x80)\n"
        "• 셀카 (0.26% / x30) | 팁 토 (2.70% / x10)\n"
        "• 기분에 따라 (7.00% / x3) | 라운드 앤 라운드 (20.00% / x1.5)\n"
        "• 애를 가져가~ (35.00% / -x1) | 스텝 댄싱 (25.00% / -x3)\n"
        "• 포탈 오류 (10.00% / -x10)"
    )

    embed.add_field(name="⛏️ 마인크래프트 (초안전형)", value=mc_info, inline=False)
    embed.add_field(name="⚔️ 리그 오브 레전드 (밸런스형)", value=lol_info, inline=False)
    embed.add_field(name="🔫 발로란트 (고위험형)", value=val_info, inline=False)
    embed.add_field(name="🕺 권루트 (극단적 초고위험 200배)", value=kwon_info, inline=False)

    await interaction.response.send_message(embed=embed)

# 11) /강화
@bot.tree.command(name="강화", description="자동차 정비소를 열어 차를 연속으로 강화합니다.")
async def upgrade(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    embed = build_upgrade_embed(interaction.user, u)
    view = UpgradeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

# 12) /순위
@bot.tree.command(name="순위", description="부자 및 소유 차 랭킹을 확인합니다.")
@app_commands.choices(종류=[
    app_commands.Choice(name="💰 부자 랭킹", value="부자"),
    app_commands.Choice(name="🚘 자동차 랭킹", value="차")
])
async def ranking(interaction: discord.Interaction, 종류: str):
    data = load_data()
    users = data["users"]

    if 종류 == "부자":
        rank_list = []
        for uid, u in users.items():
            total = u["money"]
            for art, count in u["inventory"].items():
                if art in data["market"]["artifacts"]:
                    art_info = data["market"]["artifacts"][art]
                    price = art_info["price"] if isinstance(art_info, dict) else art_info
                    total += price * count
            for st, count in u["stocks"].items():
                if st in data["market"]["stocks"]:
                    st_info = data["market"]["stocks"][st]
                    price = st_info["price"] if isinstance(st_info, dict) else st_info
                    total += price * count
            rank_list.append((uid, total))

        rank_list.sort(key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="🏆 서버 부자 랭킹 TOP 10", color=0xf1c40f)
        for i, (uid, val) in enumerate(rank_list[:10]):
            embed.add_field(name=f"{i+1}위", value=f"<@{uid}>: **{val:,}원**", inline=False)

    else:
        rank_list = [(uid, u.get("car_level", 0)) for uid, u in users.items()]
        rank_list.sort(key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="🏆 서킷 명예의 전당 TOP 10 (차 랭킹)", color=0xe67e22)
        for i, (uid, lvl) in enumerate(rank_list[:10]):
            embed.add_field(name=f"{i+1}위", value=f"<@{uid}>: **{get_car_name(lvl)}**", inline=False)

    await interaction.response.send_message(embed=embed)

# 13) /주사위대결
@bot.tree.command(name="주사위대결", description="다른 유저와 돈을 걸고 1v1 주사위 대결을 신청합니다.")
async def dice_duel(interaction: discord.Interaction, 베팅금: int):
    if 베팅금 < 1000:
        await interaction.response.send_message("❌ 최소 베팅금은 **1,000원** 이상입니다.", ephemeral=True)
        return

    data = load_data()
    host = get_user_data(data, interaction.user.id)

    if host["money"] < 베팅금:
        await interaction.response.send_message(f"❌ 잔액이 부족합니다! ({베팅금:,}원 필요)", ephemeral=True)
        return

    host["money"] -= 베팅금
    save_data(data)

    embed = discord.Embed(title="🎲 1v1 주사위 대결", description=f"**{interaction.user.display_name}**님이 **{베팅금:,}원** 대결을 열었습니다!", color=0x3498db)
    view = DiceDuelView(interaction.user, 베팅금)
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()

# 14) /가위바위보
@bot.tree.command(name="가위바위보", description="비공개 선택 방식의 1v1 가위바위보 심리전 대결을 엽니다.")
async def rps_game(interaction: discord.Interaction, 판돈: int):
    if 판돈 < 1000:
        await interaction.response.send_message("❌ 최소 판돈은 **1,000원** 이상입니다.", ephemeral=True)
        return

    data = load_data()
    host = get_user_data(data, interaction.user.id)

    if host["money"] < 판돈:
        await interaction.response.send_message(f"❌ 잔액이 부족합니다! ({판돈:,}원 필요)", ephemeral=True)
        return

    host["money"] -= 판돈
    save_data(data)

    embed = discord.Embed(title="⚔️ 1v1 가위바위보 대결", description=f"**{interaction.user.display_name}**님이 **{판돈:,}원** 대결을 열었습니다!", color=0xe67e22)
    view = RPSLobbyView(interaction.user, 판돈)
    await interaction.response.send_message(embed=embed, view=view)

# 15) /경마개장
@bot.tree.command(name="경마개장", description="서버 유저들과 함께 즐기는 2~4인 실시간 경마장을 개장합니다.")
async def open_horse_race(interaction: discord.Interaction, 판돈: int):
    if 판돈 < 1000:
        await interaction.response.send_message("❌ 최소 판돈은 **1,000원** 이상입니다.", ephemeral=True)
        return

    data = load_data()
    host = get_user_data(data, interaction.user.id)

    if host["money"] < 판돈:
        await interaction.response.send_message(f"❌ 잔액이 부족합니다! ({판돈:,}원 필요)", ephemeral=True)
        return

    host["money"] -= 판돈
    save_data(data)

    view = HorseRaceView(interaction.user, 판돈)
    await interaction.response.send_message(embed=view.build_embed(), view=view)

# 16) /파산신청
@bot.tree.command(name="파산신청", description="잔액이 마이너스(빚)일 때 하루 1회 채무 감면 룰렛을 진행합니다.")
async def bankruptcy_relief(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if u["money"] >= 0:
        await interaction.response.send_message("❌ 현금이 마이너스(빚) 상태일 때만 파산신청이 가능합니다!", ephemeral=True)
        return

    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")

    if u.get("last_bankrupt_date", "") == today_str:
        await interaction.response.send_message("❌ 파산신청은 하루에 한 번만 가능합니다.", ephemeral=True)
        return

    debt = abs(u["money"])
    rand = random.random() * 100

    if rand < 15:
        u["money"] = 0
        res_str = f"🎉 **[100% 전액 면제!!]** 빚 **{debt:,}원**을 전액 탕감받았습니다!"
        color = 0xf1c40f
    elif rand < 50:
        reduced = int(debt * 0.7)
        u["money"] = int(u["money"] * 0.3)
        res_str = f"✨ **[70% 대폭 감면!]** 빚 중 **{reduced:,}원**이 탕감되어 남은 빚은 **{abs(u['money']):,}원**입니다."
        color = 0x3498db
    else:
        reduced = int(debt * 0.5)
        u["money"] = int(u["money"] * 0.5)
        res_str = f"👍 **[50% 절반 감면!]** 빚 중 **{reduced:,}원**이 탕감되어 남은 빚은 **{abs(u['money']):,}원**입니다."
        color = 0x2ecc71

    u["last_bankrupt_date"] = today_str
    save_data(data)

    embed = discord.Embed(title="⚖️ 개인회생 파산신청 결과", description=res_str, color=color)
    await interaction.response.send_message(embed=embed)

# 17) /낚시 (레벨별 쿨타임 및 피로도 감쇄 적용)
@bot.tree.command(name="낚시", description="찌를 물에 던져 물고기나 보물상자를 낚습니다.")
async def fishing(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    fish_lvl = update_fish_level(u)
    cd = max(30, 60 - (fish_lvl * 3))

    now = datetime.now().timestamp()
    if now - u.get("last_fish_time", 0) < cd:
        remain = int(cd - (now - u.get("last_fish_time", 0)))
        await interaction.response.send_message(f"⏳ 낚싯대를 정비 중입니다! ({remain}초 후 다시 가능)", ephemeral=True)
        return

    rod_id = u.get("equipped_rod", 0)
    rod_info = ROD_DATA[rod_id]
    
    fatigue_reduction = 0
    if fish_lvl >= 7: fatigue_reduction = 3
    elif fish_lvl >= 4: fatigue_reduction = 2

    fatigue_cost = max(1, rod_info["fatigue"] - fatigue_reduction)

    if u["fatigue"] < fatigue_cost:
        await interaction.response.send_message(f"❌ 피로도가 부족합니다! ({fatigue_cost} 필요)", ephemeral=True)
        return

    u["fatigue"] -= fatigue_cost
    u["last_fish_time"] = now
    save_data(data)

    await interaction.response.send_message(f"🎣 **[{rod_info['name']}]**(으)로 찌를 멀리 던졌습니다... (피로도 -{fatigue_cost})")

    wait_sec = random.uniform(5.0, 12.0)
    await asyncio.sleep(wait_sec)

    target_time = datetime.now().timestamp()
    view = discord.ui.View(timeout=10)
    view.add_item(CatchFishButton(interaction.user.id, target_time))

    msg = await interaction.original_response()
    await msg.edit(content="💥 **입질이 왔다! 3초 안에 아래 버튼을 누르세요!!**", view=view)

# 18) /서킷던전 (신규 PVE 2줄 실시간 이동 레이스)
@bot.tree.command(name="서킷던전", description="차량 강화 등급으로 보스 레이서와 실시간 1v1 레이스를 펼칩니다.")
@app_commands.choices(층=[
    app_commands.Choice(name="1층: 동네 고가도로 (추천 1~5강)", value=1),
    app_commands.Choice(name="2층: 수도권 외곽순환 (추천 6~10강)", value=2),
    app_commands.Choice(name="3층: 태백 레이스웨이 (추천 11~15강)", value=3),
    app_commands.Choice(name="4층: 영암 F1 서킷 (추천 16~20강)", value=4),
    app_commands.Choice(name="5층: 뉘르부르크링 (추천 21~25강)", value=5),
    app_commands.Choice(name="6층: 아우토반 무제한 (추천 26~30강)", value=6)
])
async def circuit_dungeon(interaction: discord.Interaction, 층: int):
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")

    if u.get("dungeon_clear_date", "") != today_str:
        u["cleared_dungeon_today"] = []
        u["dungeon_clear_date"] = today_str

    if 층 in u.get("cleared_dungeon_today", []):
        await interaction.response.send_message(f"❌ **{층}층**은 오늘 이미 클리어하셨습니다! (매일 자정 초기화)", ephemeral=True)
        return

    if u["fatigue"] < 20:
        await interaction.response.send_message("❌ 서킷 던전에 입장하기 위한 피로도(20)가 부족합니다!", ephemeral=True)
        return

    u["fatigue"] -= 20
    save_data(data)

    d_info = DUNGEON_DATA[층]
    car_lvl = u["car_level"]
    car_name = get_car_name(car_lvl)

    embed = discord.Embed(
        title=f"🏎️ [서킷 던전] {d_info['name']} - 레이스 시작!",
        description=f"• **내 차량:** {car_name}\n• **보스:** {d_info['boss']}\n\n🏁 100m 결승선을 향해 출발합니다!",
        color=0x3498db
    )
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()

    p_dist, b_dist = 0, 0
    winner = None

    while not winner:
        await asyncio.sleep(1.2)

        p_speed = int(8 + (car_lvl * 1.8) + random.randint(-2, 4))
        b_speed = int(d_info["boss_speed"] + random.randint(-2, 4))

        p_dist = min(100, p_dist + p_speed)
        b_dist = min(100, b_dist + b_speed)

        p_filled = p_dist // 10
        p_bar = "─" * p_filled + "🏎️" + "─" * (10 - p_filled)

        b_filled = b_dist // 10
        b_bar = "─" * b_filled + "🚗" + "─" * (10 - b_filled)

        race_str = (
            f"🏎️ **{d_info['name']} 레이스 진행 중!**\n\n"
            f"`내  차` 🏁{p_bar} `[{p_dist}m]`\n"
            f"`보  스` 🏁{b_bar} `[{b_dist}m]`"
        )
        embed.description = race_str
        await msg.edit(embed=embed)

        if p_dist >= 100 or b_dist >= 100:
            if p_dist >= 100 and b_dist < 100:
                winner = "player"
            elif b_dist >= 100 and p_dist < 100:
                winner = "boss"
            else:
                winner = "player" if p_dist >= b_dist else "boss"

    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if winner == "player":
        u["money"] += d_info["gold"]
        rewards = [f"💰 +{d_info['gold']:,}원"]

        if d_info["stones"] > 0:
            u["inventory"]["강화석"] += d_info["stones"]
            rewards.append(f"✨ 강화석 {d_info['stones']}개")
        if d_info["protect"] > 0:
            u["inventory"]["파괴 방지권"] += d_info["protect"]
            rewards.append(f"🛡️ 파괴 방지권 {d_info['protect']}개")
        if d_info["degrade_protect"] > 0:
            u["inventory"]["하락 방지권"] += d_info["degrade_protect"]
            rewards.append(f"📉 하락 방지권 {d_info['degrade_protect']}개")

        if 층 not in u["cleared_dungeon_today"]:
            u["cleared_dungeon_today"].append(층)

        save_data(data)

        win_embed = discord.Embed(title=f"🏆 {층}층 보스 격파 성공!", color=0x2ecc71)
        win_embed.description = (
            f"🎉 보스 **[{d_info['boss']}]**를 제치고 가장 먼저 결승선을 통과했습니다!\n\n"
            f"🎁 **클리어 보상:**\n• " + "\n• ".join(rewards)
        )
        await msg.edit(embed=win_embed)
    else:
        save_data(data)
        lose_embed = discord.Embed(title=f"💥 {층}층 완패...", color=0xe74c3c)
        lose_embed.description = f"보스 **[{d_info['boss']}]**의 압도적인 출력에 밀렸습니다...\n차량을 더 강화한 후 재도전해보세요!"
        await msg.edit(embed=lose_embed)

# ---------------------------------------------------------
# 9. 실행부
# ---------------------------------------------------------
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN.strip().strip("'").strip('"'))
    else:
        print("❌ 디스코드 토큰 환경변수를 찾을 수 없습니다.")
