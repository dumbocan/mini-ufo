def ensure_headless():
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
