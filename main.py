import os
import json
import discord
from discord.ext import commands

# 1. 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True  # 메시지 내용 읽기 권한

bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 파일 경로
DATA_FILE = "bot_data.json"

# 데이터 불러오기 함수
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# 데이터 저장하기 함수
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 봇 준비 완료 이벤트
@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user.name} (ID: {bot.user.id})")

# [명령어 예시 1] 돈 확인하기
@bot.command(name="돈")
async def money(ctx):
    data = load_data()
    user_id = str(ctx.author.id)
    balance = data.get(user_id, {}).get("money", 0)
    await ctx.send(f"💰 {ctx.author.mention}님의 현재 잔액: **{balance}원**")

# [명령어 예시 2] 출석체크 (돈 받기)
@bot.command(name="출석")
async def daily(ctx):
    data = load_data()
    user_id = str(ctx.author.id)
    
    if user_id not in data:
        data[user_id] = {"money": 0}
        
    data[user_id]["money"] += 1000
    save_data(data)
    
    await ctx.send(f"✅ {ctx.author.mention}님, 출석체크로 1,000원을 받으셨습니다! (현재: {data[user_id]['money']}원)")

# 2. 토큰 가져오기 (환경변수에서 토큰을 읽어옵니다)
# 깃허브 보안 시스템에 걸리지 않도록 하드코딩을 방지합니다.
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("DISCORD_TOKEN")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("오류: 디스호스트 설정(환경변수)에 BOT_TOKEN이 등록되지 않았습니다.")
