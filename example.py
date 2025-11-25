from openai import OpenAI

# 🔑 API KEY 직접 입력
API_KEY = ""
client = OpenAI(api_key=API_KEY)

def get_recycle_method(item):
    prompt = f"""
너는 한국의 분리수거 도우미야.
사용자가 말한 품목을 어떻게 분리수거해야 하는지 간단하고 정확하게 알려줘.

품목: {item}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output[0].content[0].text


# 🔥 여기서부터는 네가 직접 품목 입력 가능!
print("=== 분리수거 도우미 ===")
print("궁금한 품목을 입력하세요. (종료하려면 exit 입력)\n")

while True:
    item = input("품목 입력: ").strip()

    if item.lower() == "exit":
        print("프로그램을 종료합니다.")
        break

    if item == "":
        print("빈 값은 입력할 수 없습니다.")
        continue

    print("\n📦 분리수거 방법:\n")
    print(get_recycle_method(item))
    print("\n---------------------------------\n")