import os
import json
import random
import asyncio
from datetime import datetime, time
import discord
from discord import app_commands
from discord.ext import commands, tasks

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------
# 1. 디스코드 봇 설정
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "bot_data.json"

# ---------------------------------------------------------
# 2. 데이터 구조 및 파일 관리 (JSON)
# ---------------------------------------------------------
DEFAULT_MARKET = {
    "artifacts": {
        "똥먹방 비법서": 30000,
        "차은우지성 조각상": 50000,
        "170KG 비법서": 70000,
        "곤지암병원 지도": 100000,
        "L을 가져가 비법서": 150000
    },
    "stocks": {
        "170kg전자": 500000,
        "L을가져닉스": 500000,
        "엔비티키퐁크": 500000
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
            return data
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
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
            "inventory": {
                "똥먹방 비법서": 0, "차은우지성 조각상": 0, "170KG 비법서": 0,
                "곤지암병원 지도": 0, "L을 가져가 비법서": 0,
                "에너지드링크": 0, "핫식스 박스": 0, "유물 랜덤 상자": 0,
                "강화석": 0, "파괴 방지권": 0, "하락 방지권": 0
            },
            "stocks": {"170kg전자": 0, "L을가져닉스": 0, "엔비티키퐁크": 0},
            "weapon_level": 0
        }
    return data["users"][uid]

# ---------------------------------------------------------
# 3. 강화 무기 명칭 및 매핑 데이터
# ---------------------------------------------------------
WEAPON_NAMES = [
    "맨손", "녹슨 단검", "수련용 목검", "강철 숏소드", "기사의 장검", "용병의 사냥칼",
    "은빛 칼날검", "정제된 카타나", "서리한의 파편", "청동룡의 이빨", "혈풍의 대검",
    "화염 베기검", "뇌전의 칠지도", "용살자의 거검", "암흑가르는 월도", "심연의 창공검",
    "영혼을 거두는 낫", "천상의 성검", "파멸의 비도", "태양의 광휘검", "시공을 가르는 검",
    "신성한 디스코 지성검", "차원 붕괴의 마검", "멸망을 부르는 인검", "불멸의 아수라도",
    "창조주의 집행검", "우주 파괴자의 도검", "신들의 종말, 라그나로크",
    "진천패도", "흑천마도", "부러지지않는 신념", "강철검제 이현성"
]

def get_weapon_name(level):
    if level <= 0: return "맨손"
    if level >= 31: return "✨ 강철검제 이현성 [30(+1)강]"
    if level == 30: return f"🔥 {WEAPON_NAMES[30]} [30강]"
    return f"{WEAPON_NAMES[level]} [{level}강]"

# ---------------------------------------------------------
# 4. 스케줄러 (유물/주식 시세 및 자정 피로도 리셋)
# ---------------------------------------------------------
@tasks.loop(minutes=30)
async def update_artifact_prices():
    data = load_data()
    base_prices = {"똥먹방 비법서": (30000, 6000, 90000), "차은우지성 조각상": (50000, 10000, 150000),
                   "170KG 비법서": (70000, 14000, 210000), "곤지암병원 지도": (100000, 20000, 300000),
                   "L을 가져가 비법서": (150000, 30000, 450000)}
    for item, (base, min_p, max_p) in base_prices.items():
        curr = data["market"]["artifacts"].get(item, base)
        rate = random.uniform(-0.30, 0.30)
        new_price = int(curr * (1 + rate))
        data["market"]["artifacts"][item] = max(min_p, min(max_p, new_price))
    save_data(data)

@tasks.loop(hours=1)
async def update_stock_prices():
    data = load_data()
    for stock in data["market"]["stocks"].keys():
        curr = data["market"]["stocks"][stock]
        rate = random.uniform(-0.40, 0.60)
        new_price = int(curr * (1 + rate))
        data["market"]["stocks"][stock] = max(10000, new_price)
    save_data(data)

@tasks.loop(time=time(hour=15, minute=0)) # UTC 15시 = KST 00시 (자정)
async def daily_reset():
    data = load_data()
    for uid, user in data["users"].items():
        user["fatigue"] = 100
        user["drink_used_today"] = 0
        user["hot6_used_today"] = 0
    save_data(data)

# ---------------------------------------------------------
# 5. 봇 준비 이벤트 및 명령어 동기화
# ---------------------------------------------------------
@bot.event
async def on_ready():
    update_artifact_prices.start()
    update_stock_prices.start()
    daily_reset.start()
    try:
        synced = await bot.tree.sync()
        print(f"✅ 로그인 성공! {len(synced)}개의 슬래시 명령어가 동기화되었습니다.")
    except Exception as e:
        print(f"명령어 동기화 오류: {e}")

# ---------------------------------------------------------
# 6. 슬래시 명령어 구현
# ---------------------------------------------------------

# /내정보
@bot.tree.command(name="내정보", description="현재 재산, 피로도, 춤 레벨 및 무기 정보를 확인합니다.")
async def my_info(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    embed = discord.Embed(title=f"👤 {interaction.user.display_name}님의 정보Card", color=0x3498db)
    embed.add_field(name="💰 현금", value=f"{u['money']:,}원", inline=True)
    embed.add_field(name="⚡ 피로도", value=f"{u['fatigue']}/100", inline=True)
    embed.add_field(name="💃 춤 레벨", value=f"Lv.{u['dance_level']} (누적 {u['dance_count']}회)", inline=True)
    embed.add_field(name="⚔️ 장착 무기", value=get_weapon_name(u["weapon_level"]), inline=False)
    await interaction.response.send_message(embed=embed)

# /춤추기
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
    
    # 레벨업 체크
    reqs = [50, 150, 300, 500, 750]
    for i, req in enumerate(reqs):
        if u["dance_count"] >= req:
            u["dance_level"] = max(u["dance_level"], i + 1)

    rand = random.random() * 100
    msg, reward_str = "", ""
    embed_color = 0x2ecc71

    if rand < 25:
        u["money"] += 500
        msg = "소소하게 엉덩이를 털었다. 지나가던 초등학생이 짠했는지 동전을 던져주고 갔다."
        reward_str = "💰 +500원"
    elif rand < 60:
        u["money"] += 1000
        msg = "길거리에서 뻣뻣한 춤을 췄다. 행인이 구경값으로 돈을 내밀었다."
        reward_str = "💰 +1,000원"
    elif rand < 75:
        u["money"] += 3000
        msg = "현란한 팝핀을 선보였다! 지나가던 인플루언서가 감탄했다."
        reward_str = "💰 +3,000원"
        embed_color = 0x3498db
    elif rand < 85:
        u["money"] += 5000
        msg = "리듬에 몸을 맡기고 디스코 댄스를 폭발시켰다!"
        reward_str = "💰 +5,000원"
        embed_color = 0x3498db
    elif rand < 92:
        u["money"] += 10000
        msg = "★대폭발★ 길거리가 순식간에 클럽으로 변했다!"
        reward_str = "💰 +10,000원"
        embed_color = 0x9b59b6
    elif rand < 95:
        u["money"] += 50000
        msg = "중력을 무시하는 브레이크 댄스! 대기업 회장님이 관람료를 후하게 던졌다!"
        reward_str = "💰 +50,000원"
        embed_color = 0x9b59b6
    elif rand < 97:
        u["money"] += 100000
        msg = "✨[전설의 춤신춤왕]✨ 하늘에서 빛이 내리쬐며 디스코 볼이 돌아간다!"
        reward_str = "💰 +100,000원"
        embed_color = 0xf1c40f
    elif rand < 98:
        u["inventory"]["강화석"] += 1
        msg = "✨ 열정적인 춤 끝에 바닥에서 번쩍이는 강화석을 주웠다!"
        reward_str = "✨ 강화석 1개 획득"
        embed_color = 0xe67e22
    else:
        artifacts = ["똥먹방 비법서", "차은우지성 조각상", "170KG 비법서", "곤지암병원 지도", "L을 가져가 비법서"]
        art = random.choice(artifacts)
        u["inventory"][art] += 1
        msg = f"✨ 봉인되어 있던 고대의 유물 【 {art} 】을(를) 발굴했다!"
        reward_str = f"🏛️ {art} 1개 획득"
        embed_color = 0xf1c40f

    save_data(data)
    embed = discord.Embed(title="🕺 춤추기 결과", description=msg, color=embed_color)
    embed.add_field(name="보상", value=reward_str, inline=False)
    embed.set_footer(text=f"남은 피로도: {u['fatigue']}/100")
    await interaction.response.send_message(embed=embed)

# /도박
@bot.tree.command(name="도박", description="다양한 게임 스타일로 도박을 진행합니다.")
@app_commands.choices(종류=[
    app_commands.Choice(name="⛏️ 마인크래프트 (초안전형)", value="마크"),
    app_commands.Choice(name="⚔️ 리그 오브 레전드 (밸런스형)", value="롤"),
    app_commands.Choice(name="🔫 발로란트 (고위험형)", value="발로란트"),
    app_commands.Choice(name="🕺 권루트 (극단적 초고위험 200배)", value="권루트")
])
async def gamble(interaction: discord.Interaction, 종류: str, 베팅금: int):
    if 베팅금 <= 0:
        await interaction.response.send_message("❌ 1원 이상 베팅해주세요.", ephemeral=True)
        return

    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if u["money"] < 베팅금:
        await interaction.response.send_message("❌ 소지한 현금이 부족합니다.", ephemeral=True)
        return

    # 로딩 연출
    await interaction.response.defer()
    loading_embed = discord.Embed(title="🎰 도박 진행 중...", description="결과를 계산하고 있습니다.", color=0x95a5a6)
    
    if 종류 == "마크":
        loading_embed.description = "⛏️ 깊은 굴을 파고 들어가는 중..."
    elif 종류 == "롤":
        loading_embed.description = "⚔️ 픽창에 들어섰습니다..."
    elif 종류 == "발로란트":
        loading_embed.description = "🔫 에임 연습하는 중..."
    elif 종류 == "권루트":
        loading_embed.description = "💃 권루트 댄스를 시전하는 중..."

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
        elif rand < 10.0: mult, result_title, embed_color = 3, "🔹 기분에 따라서", 0x2ecc71
        elif rand < 30.0: mult, result_title, embed_color = 1.5, "🔹 라운드 앤 라운드", 0x2ecc71
        elif rand < 65.0: mult, result_title, embed_color = -1, "🔸 애를 가져가~", 0xe74c3c
        elif rand < 90.0: mult, result_title, embed_color = -3, "🔸 스탭 댄싱", 0xe74c3c
        else: mult, result_title, embed_color = -10, "💥 포탈 오류 (전재산 파산급)", 0x2c3e50

    change_amount = int(베팅금 * abs(mult)) if mult < 0 else int(베팅금 * mult)
    
    if mult >= 0:
        u["money"] += change_amount
        res_str = f"🎉 **+{change_amount:,}원** 이득!"
    else:
        u["money"] = max(0, u["money"] - change_amount)
        res_str = f"💥 **-{change_amount:,}원** 손실..."

    save_data(data)
    res_embed = discord.Embed(title=f"🎰 {종류} 도박 결과", description=f"결과: **{result_title}**", color=embed_color)
    res_embed.add_field(name="변동 금액", value=res_str, inline=False)
    res_embed.add_field(name="현재 잔액", value=f"{u['money']:,}원", inline=False)
    await msg.edit(embed=res_embed)

# /강화
@bot.tree.command(name="강화", description="무기를 강화합니다.")
async def upgrade(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    curr_lvl = u["weapon_level"]

    if curr_lvl >= 31:
        await interaction.response.send_message("✨ 이미 최고 등급인 [30(+1)강 강철검제 이현성]에 도달했습니다!", ephemeral=True)
        return

    if u["inventory"]["강화석"] < 1:
        await interaction.response.send_message("❌ 강화석이 부족합니다! (춤추기 드롭 또는 상점 구매)", ephemeral=True)
        return

    cost = (curr_lvl + 1) * 20000
    if u["money"] < cost:
        await interaction.response.send_message(f"❌ 강화 비용이 부족합니다. (필요 골드: {cost:,}원)", ephemeral=True)
        return

    u["inventory"]["강화석"] -= 1
    u["money"] -= cost

    # 확률 및 리스크 계산
    if curr_lvl < 5: success_rate, destroy_rate = 100 - (curr_lvl * 5), 0
    elif curr_lvl < 10: success_rate, destroy_rate = 70 - ((curr_lvl - 5) * 5), 0
    elif curr_lvl < 15: success_rate, destroy_rate = 40 - ((curr_lvl - 10) * 3), 0
    elif curr_lvl < 20: success_rate, destroy_rate = 20 - ((curr_lvl - 15) * 2), 0
    elif curr_lvl < 30: success_rate, destroy_rate = max(3, 8 - (curr_lvl - 20)), 15
    else: success_rate, destroy_rate = 3, 50 # 30 -> 31(30+1강) 히든

    rand = random.random() * 100
    if rand < success_rate:
        u["weapon_level"] += 1
        msg = f"🎉 강화 성공!! 무기가 **{get_weapon_name(u['weapon_level'])}**(으)로 강화되었습니다!"
        color = 0xf1c40f if u["weapon_level"] >= 28 else 0x2ecc71
    else:
        # 실패 리스크 처리
        if destroy_rate > 0 and (random.random() * 100 < destroy_rate):
            if u["inventory"]["파괴 방지권"] > 0:
                u["inventory"]["파괴 방지권"] -= 1
                msg = "💥 강화 실패! 그러나 **파괴 방지권**이 무기 파괴를 막아냈습니다."
                color = 0xe67e22
            else:
                u["weapon_level"] = 0
                msg = "💥 강화 실패... 무기가 파괴되어 맨손이 되었습니다..."
                color = 0x2c3e50
        else:
            if u["inventory"]["하락 방지권"] > 0:
                u["inventory"]["하락 방지권"] -= 1
                msg = "📉 강화 실패! **하락 방지권**이 등급 하락을 막았습니다."
                color = 0xe67e22
            else:
                u["weapon_level"] = max(0, u["weapon_level"] - 1)
                msg = f"📉 강화 실패... 무기 등급이 **{get_weapon_name(u['weapon_level'])}**(으)로 하락했습니다."
                color = 0xe74c3c

    save_data(data)
    embed = discord.Embed(title="⚔️ 무기 강화 시도 결과", description=msg, color=color)
    await interaction.response.send_message(embed=embed)

# /순위
@bot.tree.command(name="순위", description="부자 및 무기 강화 순위를 확인합니다.")
@app_commands.choices(종류=[
    app_commands.Choice(name="💰 부자 랭킹", value="부자"),
    app_commands.Choice(name="⚔️ 무기 랭킹", value="무기")
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
                    total += data["market"]["artifacts"][art] * count
            for st, count in u["stocks"].items():
                if st in data["market"]["stocks"]:
                    total += data["market"]["stocks"][st] * count
            rank_list.append((uid, total))
        
        rank_list.sort(key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="🏆 부자 랭킹 TOP 10", color=0xf1c40f)
        for i, (uid, val) in enumerate(rank_list[:10]):
            embed.add_field(name=f"{i+1}위", value=f"<@{uid}>: **{val:,}원**", inline=False)

    else:
        rank_list = [(uid, u["weapon_level"]) for uid, u in users.items()]
        rank_list.sort(key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="🏆 무기 강화 랭킹 TOP 10", color=0xe67e22)
        for i, (uid, lvl) in enumerate(rank_list[:10]):
            embed.add_field(name=f"{i+1}위", value=f"<@{uid}>: **{get_weapon_name(lvl)}**", inline=False)

    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 7. 봇 실행
# ---------------------------------------------------------
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN.strip().strip("'").strip('"'))
    else:
        print("❌ 토큰을 찾을 수 없습니다.")
