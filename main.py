import os
import json
import discord
from discord.ext import commands

# python-dotenv 라이브러리로 디스호스트의 .env 파일 강제 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 1. 디스코드 인텐트(Intents) 및 봇 설정
intents = discord.Intents.default()
intents.message_content = True  # 메시지 내용 읽기 권한
intents.members = True          # 서버 멤버 감지 권한

bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장용 파일 이름
DATA_FILE = "bot_data.json"


# 2. JSON 데이터 불러오기 / 저장하기 함수
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"데이터 파일 읽기 오류: {e}")
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"데이터 파일 저장 오류: {e}")


# 3. 봇 이벤트 및 명령어
@bot.event
async def on_ready():
    print("----------------------------------------")
    print(f"✅ 로그인 성공! 봇이 온에어 상태입니다.")
    print(f"봇 이름: {bot.user.name}")
    print(f"봇 ID: {bot.user.id}")
    print("----------------------------------------")

# [명령어] !돈 - 잔액 확인
@bot.command(name="돈")
async def check_money(ctx):
    data = load_data()
    user_id = str(ctx.author.id)
    balance = data.get(user_id, {}).get("money", 0)
    await ctx.send(f"💰 {ctx.author.mention}님의 현재 잔액: **{balance:,}원**")

# [명령어] !출석 - 돈 지급 (경제 기능)
@bot.command(name="출석")
async def daily_money(ctx):
    data = load_data()
    user_id = str(ctx.author.id)

    if user_id not in data:
        data[user_id] = {"money": 0}

    reward = 1000
    data[user_id]["money"] = data[user_id].get("money", 0) + reward
    save_data(data)

    await ctx.send(f"✅ {ctx.author.mention}님, 출석체크로 **{reward:,}원**을 받았습니다! (현재 잔액: {data[user_id]['money']:,}원)")


# 4. 환경변수 및 .env에서 토큰 가져오기
RAW_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN") or ""
TOKEN = RAW_TOKEN.strip().strip("'").strip('"')


# 5. 봇 실행
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("\n❌ 토큰을 찾을 수 없습니다. 디스호스트 [파일] 탭에 .env 파일을 생성해 주세요.\n")
