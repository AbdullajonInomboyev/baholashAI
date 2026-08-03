"""Server tomonda SVG grafik geometriyasini hisoblaydi (tashqi kutubxonasiz)."""
import math


def bar_chart(data, width=520, height=190, pad=34):
    maxv = max((v for _, v in data), default=0) or 1
    n = len(data) or 1
    inner = width - pad * 2
    slot = inner / n
    bw = min(slot * 0.55, 46)
    bars = []
    for i, (lab, val) in enumerate(data):
        h = (val / maxv) * (height - pad - 18)
        x = pad + slot * i + (slot - bw) / 2
        y = height - pad - h
        bars.append({"x": round(x, 1), "y": round(y, 1), "w": round(bw, 1),
                     "h": round(h, 1), "label": lab, "value": val,
                     "cx": round(x + bw / 2, 1), "value_y": round(y - 5, 1)})
    return {"bars": bars, "width": width, "height": height, "baseline": height - pad,
            "label_y": height - pad + 16}


def donut(segments, size=168, thickness=32):
    total = sum(v for _, v, _ in segments) or 1
    cx = cy = size / 2
    r = (size - thickness) / 2
    start = -90.0
    out = []
    for lab, val, color in segments:
        frac = val / total
        ang = frac * 360
        # to'liq 100% bo'lsa uzluksiz aylana uchun kichik tuzatish
        end = start + (ang if ang < 359.999 else 359.999)
        large = 1 if ang > 180 else 0
        x1 = cx + r * math.cos(math.radians(start))
        y1 = cy + r * math.sin(math.radians(start))
        x2 = cx + r * math.cos(math.radians(end))
        y2 = cy + r * math.sin(math.radians(end))
        d = f"M {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x2:.1f} {y2:.1f}"
        out.append({"d": d, "color": color, "label": lab, "value": val,
                    "pct": round(frac * 100)})
        start = end
    return {"segments": out, "size": size, "cx": cx, "cy": cy, "r": r,
            "thickness": thickness, "total": total}
