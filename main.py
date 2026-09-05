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

# ⚠️ [필수 수정] 본인의 깃허브 아이디와 저장소(Repository) 이름으로 입력해주세요!
GITHUB_USERNAME = "본인_깃허브_아이디"
GITHUB_REPO = "저장소_이름"
GITHUB_IMG_BASE = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/images"

def get_img_url(file_name):
    return f"{GITHUB_IMG_BASE}/{file_name}"

def get_fatigue_bar(fatigue, max_fatigue=100):
    filled = max(0, min(10, int(round((fatigue / max_fatigue) * 10))))
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {fatigue}/{max_fatigue}"

# ---------------------------------------------------------
# 2. 데이터베이스 구조 및 마이그레이션
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
    }
}

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

            for category in ["artifacts", "stocks"]:
                for k, v in data["market"][category].items():
                    if isinstance(v, int):
                        data["market"][category][k] = {"price": v, "prev_price": v}
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
            "dance_count": 0,
            "dance_level": 0,
            "drink_used_today": 0,
            "hot6_used_today": 0,
            "remittance_count_today": 0,
            "last_check_date": "",
            "attendance_streak": 0,
            "inventory": {
                "똥먹방 비법서": 0, "차은우지성 조각상": 0, "170KG 비법서": 0,
                "곤지암병원 지도": 0, "L을 가져가 비법서": 0,
                "에너지드링크": 0, "핫식스 박스": 0, "유물 랜덤 상자": 0,
                "강화석": 0, "파괴 방지권": 0, "하락 방지권": 0
            },
            "stocks": {"170kg전자": 0, "L을가져닉스": 0, "엔비티키퐁크": 0},
            "car_level": 0
        }
    else:
        u = data["users"][uid]
        u.setdefault("remittance_count_today", 0)
        u.setdefault("last_check_date", "")
        u.setdefault("attendance_streak", 0)
        # 구버전 weapon_level 호환 마이그레이션
        if "car_level" not in u:
            u["car_level"] = u.pop("weapon_level", 0)
    return data["users"][uid]

# ---------------------------------------------------------
# 3. 차(Car) 강화 명칭 트래커 (32단계)
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

def get_car_name(level):
    if level <= 0: return "뚜벅이 (맨발)"
    if level >= 31: return "✨ 부가티 라 부아튀르 누아르 [30(+1)강]"
    if level == 30: return f"🔥 {CAR_NAMES[30]} [30강]"
    return f"{CAR_NAMES[level]} [{level}강]"

# ---------------------------------------------------------
# 4. 정각 주기 스케줄러 (KST 기준)
# ---------------------------------------------------------
artifact_times = [time(hour=h, minute=m) for h in range(24) for m in (0, 30)]
@tasks.loop(time=artifact_times)
async def update_artifact_prices():
    data = load_data()
    base_prices = {
        "똥먹방 비법서": (30000, 6000, 90000),
        "차은우지성 조각상": (50000, 10000, 150000),
        "170KG 비법서": (70000, 14000, 210000),
        "곤지암병원 지도": (100000, 20000, 300000),
        "L을 가져가 비법서": (150000, 30000, 450000)
    }
    for item, (base, min_p, max_p) in base_prices.items():
        curr_data = data["market"]["artifacts"].get(item, {"price": base, "prev_price": base})
        curr_price = curr_data["price"] if isinstance(curr_data, dict) else curr_data
        
        rate = random.uniform(-0.30, 0.30)
        new_price = max(min_p, min(max_p, int(curr_price * (1 + rate))))
        
        data["market"]["artifacts"][item] = {
            "price": new_price,
            "prev_price": curr_price
        }
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
        
        data["market"]["stocks"][stock] = {
            "price": new_price,
            "prev_price": curr_price
        }
    save_data(data)

@tasks.loop(time=time(hour=15, minute=0)) # KST 00시 (UTC 15시)
async def daily_reset():
    data = load_data()
    for uid, user in data["users"].items():
        user["fatigue"] = 100
        user["drink_used_today"] = 0
        user["hot6_used_today"] = 0
        user["remittance_count_today"] = 0
    save_data(data)

# ---------------------------------------------------------
# 5. UI 컴포넌트 (/가방 드롭다운 UI & P2P 도박 UI)
# ---------------------------------------------------------

