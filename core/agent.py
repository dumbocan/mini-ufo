import os, sys, time, pathlib
from datetime import datetime
from tomlkit import parse
from core.graphics_guard import ensure_headless

import os
PROJ_DIR=os.getenv("MINIUFO_PROJECT_DIR")
LOGS_DIR=(pathlib.Path(PROJ_DIR)/"logs" if PROJ_DIR else pathlib.Path.home()/ "mini-ufo"/"logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

def log(msg):
    s=f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(s, flush=True)
    try:
        with open(LOG_FILE,"a",encoding="utf-8") as f: f.write(s+"\n")
    except Exception:
        pass

def load_config():
    cfg_path = pathlib.Path.home()/ "mini-ufo"/"core"/"config.toml"
    data = parse(cfg_path.read_text(encoding="utf-8"))
    return data

def apply_env_for_backend(backend, base_url, model):
    # Proveer variables OPENAI_* para compatibilidad OpenAI-like
    os.environ["OPENAI_BASE_URL"] = base_url
    os.environ["OPENAI_API_BASE"] = base_url
    # Reutilizar DEEPSEEK_API_KEY si está, como OPENAI_API_KEY (útil para clientes genéricos)
    if os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
    log(f"ENV set: OPENAI_BASE_URL={base_url} model={model} backend={backend}")

def configure_interpreter(backend, base_url, model):
    from interpreter import interpreter  # open-interpreter 0.4.3
    # Mensajes + modo sin aprobación interactiva
    if hasattr(interpreter, "auto_run"): interpreter.auto_run = True
    if hasattr(interpreter, "auto_approve"): interpreter.auto_approve = True
    if hasattr(interpreter, "approve"): interpreter.approve = True
    if hasattr(interpreter, "require_approval"): interpreter.require_approval = False

    # Fijar modelo/base de forma agresiva (evitar defaults gpt-*)
    try:
        interpreter.model = model
    except Exception: pass
    try:
        interpreter.api_base = base_url
    except Exception: pass
    try:
        # Algunos builds exponen interpreter.llm con provider/params
        if hasattr(interpreter, "llm"):
            try: interpreter.llm.provider = ("deepseek" if backend=="deepseek" else "ollama")
            except Exception: pass
            try:
                p = getattr(interpreter.llm, "params", {}) or {}
                p["model"] = model
                p["api_base"] = base_url
                interpreter.llm.params = p
            except Exception: pass
    except Exception:
        pass

    # Mensaje de sistema único
    interpreter.system_message = (
        "Eres un agente que: (1) crea/edita código, (2) ejecuta, "
        "(3) lee errores, (4) autocorrige y (5) reintenta hasta que funcione. "
        "Nunca uses modelos gpt-* ni cambies de backend sin orden. "
        "Guarda gráficos en ./outputs, logs en ./logs. Sé conciso en consola."
    )
    return interpreter

def main():
    ensure_headless()
    cfg = load_config()
    backend = str(cfg["llm"]["backend"])
    model   = str(cfg["llm"]["model"])
    if backend == "deepseek":
        base_url = str(cfg["deepseek"]["base_url"])
    else:
        base_url = str(cfg["ollama"]["base_url"])

    apply_env_for_backend(backend, base_url, model)

    # Soportar --dry-run para diagnóstico sin llamar al LLM
    if "--dry-run" in sys.argv:
        log(f"[DRY-RUN] backend={backend} model={model} base_url={base_url}")
        log(f"[DRY-RUN] LOG_FILE={LOG_FILE}")
        return

    # Objetivo/Prompt de usuario (un único user_message)
    objective = os.getenv("MINIUFO_OBJECTIVE")
    if not objective:
        # Permitir pasar el objetivo como argumento plano
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        objective = " ".join(args).strip() if args else "Hola, imprime 'ok' y termina."

    # Directorio de trabajo del proyecto (opcional)
    proj = os.getenv("MINIUFO_PROJECT_DIR")
    if proj:
        try:
            os.chdir(proj)
            log(f"cd {proj}")
        except Exception as e:
            log(f"WARNING: no pude entrar a {proj}: {e}")

    # Configurar interpreter y lanzar chat con único user_message
    try:
        interp = configure_interpreter(backend, base_url, model)
        log(f"Starting agent with backend={backend}, model={model}")
        t0=time.time()
        # Único user message:
        # - Indica guardar PNGs en ./outputs y usar backend Agg (ya forzado por graphics_guard)
        # - Pide reintentos hasta éxito (interpreter se encarga si el prompt lo especifica)
        user_message = (
            f"Objetivo:\n{objective}\n\n"
            "Reglas:\n"
            "- Usa Python cuando proceda.\n"
            "- Ejecuta, lee errores y autocorrige hasta que funcione (máximo 5 reintentos).\n"
            "- Guarda gráficos en ./outputs.\n"
            "- Escribe logs de decisiones breves en consola.\n"
        )
        interp.chat(user_message)  # system_message + 1 user_message
        dt=time.time()-t0
        log(f"Agent finished in {dt:.1f}s")
    except Exception as e:
        log(f"ERROR en ejecución del agente: {e}")
        raise

if __name__ == "__main__":
    main()
