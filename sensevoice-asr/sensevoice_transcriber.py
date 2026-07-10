"""
SenseVoice 语音转录模块（调试版）
"""
import os
import sys
import traceback
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

_MODEL_DIR = Path(__file__).parent / "models" / "iic" / "SenseVoiceSmall"
os.environ["MODELSCOPE_CACHE"] = str(_MODEL_DIR.parent.parent)
os.environ["MODELSCOPE_DISABLE_REMOTE"] = "1"

_model = None
_current_device = None


def _get_model_dir(custom_dir=None):
    if custom_dir:
        p = Path(custom_dir)
        if (p / "model.pt").exists():
            return p
        raise FileNotFoundError(f"模型目录缺少 model.pt: {custom_dir}")
    if (_MODEL_DIR / "model.pt").exists():
        return _MODEL_DIR
    raise FileNotFoundError("模型未找到！请将模型放到 ./models/iic/SenseVoiceSmall/")


def transcribe(
    audio_path,
    language="zh",
    device="cpu",
    model_dir=None,
    use_itn=True,
    batch_size_s=60,
    enable_vad=False,
):
    global _model, _current_device

    print(f"[DEBUG] transcribe() 被调用, audio={audio_path}", flush=True)

    if not Path(audio_path).exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    model_path = _get_model_dir(model_dir)
    print(f"[DEBUG] 模型路径: {model_path}", flush=True)
    print(f"[DEBUG] model.pt 大小: {(_model_dir := model_path / 'model.pt').stat().st_size / 1024 / 1024:.0f} MB", flush=True)
    print(f"[DEBUG] config.yaml: {(model_path / 'config.yaml').exists()}", flush=True)

    if _model is None or _current_device != device:
        print("[DEBUG] 开始加载模型...", flush=True)

        # 不抑制任何日志，全量输出
        from funasr import AutoModel
        import time

        print(f"[DEBUG] funasr.AutoModel 导入成功", flush=True)
        print(f"[DEBUG] 调用 AutoModel(model={str(model_path)}, device={device})", flush=True)

        t0 = time.time()
        try:
            _model_new = AutoModel(
                model=str(model_path),
                device=device,
                disable_pbar=False,
                disable_update=True,
                disable_log=False,     # 全量日志
                log_level="INFO",       # INFO 级别
                check_latest=False,
            )
            print(f"[DEBUG] AutoModel() 返回成功, 耗时 {time.time() - t0:.1f}s", flush=True)
            _model = _model_new
            _current_device = device
            print("[SenseVoice] ✅ 模型加载完成", flush=True)
        except BaseException as e:
            print(f"[FATAL] AutoModel() 异常: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            sys.stdout.flush()
            raise

    print("[DEBUG] 开始转录...", flush=True)
    try:
        result = _model.generate(
            input=audio_path,
            language=language,
            ban_emo_unk=True,
            use_itn=use_itn,
            batch_size_s=batch_size_s,
        )
        print(f"[DEBUG] generate() 返回成功", flush=True)
    except BaseException as e:
        print(f"[FATAL] generate() 异常: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        raise

    if not result:
        print("[DEBUG] result 为空", flush=True)
        return ""

    text = result[0].get("text", "")
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)

    print(f"[DEBUG] 转录完成, {len(text)} 字符", flush=True)
    return text.strip()