# 1) /가방 대화형 사용 UI
class BagSelect(discord.ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [
            discord.SelectOption(label="에너지드링크", description="피로도 +30 회복 (일일 3회)", emoji="🥤", value="에너지드링크"),
            discord.SelectOption(label="핫식스 박스", description="피로도 100 완충 (일일 1회)", emoji="⚡", value="핫식스 박스"),
            discord.SelectOption(label="유물 랜덤 상자", description="고대 유물 100% 획득", emoji="📦", value="유물 랜덤 상자")
        ]
        super().__init__(placeholder="사용할 아이템을 선택하세요...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인의 가방 메뉴만 조작할 수 있습니다.", ephemeral=True)
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
                await interaction.response.send_message("❌ 에너지드링크는 하루 최대 3회만 사용할 수 있습니다.", ephemeral=True)
                return
            u["inventory"][item] -= 1
            u["drink_used_today"] += 1
            u["fatigue"] = min(100, u["fatigue"] + 30)
            msg = f"🥤 에너지드링크를 사용했습니다! (피로도: {u['fatigue']}/100)"

        elif item == "핫식스 박스":
            if u["hot6_used_today"] >= 1:
                await interaction.response.send_message("❌ 핫식스 박스는 하루 최대 1회만 사용할 수 있습니다.", ephemeral=True)
                return
            u["inventory"][item] -= 1
            u["hot6_used_today"] += 1
            u["fatigue"] = 100
            msg = f"⚡ 핫식스를 마셨습니다! 피로도가 100으로 완충되었습니다!"

        elif item == "유물 랜덤 상자":
            u["inventory"][item] -= 1
            arts = ["똥먹방 비법서", "차은우지성 조각상", "170KG 비법서", "곤지암병원 지도", "L을 가져가 비법서"]
            got = random.choice(arts)
            u["inventory"][got] += 1
            msg = f"📦 유물 랜덤 상자에서 【 {got} 】을(를) 발굴했습니다!"

        save_data(data)

        # 가방 화면 실시간 갱신
        embed = build_bag_embed(interaction.user, u)
        await interaction.response.edit_message(embed=embed, view=self.view)
        await interaction.followup.send(msg, ephemeral=True)

class BagView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.add_item(BagSelect(user_id))

def build_bag_embed(user, u):
    embed = discord.Embed(title=f"🎒 {user.display_name}님의 가방 소지품", color=0x9b59b6)
    embed.set_thumbnail(url=user.display_avatar.url)

    artifacts = [f"• {k}: **{v}개**" for k, v in u["inventory"].items() if k in DEFAULT_MARKET["artifacts"] and v > 0]
    consumables = [f"• {k}: **{v}개**" for k, v in u["inventory"].items() if k in ["에너지드링크", "핫식스 박스", "유물 랜덤 상자"] and v > 0]
    materials = [f"• {k}: **{v}개**" for k, v in u["inventory"].items() if k in ["강화석", "파괴 방지권", "하락 방지권"] and v > 0]

    embed.add_field(name="🏛️ 보유 유물", value="\n".join(artifacts) if artifacts else "없음", inline=False)
    embed.add_field(name="🥤 소모성 아이템 (아래 메뉴로 사용)", value="\n".join(consumables) if consumables else "없음", inline=False)
    embed.add_field(name="🛡️ 강화 재료 (강화 시 자동 적용)", value="\n".join(materials) if materials else "없음", inline=False)
    return embed

# 2) /주사위대결 UI (1v1 오픈 난입)
class DiceDuelView(discord.ui.View):
    def __init__(self, host_user, bet_amount):
        super().__init__(timeout=180)
        self.host_user = host_user
        self.bet_amount = bet_amount

    @discord.ui.button(label="⚔️ 도전하기", style=discord.ButtonStyle.green)
    async def challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host_user.id:
            await interaction.response.send_message("❌ 자신이 연 대결에는 참여할 수 없습니다.", ephemeral=True)
            return

        data = load_data()
        challenger = get_user_data(data, interaction.user.id)

        if challenger["money"] < self.bet_amount:
            await interaction.response.send_message("❌ 베팅 금액에 필요한 현금이 부족합니다.", ephemeral=True)
            return

        challenger["money"] -= self.bet_amount

        # 주사위 굴리기 (1~100)
        host_roll = random.randint(1, 100)
        challenger_roll = random.randint(1, 100)

        host_data = get_user_data(data, self.host_user.id)
        total_pot = self.bet_amount * 2

        if host_roll > challenger_roll:
            host_data["money"] += total_pot
            result_str = f"🎉 **{self.host_user.mention}님 승리!!** (+{total_pot:,}원 독식)"
            color = 0x2ecc71
        elif challenger_roll > host_roll:
            challenger["money"] += total_pot
            result_str = f"🎉 **{interaction.user.mention}님 승리!!** (+{total_pot:,}원 독식)"
            color = 0x2ecc71
        else:
            host_data["money"] += self.bet_amount
            challenger["money"] += self.bet_amount
            result_str = "🤝 **무승부!** 베팅금이 환불되었습니다."
            color = 0x95a5a6

        save_data(data)

        for item in self.children: item.disabled = True
        embed = discord.Embed(title="🎲 1v1 주사위 대결 결과", color=color)
        embed.add_field(name=f"👑 {self.host_user.display_name}", value=f"🎲 주사위: **{host_roll}**", inline=True)
        embed.add_field(name=f"⚔️ {interaction.user.display_name}", value=f"🎲 주사위: **{challenger_roll}**", inline=True)
        embed.add_field(name="🏆 승부 결과", value=result_str, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ 대결 취소", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_user.id:
            await interaction.response.send_message("❌ 방장만 대결을 취소할 수 있습니다.", ephemeral=True)
            return

        data = load_data()
        u = get_user_data(data, self.host_user.id)
        u["money"] += self.bet_amount
        save_data(data)

        for item in self.children: item.disabled = True
        embed = discord.Embed(title="🎲 주사위 대결 취소됨", description="방장에 의해 대결이 취소되고 베팅금이 환불되었습니다.", color=0x7f8c8d)
        await interaction.response.edit_message(embed=embed, view=self)

# 3) /경마개장 UI (2~4인 가변 경마)
class HorseRaceView(discord.ui.View):
    def __init__(self, host_user, bet_amount):
        super().__init__(timeout=300)
        self.host_user = host_user
        self.bet_amount = bet_amount
        self.horses = {1: "지성호", 2: "떡상호", 3: "깡통호", 4: "폭주호"}
        self.participants = {1: host_user} # 1번마는 방장 고정
        self.started = False

    def build_embed(self):
        embed = discord.Embed(title="🏇 실시간 서버 경마 대회 대기실", description=f"베팅금: **{self.bet_amount:,}원** (2인 이상 출발 가능)", color=0xe67e22)
        for num, name in self.horses.items():
            user = self.participants.get(num)
            user_str = user.mention if user else "[ 비어있음 - 버튼을 눌러 탑승 ]"
            embed.add_field(name=f"{num}번마 {name}", value=user_str, inline=False)
        return embed

    async def add_participant(self, interaction: discord.Interaction, horse_num: int):
        if interaction.user.id in [u.id for u in self.participants.values()]:
            await interaction.response.send_message("❌ 이미 마권을 하나 구매하셨습니다.", ephemeral=True)
            return

        if horse_num in self.participants:
            await interaction.response.send_message("❌ 이미 다른 참가자가 선택한 말입니다.", ephemeral=True)
            return

        data = load_data()
        u = get_user_data(data, interaction.user.id)
        if u["money"] < self.bet_amount:
            await interaction.response.send_message("❌ 판돈 참가 현금이 부족합니다.", ephemeral=True)
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
            await interaction.response.send_message("❌ 방장만 경주를 시작할 수 있습니다.", ephemeral=True)
            return

        if len(self.participants) < 2:
            await interaction.response.send_message("❌ 최소 2명 이상 참여해야 경마를 시작할 수 있습니다!", ephemeral=True)
            return

        self.started = True
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(view=self)

        # 실시간 경마 레이스 연출
        distances = {num: 0 for num in self.participants.keys()}
        total_pot = len(self.participants) * self.bet_amount
        winner_num = None

        while not winner_num:
            await asyncio.sleep(1.5)
            race_str = ""
            for num, user in self.participants.items():
                distances[num] += random.randint(10, 25)
                dist = min(100, distances[num])
                filled = dist // 10
                bar = "🟩" * filled + "⬜" * (10 - filled)
                race_str += f"🏇 {num}번마 {self.horses[num]} ({user.display_name}): {bar} ({dist}m)\n"

                if dist >= 100 and not winner_num:
                    winner_num = num

            embed = discord.Embed(title="🏇 경마 레이스 진행 중!!", description=race_str, color=0xe67e22)
            await interaction.message.edit(embed=embed)

        # 우승자 지급
        winner_user = self.participants[winner_num]
        data = load_data()
        w_data = get_user_data(data, winner_user.id)
        w_data["money"] += total_pot
        save_data(data)

        win_embed = discord.Embed(title="🏆 경마 대회 종료!", color=0xf1c40f)
        win_embed.add_field(name="🥇 우승 말", value=f"**{winner_num}번마 {self.horses[winner_num]}** ({winner_user.mention})", inline=False)
        win_embed.add_field(name="💰 획득 상금", value=f"총 판돈 **+{total_pot:,}원** 독식!", inline=False)
        await interaction.message.edit(embed=win_embed)

    @discord.ui.button(label="❌ 개장 취소", style=discord.ButtonStyle.red, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_user.id:
            await interaction.response.send_message("❌ 방장만 개장을 취소할 수 있습니다.", ephemeral=True)
            return

        data = load_data()
        for user in self.participants.values():
            u = get_user_data(data, user.id)
            u["money"] += self.bet_amount
        save_data(data)

        for item in self.children: item.disabled = True
        embed = discord.Embed(title="🏇 경마 대회 취소됨", description="모든 참가자에게 베팅금이 환불되었습니다.", color=0x7f8c8d)
        await interaction.response.edit_message(embed=embed, view=self)

# ---------------------------------------------------------
# 6. 봇 동기화 이벤트
# ---------------------------------------------------------
@bot.event
async def on_ready():
    if not update_artifact_prices.is_running(): update_artifact_prices.start()
    if not update_stock_prices.is_running(): update_stock_prices.start()
    if not daily_reset.is_running(): daily_reset.start()
    try:
        synced = await bot.tree.sync()
        print(f"✅ 동기화 완료! 총 {len(synced)}개의 슬래시 명령어가 동작 중입니다.")
    except Exception as e:
        print(f"동기화 오류: {e}")

# ---------------------------------------------------------
# 7. 전체 슬래시 명령어
# ---------------------------------------------------------

# 1) /내정보 (카드형 세련된 프로필)
@bot.tree.command(name="내정보", description="내 재산, 피로도, 차 정보 및 통계를 확인합니다.")
async def my_info(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    
    # 총자산 계산 (현금 + 유물 + 주식)
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

    embed = discord.Embed(title=f"👤 {interaction.user.display_name}님의 프로필 카드", color=0x3498db)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    embed.add_field(name="💳 현금 잔액", value=f"**{u['money']:,}원**", inline=True)
    embed.add_field(name="🏛️ 추산 총자산", value=f"**{total_wealth:,}원**", inline=True)
    embed.add_field(name="⚡ 피로도 게이지", value=get_fatigue_bar(u['fatigue']), inline=False)
    embed.add_field(name="🚘 소유 차", value=f"**{get_car_name(u['car_level'])}**", inline=True)
    embed.add_field(name="💃 춤 숙련도", value=f"**Lv.{u['dance_level']}** ({u['dance_count']}회)", inline=True)
    embed.add_field(name="📅 연속 출석", value=f"**{u['attendance_streak']}일째**", inline=True)
    embed.set_footer(text="💡 소지품 확인 및 소모품 사용은 [/가방] 명령어를 이용하세요!")
    
    await interaction.response.send_message(embed=embed)

# 2) /가방 (대화형 UI 적용)
@bot.tree.command(name="가방", description="소지품을 확인하고 소모품을 바로 사용합니다.")
async def bag(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    embed = build_bag_embed(interaction.user, u)
    view = BagView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

# 3) /출석체크 (KST 자정 체크 정밀 반영)
@bot.tree.command(name="출석체크", description="매일 출석체크를 하여 연속 보상을 받습니다.")
async def attendance(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    yesterday_str = (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if u["last_check_date"] == today_str:
        await interaction.response.send_message("❌ 오늘은 이미 출석체크를 완료했습니다! (매일 밤 12시 초기화)", ephemeral=True)
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
    embed.add_field(name="연속 출석", value=f"**{streak}일째** 달성!", inline=False)
    embed.add_field(name="출석 보상", value=f"💰 **+{reward:,}원** 지급", inline=False)
    embed.add_field(name="현재 잔액", value=f"{u['money']:,}원", inline=False)
    await interaction.response.send_message(embed=embed)

# 4) /송금
@bot.tree.command(name="송금", description="서버 유저에게 돈을 보냅니다. (하루 3회, 한도 없음)")
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
        await interaction.response.send_message("❌ 오늘 일일 송금 횟수(3회)를 모두 소진하셨습니다.", ephemeral=True)
        return

    if sender["money"] < 금액:
        await interaction.response.send_message("❌ 소지한 현금이 부족합니다.", ephemeral=True)
        return

    sender["money"] -= 금액
    receiver["money"] += 금액
    sender["remittance_count_today"] += 1

    save_data(data)

    embed = discord.Embed(title="💸 송금 완료", color=0x3498db)
    embed.add_field(name="보낸 사람", value=interaction.user.mention, inline=True)
    embed.add_field(name="받은 사람", value=받으실분.mention, inline=True)
    embed.add_field(name="송금 금액", value=f"💰 **{금액:,}원**", inline=False)
    embed.set_footer(text=f"오늘 남은 송금 횟수: {3 - sender['remittance_count_today']}회")
    await interaction.response.send_message(embed=embed)

# 5) /춤추기 (큰 이미지 짤 매핑)
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
        await interaction.response.send_message(f"⏳ 지쳤습니다! {remain}초 후에 다시 춤출 수 있습니다.", ephemeral=True)
        return
    
    if u["fatigue"] < fatigue_cost:
        await interaction.response.send_message("❌ 피로도가 부족합니다! (자정 회복 또는 상점 음료 필요)", ephemeral=True)
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
        msg = "소소하게 엉덩이를 털었다. 지나가던 초등학생이 짠했는지 동전을 던져주고 갔다."
        reward_str, img_file = "💰 +500원", "춤_일반.png"
    elif rand < 60:
        u["money"] += 1000
        msg = "길거리에서 뻣뻣한 춤을 췄다. 행인이 구경값으로 돈을 내밀었다."
        reward_str, img_file = "💰 +1,000원", "춤_일반.png"
    elif rand < 75:
        u["money"] += 3000
        msg = "현란한 팝핀을 선보였다! 지나가던 인플루언서가 감탄했다."
        reward_str, embed_color, img_file = "💰 +3,000원", 0x3498db, "춤_레어.png"
    elif rand < 85:
        u["money"] += 5000
        msg = "리듬에 몸을 맡기고 디스코 댄스를 폭발시켰다!"
        reward_str, embed_color, img_file = "💰 +5,000원", 0x3498db, "춤_레어.png"
    elif rand < 92:
        u["money"] += 10000
        msg = "★대폭발★ 길거리가 순식간에 클럽으로 변했다!"
        reward_str, embed_color, img_file = "💰 +10,000원", 0x9b59b6, "춤_에픽.png"
    elif rand < 95:
        u["money"] += 50000
        msg = "중력을 무시하는 브레이크 댄스! 대기업 회장님이 관람료를 후하게 던졌다!"
        reward_str, embed_color, img_file = "💰 +50,000원", 0x9b59b6, "춤_에픽.png"
    elif rand < 97:
        u["money"] += 100000
        msg = "✨[전설의 춤신춤왕]✨ 하늘에서 빛이 내리쬐며 디스코 볼이 돌아간다!"
        reward_str, embed_color, img_file = "💰 +100,000원", 0xf1c40f, "춤_전설.png"
    elif rand < 98:
        u["inventory"]["강화석"] += 1
        msg = "✨ 열정적인 춤 끝에 바닥에서 번쩍이는 강화석을 주웠다!"
        reward_str, embed_color, img_file = "✨ 강화석 1개 획득", 0xe67e22, "춤_강화석.png"
    else:
        artifacts = ["똥먹방 비법서", "차은우지성 조각상", "170KG 비법서", "곤지암병원 지도", "L을 가져가 비법서"]
        art = random.choice(artifacts)
        u["inventory"][art] += 1
        msg = f"✨ 봉인되어 있던 고대의 유물 【 {art} 】을(를) 발굴했다!"
        reward_str, embed_color = f"🏛️ {art} 1개 획득", 0xf1c40f
        art_map = {
            "똥먹방 비법서": "유물_똥먹방비법서.png",
            "차은우지성 조각상": "유물_차은우지성조각상.png",
            "170KG 비법서": "유물_170KG비법서.png",
            "곤지암병원 지도": "유물_곤지암병원지도.png",
            "L을 가져가 비법서": "유물_L을가져가비법서.png"
        }
        img_file = art_map.get(art, "춤_일반.png")

    save_data(data)
    embed = discord.Embed(title="🕺 춤추기 완료", description=msg, color=embed_color)
    embed.set_image(url=get_img_url(img_file))
    embed.add_field(name="보상", value=reward_str, inline=False)
    embed.set_footer(text=f"남은 피로도: {u['fatigue']}/100")
    await interaction.response.send_message(embed=embed)

# 6) /유물시세 (가독성 개편)
@bot.tree.command(name="유물시세", description="30분 정각마다 변하는 유물 시세를 확인합니다.")
async def artifact_prices(interaction: discord.Interaction):
    data = load_data()
    market = data["market"]["artifacts"]
    now = datetime.now(KST)
    rem_min = 30 - (now.minute % 30)
    
    embed = discord.Embed(title="🏛️ 유물 실시간 시세표 (30분 주기 변동)", color=0xf1c40f)
    embed.set_thumbnail(url=get_img_url("유물시세.png"))
    
    lines = []
    for name, info in market.items():
        price = info["price"] if isinstance(info, dict) else info
        prev = info["prev_price"] if isinstance(info, dict) else price
        diff = price - prev
        rate = ((price - prev) / prev * 100) if prev > 0 else 0
        
        if diff > 0: status = f"▲ +{diff:,}원 (+{rate:.1f}%)"
        elif diff < 0: status = f"▼ -{abs(diff):,}원 ({rate:.1f}%)"
        else: status = "➖ 0원 (0.0%)"
        
        lines.append(f"• **{name}** | `{price:,}원` ({status})")
        
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"⏱️ 다음 시세 갱신까지: 약 {rem_min}분 남음")
    await interaction.response.send_message(embed=embed)

# 7) /유물판매
@bot.tree.command(name="유물판매", description="소지한 유물을 판매합니다.")
@app_commands.choices(유물명=[
    app_commands.Choice(name="똥먹방 비법서", value="똥먹방 비법서"),
    app_commands.Choice(name="차은우지성 조각상", value="차은우지성 조각상"),
    app_commands.Choice(name="170KG 비법서", value="170KG 비법서"),
    app_commands.Choice(name="곤지암병원 지도", value="곤지암병원 지도"),
    app_commands.Choice(name="L을 가져가 비법서", value="L을 가져가 비법서")
])
async def sell_artifact(interaction: discord.Interaction, 유물명: str, 개수: int):
    if 개수 <= 0:
        await interaction.response.send_message("❌ 1개 이상 입력해주세요.", ephemeral=True)
        return
    
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    if u["inventory"].get(유물명, 0) < 개수:
        await interaction.response.send_message(f"❌ 소지한 [{유물명}]이(가) 부족합니다.", ephemeral=True)
        return

    art_data = data["market"]["artifacts"][유물명]
    price = art_data["price"] if isinstance(art_data, dict) else art_data
    total = price * 개수
    u["inventory"][유물명] -= 개수
    u["money"] += total
    
    save_data(data)
    await interaction.response.send_message(f"✅ [{유물명}] {개수}개를 개당 {price:,}원 (총 {total:,}원)에 매각했습니다!")

# 8) /상점
@bot.tree.command(name="상점", description="피로도 회복제, 유물 상자 및 강화 재료를 구매합니다.")
@app_commands.choices(품목=[
    app_commands.Choice(name="🥤 에너지드링크 (+30 피로도) - 10,000원", value="에너지드링크"),
    app_commands.Choice(name="⚡ 핫식스 박스 (+100 피로도 완충) - 30,000원", value="핫식스 박스"),
    app_commands.Choice(name="📦 유물 랜덤 상자 - 80,000원", value="유물 랜덤 상자"),
    app_commands.Choice(name="✨ 강화석 팩 (10개) - 15,000원", value="강화석 팩"),
    app_commands.Choice(name="🛡️ 파괴 방지권 - 40,000원", value="파괴 방지권"),
    app_commands.Choice(name="📉 하락 방지권 - 20,000원", value="하락 방지권")
])
async def shop(interaction: discord.Interaction, 품목: str, 개수: int = 1):
    if 개수 <= 0:
        await interaction.response.send_message("❌ 1개 이상 구매해주세요.", ephemeral=True)
        return

    prices = {
        "에너지드링크": 10000, "핫식스 박스": 30000, "유물 랜덤 상자": 80000,
        "강화석 팩": 15000, "파괴 방지권": 40000, "하락 방지권": 20000
    }
    shop_img_map = {
        "에너지드링크": "상점_에너지드링크.png", "핫식스 박스": "상점_핫식스.png",
        "유물 랜덤 상자": "상점_유물상자.png", "강화석 팩": "상점_강화석.png",
        "파괴 방지권": "상점_파괴방지권.png", "하락 방지권": "상점_하락방지권.png"
    }

    cost = prices[품목] * 개수
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if u["money"] < cost:
        await interaction.response.send_message(f"❌ 소지 금액이 부족합니다. (필요 금액: {cost:,}원)", ephemeral=True)
        return

    u["money"] -= cost
    if 품목 == "강화석 팩": u["inventory"]["강화석"] += 10 * 개수
    else: u["inventory"][품목] += 개수

    save_data(data)
    embed = discord.Embed(title="🛒 상점 구매 완료", description=f"[{품목}] {개수}개를 총 {cost:,}원에 구매했습니다!", color=0x2ecc71)
    embed.set_thumbnail(url=get_img_url(shop_img_map.get(품목, "상점_강화석.png")))
    await interaction.response.send_message(embed=embed)

# 9) /도박 (수정된 파일명 매핑 및 썸네일 적용)
GAMBLE_IMG_MAP = {
    # 마크
    "엔더드래곤": "마크_엔더드래곤.png", "네더라이트": "마크_네더라이트.png", "다이아몬드": "마크_다이아.png",
    "철 발견": "마크_철.png", "평화로운 하루": "마크_평화.png", "크리퍼 폭발": "마크_크리퍼.png",
    "용암 사망": "마크_용암.png", "엄크": "마크_엄크.png",
    # 롤
    "챌린저": "롤_챌린저.png", "그랜드마스터": "롤_그랜드마스터.png", "마스터": "롤_마스터.png",
    "다이아몬드": "롤_다이아.png", "에메랄드": "롤_에메랄드.png", "플래티넘": "롤_플래티넘.png",
    "골드": "롤_골드.png", "실버": "롤_실버.png", "브론즈": "롤_브론즈.png", "아이언": "롤_아이언.png",
    # 발로란트
    "레디언트": "발로란트_레디언트.png", "불멸": "발로란트_불멸.png", "초월자": "발로란트_초월자.png",
    # 권루트
    "L을 가져가~": "권루트_L을가져가.png", "측면 대 측면": "권루트_측면대측면.png", "셀카": "권루트_셀카.png",
    "팁 토": "권루트_팁토.png", "기분에 따라": "권루트_기분에따라.png", "라운드 앤 라운드": "권루트_라운드앤라운드.png",
    "애를 가져가~": "권루트_애를가져가.png", "스텝 댄싱": "권루트_스텝댄싱.png", "포탈 오류": "권루트_포탈오류.png"
}

@bot.tree.command(name="도박", description="게임 컨셉의 도박을 진행합니다. (최소 1,000원 이상)")
@app_commands.choices(종류=[
    app_commands.Choice(name="⛏️ 마인크래프트 (초안전형)", value="마크"),
    app_commands.Choice(name="⚔️ 리그 오브 레전드 (밸런스형)", value="롤"),
    app_commands.Choice(name="🔫 발로란트 (고위험형)", value="발로란트"),
    app_commands.Choice(name="🕺 권루트 (극단적 초고위험 200배)", value="권루트")
])
async def gamble(interaction: discord.Interaction, 종류: str, 베팅금: int):
    if 베팅금 < 1000:
        await interaction.response.send_message("❌ 도박 최소 베팅 금액은 **1,000원** 이상입니다.", ephemeral=True)
        return

    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if u["money"] < 베팅금:
        await interaction.response.send_message("❌ 소지한 현금이 부족합니다.", ephemeral=True)
        return

    await interaction.response.defer()
    loading_embed = discord.Embed(title="🎰 도박 진행 중...", description="결과를 계산하고 있습니다.", color=0x95a5a6)
    loading_embed.set_thumbnail(url=get_img_url(f"도박_{종류}.png"))
    
    if 종류 == "마크": loading_embed.description = "⛏️ 깊은 굴을 파고 들어가는 중..."
    elif 종류 == "롤": loading_embed.description = "⚔️ 픽창에 들어섰습니다..."
    elif 종류 == "발로란트": loading_embed.description = "🔫 에임 연습하는 중..."
    elif 종류 == "권루트": loading_embed.description = "💃 권루트 댄스를 시전하는 중..."

    msg = await interaction.followup.send(embed=loading_embed)
    await asyncio.sleep(2)

    rand = random.random() * 100
    mult, result_title, embed_color = 0, "", 0x2ecc71

    if 종류 == "마크":
        if rand < 0.2: mult, result_title, embed_color = 30, "🔹 엔더드래곤", 0xf1c40f
        elif rand < 4.2: mult, result_title, embed_color = 5, "🔹 네더라이트", 0x9b59b6
        elif rand < 14.2: mult, result_title, embed_color = 2, "🔹 다이아몬드", 0x3498db
        elif rand < 43.0: mult, result_title, embed_color = 1, "🔹 철 발견", 0x2ecc71
        elif rand < 55.0: mult, result_title, embed_color = 0, "⬛ 평화로운 하루", 0x95a5a6
        elif rand < 84.0: mult, result_title, embed_color = -1, "🔸 크리퍼 폭발", 0xe74c3c
        elif rand < 95.0: mult, result_title, embed_color = -2, "🔸 용암 사망", 0xe74c3c
        else: mult, result_title, embed_color = -5, "🔸 정전 / 엄크", 0x2c3e50

    elif 종류 == "롤":
        if rand < 0.02: mult, result_title, embed_color = 100, "🔹 챌린저", 0xf1c40f
        elif rand < 0.06: mult, result_title, embed_color = 50, "🔹 그랜드마스터", 0xf1c40f
        elif rand < 0.40: mult, result_title, embed_color = 20, "🔹 마스터", 0x9b59b6
        elif rand < 3.00: mult, result_title, embed_color = 5, "🔹 다이아몬드", 0x3498db
        elif rand < 8.00: mult, result_title, embed_color = 3, "🔹 에메랄드", 0x2ecc71
        elif rand < 17.5: mult, result_title, embed_color = 2, "🔹 플래티넘", 0x2ecc71
        elif rand < 45.5: mult, result_title, embed_color = 1, "🔹 골드", 0x2ecc71
        elif rand < 75.5: mult, result_title, embed_color = -1, "🔸 실버", 0xe74c3c
        elif rand < 95.5: mult, result_title, embed_color = -2, "🔸 브론즈", 0xe74c3c
        else: mult, result_title, embed_color = -5, "🔸 아이언", 0x2c3e50

    elif 종류 == "발로란트":
        if rand < 0.02: mult, result_title, embed_color = 100, "🔹 레디언트", 0xf1c40f
        elif rand < 0.06: mult, result_title, embed_color = 50, "🔹 불멸", 0xf1c40f
        elif rand < 0.40: mult, result_title, embed_color = 20, "🔹 초월자", 0x9b59b6
        elif rand < 4.00: mult, result_title, embed_color = 5, "🔹 다이아몬드", 0x3498db
        elif rand < 13.5: mult, result_title, embed_color = 2, "🔹 플래티넘", 0x2ecc71
        elif rand < 45.5: mult, result_title, embed_color = 1, "🔹 골드", 0x2ecc71
        elif rand < 75.5: mult, result_title, embed_color = -1, "🔸 실버", 0xe74c3c
        elif rand < 95.5: mult, result_title, embed_color = -2, "🔸 브론즈", 0xe74c3c
        else: mult, result_title, embed_color = -5, "🔸 아이언", 0x2c3e50

    elif 종류 == "권루트":
        if rand < 0.01: mult, result_title, embed_color = 200, "🔹 L을 가져가~", 0xf1c40f
        elif rand < 0.04: mult, result_title, embed_color = 80, "🔹 측면 대 측면", 0xf1c40f
        elif rand < 0.30: mult, result_title, embed_color = 30, "🔹 셀카", 0x9b59b6
        elif rand < 3.00: mult, result_title, embed_color = 10, "🔹 팁 토", 0x3498db
        elif rand < 10.0: mult, result_title, embed_color = 3, "🔹 기분에 따라", 0x2ecc71
        elif rand < 30.0: mult, result_title, embed_color = 1.5, "🔹 라운드 앤 라운드", 0x2ecc71
        elif rand < 65.0: mult, result_title, embed_color = -1, "🔸 애를 가져가~", 0xe74c3c
        elif rand < 90.0: mult, result_title, embed_color = -3, "🔸 스텝 댄싱", 0xe74c3c
        else: mult, result_title, embed_color = -10, "💥 포탈 오류 (전재산 파산)", 0x2c3e50

    change_amount = int(베팅금 * abs(mult)) if mult < 0 else int(베팅금 * mult)
    
    if mult >= 0:
        u["money"] += change_amount
        res_str = f"🎉 **+{change_amount:,}원** 이득!"
    else:
        u["money"] = max(0, u["money"] - change_amount)
        res_str = f"💥 **-{change_amount:,}원** 손실..."

    save_data(data)
    res_embed = discord.Embed(title=f"🎰 {종류} 도박 결과", description=f"결과: **{result_title}**", color=embed_color)
    
    res_img = f"도박_{종류}.png"
    for k, v in GAMBLE_IMG_MAP.items():
        if k in result_title:
            res_img = v
            break
            
    res_embed.set_thumbnail(url=get_img_url(res_img))
    res_embed.add_field(name="변동 금액", value=res_str, inline=False)
    res_embed.add_field(name="현재 잔액", value=f"{u['money']:,}원", inline=False)
    await msg.edit(embed=res_embed)

# 10) /주식시세 (가독성 개편)
@bot.tree.command(name="주식시세", description="1시간 정각마다 변동하는 주식 시세를 확인합니다.")
async def stock_prices(interaction: discord.Interaction):
    data = load_data()
    stocks = data["market"]["stocks"]
    now = datetime.now(KST)
    rem_min = 60 - now.minute if now.minute > 0 else 60

    embed = discord.Embed(title="📈 주식 실시간 시세표 (1시간 주기 변동)", color=0x3498db)
    embed.set_thumbnail(url=get_img_url("주식시세.png"))
    
    lines = []
    for st, info in stocks.items():
        price = info["price"] if isinstance(info, dict) else info
        prev = info["prev_price"] if isinstance(info, dict) else price
        diff = price - prev
        rate = ((price - prev) / prev * 100) if prev > 0 else 0

        if diff > 0: status = f"▲ +{diff:,}원 (+{rate:.1f}%)"
        elif diff < 0: status = f"▼ -{abs(diff):,}원 ({rate:.1f}%)"
        else: status = "➖ 0원 (0.0%)"

        lines.append(f"• **{st}** | `{price:,}원` ({status})")

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"⏱️ 다음 시세 갱신까지: 약 {rem_min}분 남음")
    await interaction.response.send_message(embed=embed)

# 11) /주식매수
@bot.tree.command(name="주식매수", description="주식을 매수합니다.")
@app_commands.choices(종목=[
    app_commands.Choice(name="170kg전자", value="170kg전자"),
    app_commands.Choice(name="L을가져닉스", value="L을가져닉스"),
    app_commands.Choice(name="엔비티키퐁크", value="엔비티키퐁크")
])
async def buy_stock(interaction: discord.Interaction, 종목: str, 수량: int):
    if 수량 <= 0:
        await interaction.response.send_message("❌ 1주 이상 입력해주세요.", ephemeral=True)
        return

    data = load_data()
    u = get_user_data(data, interaction.user.id)
    st_data = data["market"]["stocks"][종목]
    price = st_data["price"] if isinstance(st_data, dict) else st_data
    cost = price * 수량

    if u["money"] < cost:
        await interaction.response.send_message(f"❌ 소지금이 부족합니다. (필요 금액: {cost:,}원)", ephemeral=True)
        return

    u["money"] -= cost
    u["stocks"][종목] += 수량
    save_data(data)
    await interaction.response.send_message(f"📈 [{종목}] {수량}주를 주당 {price:,}원 (총 {cost:,}원)에 매수했습니다!")

# 12) /주식매도
@bot.tree.command(name="주식매도", description="보유 주식을 매도하여 현금화합니다.")
@app_commands.choices(종목=[
    app_commands.Choice(name="170kg전자", value="170kg전자"),
    app_commands.Choice(name="L을가져닉스", value="L을가져닉스"),
    app_commands.Choice(name="엔비티키퐁크", value="엔비티키퐁크")
])
async def sell_stock(interaction: discord.Interaction, 종목: str, 수량: int):
    if 수량 <= 0:
        await interaction.response.send_message("❌ 1주 이상 입력해주세요.", ephemeral=True)
        return

    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if u["stocks"].get(종목, 0) < 수량:
        await interaction.response.send_message(f"❌ 소지한 [{종목}] 주식이 부족합니다.", ephemeral=True)
        return

    st_data = data["market"]["stocks"][종목]
    price = st_data["price"] if isinstance(st_data, dict) else st_data
    total = price * 수량

    u["stocks"][종목] -= 수량
    u["money"] += total
    save_data(data)
    await interaction.response.send_message(f"📉 [{종목}] {수량}주를 주당 {price:,}원 (총 {total:,}원)에 매도했습니다!")

# 13) /강화 (차 강화 시스템)
@bot.tree.command(name="강화", description="차를 강화합니다. (최대 30(+1)강 부가티 라 부아튀르 누아르)")
async def upgrade(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    curr_lvl = u["car_level"]

    if curr_lvl >= 31:
        await interaction.response.send_message("✨ 이미 최상위 등급인 [30(+1)강 부가티 라 부아튀르 누아르]를 소유 중입니다!", ephemeral=True)
        return

    if u["inventory"]["강화석"] < 1:
        await interaction.response.send_message("❌ 강화석이 부족합니다! (춤추기 드롭 또는 상점 구매)", ephemeral=True)
        return

    cost = (curr_lvl + 1) * 20000
    if u["money"] < cost:
        await interaction.response.send_message(f"❌ 강화 골드가 부족합니다. (필요 금액: {cost:,}원)", ephemeral=True)
        return

    u["inventory"]["강화석"] -= 1
    u["money"] -= cost

    if curr_lvl < 5: success_rate, destroy_rate = 100 - (curr_lvl * 5), 0
    elif curr_lvl < 10: success_rate, destroy_rate = 70 - ((curr_lvl - 5) * 5), 0
    elif curr_lvl < 15: success_rate, destroy_rate = 40 - ((curr_lvl - 10) * 3), 0
    elif curr_lvl < 20: success_rate, destroy_rate = 20 - ((curr_lvl - 15) * 2), 0
    elif curr_lvl < 30: success_rate, destroy_rate = max(3, 8 - (curr_lvl - 20)), 15
    else: success_rate, destroy_rate = 3, 50

    rand = random.random() * 100

    if rand < success_rate:
        u["car_level"] += 1
        msg = f"🎉 차 강화 성공!! 소유 차가 **{get_car_name(u['car_level'])}**(으)로 업그레이드되었습니다!"
        color = 0xf1c40f if u["car_level"] >= 28 else 0x2ecc71
    else:
        if destroy_rate > 0 and (random.random() * 100 < destroy_rate):
            if u["inventory"]["파괴 방지권"] > 0:
                u["inventory"]["파괴 방지권"] -= 1
                msg = "💥 강화 실패! **파괴 방지권**이 차 침수/폐차를 막아냈습니다."
                color = 0xe67e22
            else:
                u["car_level"] = 0
                msg = "💥 강화 실패... 차가 대파되어 결국 맨발(뚜벅이) 신세가 되었습니다..."
                color = 0x2c3e50
        else:
            if u["inventory"]["하락 방지권"] > 0:
                u["inventory"]["하락 방지권"] -= 1
                msg = "📉 강화 실패! **하락 방지권**이 차량 등급 하락을 방지했습니다."
                color = 0xe67e22
            else:
                u["car_level"] = max(0, u["car_level"] - 1)
                msg = f"📉 강화 실패... 소유 차 등급이 **{get_car_name(u['car_level'])}**(으)로 강등되었습니다."
                color = 0xe74c3c

    save_data(data)
    embed = discord.Embed(title="🚘 자동차 강화 결과", description=msg, color=color)
    await interaction.response.send_message(embed=embed)

# 14) /순위
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

# 15) /주사위대결 (P2P 오픈 매칭)
@bot.tree.command(name="주사위대결", description="다른 유저와 돈을 걸고 1v1 주사위 대결을 신청합니다.")
async def dice_duel(interaction: discord.Interaction, 베팅금: int):
    if 베팅금 < 1000:
        await interaction.response.send_message("❌ 최소 베팅 금액은 **1,000원** 이상입니다.", ephemeral=True)
        return

    data = load_data()
    host = get_user_data(data, interaction.user.id)

    if host["money"] < 베팅금:
        await interaction.response.send_message("❌ 소지한 현금이 부족합니다.", ephemeral=True)
        return

    host["money"] -= 베팅금
    save_data(data)

    embed = discord.Embed(title="🎲 1v1 주사위 대결 대기 중", description=f"**{interaction.user.display_name}**님이 **{베팅금:,}원** 주사위 대결을 열었습니다!\n지나가던 누구나 아래 버튼을 눌러 난입하세요!", color=0x3498db)
    view = DiceDuelView(interaction.user, 베팅금)
    await interaction.response.send_message(embed=embed, view=view)

# 16) /경마개장 (2~4인 가변 P2P 경마)
@bot.tree.command(name="경마개장", description="서버 유저들과 함께 즐기는 2~4인 실시간 경마장을 개장합니다.")
async def open_horse_race(interaction: discord.Interaction, 판돈: int):
    if 판돈 < 1000:
        await interaction.response.send_message("❌ 최소 판돈은 **1,000원** 이상입니다.", ephemeral=True)
        return

    data = load_data()
    host = get_user_data(data, interaction.user.id)

    if host["money"] < 판돈:
        await interaction.response.send_message("❌ 판돈 개장에 필요한 현금이 부족합니다.", ephemeral=True)
        return

    host["money"] -= 판돈
    save_data(data)

    view = HorseRaceView(interaction.user, 판돈)
    await interaction.response.send_message(embed=view.build_embed(), view=view)

# ---------------------------------------------------------
# 8. 실행부
# ---------------------------------------------------------
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN.strip().strip("'").strip('"'))
    else:
        print("❌ 디스코드 토큰 환경변수를 찾을 수 없습니다.")
