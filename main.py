import os
import json
import discord
from discord.ext import commands

# -------------------------------------------------------------
# 1. 디스코드 인텐트(Intents) 및 봇 설정
# -------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True  # 메시지 내용 읽기 권한
intents.members = True          # 서버 멤버 감지 권한

bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장용 파일 이름
DATA_FILE = "bot_data.json"


# -------------------------------------------------------------
# 2. JSON 데이터 불러오기 / 저장하기 함수
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# 3. 봇 이벤트 및 명령어
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# 4. 토큰 가져오기 및 예외 처리 (공백/따옴표 자동 제거)
# -------------------------------------------------------------
# 환경변수에서 'BOT_TOKEN' 또는 'DISCORD_TOKEN'을 먼저 찾습니다.
raw_token = os.environ.get("BOT_TOKEN") or os.environ.get("DISCORD_TOKEN") or ""

# 만약 환경변수가 비어있다면, 아래 따옴표 안의 직접 입력한 토큰을 사용합니다.
if not raw_token or raw_token.strip() == "":
    raw_token = "여기에_새로_발급받은_디스코드_봇_토큰_붙여넣기"

# 토큰 복사 시 들어갈 수 있는 앞뒤 공백, 줄바꿈, 따옴표를 정제합니다.
TOKEN = raw_token.strip().strip("'").strip('"')


# -------------------------------------------------------------
# 5. 봇 실행
# -------------------------------------------------------------
if __name__ == "__main__":
    if TOKEN and TOKEN != "여기에_새로_발급받은_디스코드_봇_토큰_붙여넣기":
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            print("\n❌ [로그인 실패] 토큰이 올바르지 않습니다!")
            print("1. Discord Developer Portal -> Bot -> 'Reset Token'으로 뽑은 진짜 토큰이 맞는지 확인해 주세요.")
            print("2. Application ID나 Client Secret을 토큰 자리에 넣으셨는지 확인해 주세요.\n")
        except Exception as e:
            print(f"\n❌ [시작 실패] 오류 원인: {e}\n")
    else:
        print("\n❌ [설정 오류] 토큰이 비어있거나 기본 문구가 그대로 남아있습니다!")
        print("디스호스트 [간편 설정]의 BOT_TOKEN 환경변수를 저장하거나, 코드 맨 밑에 토큰을 넣고 저장해 주세요.\n")
