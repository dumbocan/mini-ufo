from core.graphics_guard import ensure_headless
ensure_headless()

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

Path("outputs").mkdir(exist_ok=True, parents=True)
x = np.linspace(0, 2*np.pi, 400)
plt.figure()
plt.plot(x, np.sin(x))
plt.title("Seno")
plt.savefig("outputs/seno.png", dpi=120)
print("OK: outputs/seno.png")
