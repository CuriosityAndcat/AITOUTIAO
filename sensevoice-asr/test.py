from sensevoice_transcriber import transcribe
import time

audio = r"D:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav"

print("=" * 50)
print("  SenseVoice 转录测试")
print("=" * 50)

t0 = time.time()
text = transcribe(audio, language="zh")
elapsed = time.time() - t0

print(f"\n转录耗时: {elapsed:.1f}s")
print(f"文本长度: {len(text)} 字符")
print(f"\n前 200 字预览:\n{text[:200]}")

with open("output.txt", "w", encoding="utf-8") as f:
    f.write(text)
print("\n全文已保存到 output.txt")

