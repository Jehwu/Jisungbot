import os
import json
import random
import asyncio
from datetime import datetime, time, timedelta
import discord
from discord import app_commands
from discord.ext import commands, tasks

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------
# 1. 봇 기본 설정
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "bot_data.json"

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

            # 구버전 데이터(int 형태) 자동 호환 마이그레이션
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
            "weapon_level": 0
        }
    else:
        # 하위 호환성 필드 보장
        u = data["users"][uid]
        u.setdefault("remittance_count_today", 0)
        u.setdefault("last_check_date", "")
        u.setdefault("attendance_streak", 0)
    return data["users"][uid]

# ---------------------------------------------------------
# 3. 강화 무기 명칭 트래커
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
# 4. 정각 주기 스케줄러 (30분/1시간 정각 딱 맞춰 실행)
# ---------------------------------------------------------
# 매시 :00, :30분에 유물 시세 변동
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

# 매시 :00 정각에 주식 시세 변동
stock_times = [time(hour=h, minute=0) for h in range(24)]
@tasks.loop(time=stock_times)
async def update_stock_prices():
    data = load_data()
    for stock in data["market"]["stocks"].keys():
        curr_data = data["market"]["stocks"][stock]
        curr_price = curr_data["price"] if isinstance(curr_data, dict) else curr_data
        
        # -35% ~ +35% 균등 등락 (우상향 버그 수정)
        rate = random.uniform(-0.35, 0.35)
        new_price = max(10000, int(curr_price * (1 + rate)))
        
        data["market"]["stocks"][stock] = {
            "price": new_price,
            "prev_price": curr_price
        }
    save_data(data)

# 매일 KST 자정(UTC 15시) 피로도 및 송금 횟수 완충
@tasks.loop(time=time(hour=15, minute=0))
async def daily_reset():
    data = load_data()
    for uid, user in data["users"].items():
        user["fatigue"] = 100
        user["drink_used_today"] = 0
        user["hot6_used_today"] = 0
        user["remittance_count_today"] = 0
    save_data(data)

# ---------------------------------------------------------
# 5. 봇 동기화 이벤트
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
# 6. 전체 슬래시 명령어
# ---------------------------------------------------------

