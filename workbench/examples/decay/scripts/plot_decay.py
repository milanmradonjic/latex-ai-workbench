"""Small SVG fixture; replace with the project's scientific plotting tools."""
import json
from pathlib import Path

data = json.loads(Path("results/decay.json").read_text())
time, amplitude = data["time"], data["amplitude"]
points = " ".join(f"{60 + 520*t/time[-1]:.3f},{240 - 190*a/max(amplitude):.3f}" for t, a in zip(time, amplitude))
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="300" viewBox="0 0 640 300">
<rect width="640" height="300" fill="white"/>
<text x="60" y="25" font-size="16">Synthetic decay fixture</text>
<path d="M60 40 V240 H590" fill="none" stroke="black"/>
<polyline points="{points}" fill="none" stroke="#1565c0" stroke-width="2"/>
<text x="290" y="280" font-size="14">Time (s)</text>
<text x="70" y="55" font-size="12">Amplitude (arbitrary units)</text>
</svg>
'''
Path("figures/decay.svg").write_text(svg)