# 1) /내정보
@bot.tree.command(name="내정보", description="내 재산, 피로도, 춤 레벨, 보유 가방을 확인합니다.")
async def my_info(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    embed = discord.Embed(title=f"👤 {interaction.user.display_name}님의 프로필", color=0x3498db)
    embed.add_field(name="💰 현금", value=f"{u['money']:,}원", inline=True)
    embed.add_field(name="⚡ 피로도", value=f"{u['fatigue']}/100", inline=True)
    embed.add_field(name="💃 춤 숙련도", value=f"Lv.{u['dance_level']} ({u['dance_count']}회)", inline=True)
    embed.add_field(name="📅 연속 출석", value=f"{u['attendance_streak']}일째", inline=True)
    embed.add_field(name="💸 오늘 송금", value=f"{u['remittance_count_today']}/3회 사용", inline=True)
    embed.add_field(name="⚔️ 장착 무기", value=get_weapon_name(u["weapon_level"]), inline=False)
    
    inv_str = [f"{k}: {v}개" for k, v in u["inventory"].items() if v > 0]
    embed.add_field(name="🎒 보유 가방", value="\n".join(inv_str) if inv_str else "비어 있음", inline=False)
    await interaction.response.send_message(embed=embed)

# 2) /출석체크
@bot.tree.command(name="출석체크", description="매일 출석체크를 하여 연속 보상을 받습니다.")
async def attendance(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if u["last_check_date"] == today_str:
        await interaction.response.send_message("❌ 오늘은 이미 출석체크를 완료했습니다! 내일 다시 시도해주세요.", ephemeral=True)
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
    embed.add_field(name="연속 출석", value=f"**{streak}일째** 달성!", inline=False)
    embed.add_field(name="출석 보상", value=f"💰 **+{reward:,}원** 지급", inline=False)
    embed.add_field(name="현재 잔액", value=f"{u['money']:,}원", inline=False)
    await interaction.response.send_message(embed=embed)

# 3) /송금
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

# 4) /춤추기
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
    msg, reward_str, embed_color = "", "", 0x2ecc71

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
    embed = discord.Embed(title="🕺 춤추기 완료", description=msg, color=embed_color)
    embed.add_field(name="보상", value=reward_str, inline=False)
    embed.set_footer(text=f"남은 피로도: {u['fatigue']}/100")
    await interaction.response.send_message(embed=embed)

# 5) /유물시세 (변동 화살표 및 남은 시간 포함)
@bot.tree.command(name="유물시세", description="30분 정각마다 변하는 유물 시세를 확인합니다.")
async def artifact_prices(interaction: discord.Interaction):
    data = load_data()
    market = data["market"]["artifacts"]
    
    now = datetime.now()
    rem_min = 30 - (now.minute % 30)
    
    embed = discord.Embed(title="🏛️ 유물 실시간 시세표 (30분 주기 정각 변동)", color=0xf1c40f)
    for name, info in market.items():
        price = info["price"] if isinstance(info, dict) else info
        prev = info["prev_price"] if isinstance(info, dict) else price
        
        diff = price - prev
        rate = ((price - prev) / prev * 100) if prev > 0 else 0
        
        if diff > 0: status = f"▲ +{diff:,}원 (+{rate:.1f}%)"
        elif diff < 0: status = f"▼ -{abs(diff):,}원 ({rate:.1f}%)"
        else: status = "➖ 변동 없음 (0.0%)"
        
        embed.add_field(name=name, value=f"**{price:,}원** ({status})", inline=False)
        
    embed.set_footer(text=f"⏱️ 다음 시세 갱신까지: 약 {rem_min}분 남음")
    await interaction.response.send_message(embed=embed)

# 6) /유물판매
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

# 7) /상점
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
    await interaction.response.send_message(f"🛒 [{품목}] {개수}개를 총 {cost:,}원에 구매했습니다!")

# 8) /사용
@bot.tree.command(name="사용", description="가방 소모품을 사용합니다.")
@app_commands.choices(아이템=[
    app_commands.Choice(name="🥤 에너지드링크 (피로도 +30 / 일 3회)", value="에너지드링크"),
    app_commands.Choice(name="⚡ 핫식스 박스 (피로도 +100 / 일 1회)", value="핫식스 박스"),
    app_commands.Choice(name="📦 유물 랜덤 상자 (유물 100% 뽑기)", value="유물 랜덤 상자")
])
async def use_item(interaction: discord.Interaction, 아이템: str):
    data = load_data()
    u = get_user_data(data, interaction.user.id)

    if u["inventory"].get(아이템, 0) <= 0:
        await interaction.response.send_message(f"❌ 가방에 [{아이템}]이(가) 없습니다.", ephemeral=True)
        return

    if 아이템 == "에너지드링크":
        if u["drink_used_today"] >= 3:
            await interaction.response.send_message("❌ 에너지드링크는 하루 최대 3회만 사용할 수 있습니다.", ephemeral=True)
            return
        u["inventory"][아이템] -= 1
        u["drink_used_today"] += 1
        u["fatigue"] = min(100, u["fatigue"] + 30)
        msg = f"🥤 에너지드링크를 마셨습니다! 피로도 +30 회복 (현재: {u['fatigue']}/100)"

    elif 아이템 == "핫식스 박스":
        if u["hot6_used_today"] >= 1:
            await interaction.response.send_message("❌ 핫식스 박스는 하루 최대 1회만 사용할 수 있습니다.", ephemeral=True)
            return
        u["inventory"][아이템] -= 1
        u["hot6_used_today"] += 1
        u["fatigue"] = 100
        msg = f"⚡ 핫식스를 마셨습니다! 피로도가 100으로 완충되었습니다!"

    elif 아이템 == "유물 랜덤 상자":
        u["inventory"][아이템] -= 1
        arts = ["똥먹방 비법서", "차은우지성 조각상", "170KG 비법서", "곤지암병원 지도", "L을 가져가 비법서"]
        got = random.choice(arts)
        u["inventory"][got] += 1
        msg = f"📦 유물 랜덤 상자에서 【 {got} 】을(를) 획득했습니다!"

    save_data(data)
    await interaction.response.send_message(msg)

# 9) /도박
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
        elif rand < 10.0: mult, result_title, embed_color = 3, "🔹 기분에 따라서", 0x2ecc71
        elif rand < 30.0: mult, result_title, embed_color = 1.5, "🔹 라운드 앤 라운드", 0x2ecc71
        elif rand < 65.0: mult, result_title, embed_color = -1, "🔸 애를 가져가~", 0xe74c3c
        elif rand < 90.0: mult, result_title, embed_color = -3, "🔸 스탭 댄싱", 0xe74c3c
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
    res_embed.add_field(name="변동 금액", value=res_str, inline=False)
    res_embed.add_field(name="현재 잔액", value=f"{u['money']:,}원", inline=False)
    await msg.edit(embed=res_embed)

# 10) /주식시세 (변동 화살표 및 남은 시간 포함)
@bot.tree.command(name="주식시세", description="1시간 정각마다 변동하는 주식 시세를 확인합니다.")
async def stock_prices(interaction: discord.Interaction):
    data = load_data()
    stocks = data["market"]["stocks"]
    
    now = datetime.now()
    rem_min = 60 - now.minute if now.minute > 0 else 60

    embed = discord.Embed(title="📈 주식 실시간 시세표 (1시간 주기 정각 변동)", color=0x3498db)
    for st, info in stocks.items():
        price = info["price"] if isinstance(info, dict) else info
        prev = info["prev_price"] if isinstance(info, dict) else price

        diff = price - prev
        rate = ((price - prev) / prev * 100) if prev > 0 else 0

        if diff > 0: status = f"▲ +{diff:,}원 (+{rate:.1f}%)"
        elif diff < 0: status = f"▼ -{abs(diff):,}원 ({rate:.1f}%)"
        else: status = "➖ 변동 없음 (0.0%)"

        embed.add_field(name=st, value=f"**{price:,}원** ({status})", inline=False)

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

# 13) /강화
@bot.tree.command(name="강화", description="무기를 강화합니다. (최대 30(+1)강)")
async def upgrade(interaction: discord.Interaction):
    data = load_data()
    u = get_user_data(data, interaction.user.id)
    curr_lvl = u["weapon_level"]

    if curr_lvl >= 31:
        await interaction.response.send_message("✨ 이미 최상위 등급인 [30(+1)강 강철검제 이현성]을 장착 중입니다!", ephemeral=True)
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
        u["weapon_level"] += 1
        msg = f"🎉 강화 성공!! 무기가 **{get_weapon_name(u['weapon_level'])}**(으)로 승급되었습니다!"
        color = 0xf1c40f if u["weapon_level"] >= 28 else 0x2ecc71
    else:
        if destroy_rate > 0 and (random.random() * 100 < destroy_rate):
            if u["inventory"]["파괴 방지권"] > 0:
                u["inventory"]["파괴 방지권"] -= 1
                msg = "💥 강화 실패! **파괴 방지권**이 무기 파괴를 막아냈습니다."
                color = 0xe67e22
            else:
                u["weapon_level"] = 0
                msg = "💥 강화 실패... 무기가 순식간에 파괴되어 맨손으로 돌아갔습니다..."
                color = 0x2c3e50
        else:
            if u["inventory"]["하락 방지권"] > 0:
                u["inventory"]["하락 방지권"] -= 1
                msg = "📉 강화 실패! **하락 방지권**이 등급 하락을 방지했습니다."
                color = 0xe67e22
            else:
                u["weapon_level"] = max(0, u["weapon_level"] - 1)
                msg = f"📉 강화 실패... 무기 등급이 **{get_weapon_name(u['weapon_level'])}**(으)로 강등되었습니다."
                color = 0xe74c3c

    save_data(data)
    embed = discord.Embed(title="⚔️ 무기 강화 결과", description=msg, color=color)
    await interaction.response.send_message(embed=embed)

# 14) /순위
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
        rank_list = [(uid, u["weapon_level"]) for uid, u in users.items()]
        rank_list.sort(key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="🏆 최강 무기 랭킹 TOP 10", color=0xe67e22)
        for i, (uid, lvl) in enumerate(rank_list[:10]):
            embed.add_field(name=f"{i+1}위", value=f"<@{uid}>: **{get_weapon_name(lvl)}**", inline=False)

    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 7. 실행부
# ---------------------------------------------------------
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN.strip().strip("'").strip('"'))
    else:
        print("❌ 디스코드 토큰 환경변수를 찾을 수 없습니다.")
