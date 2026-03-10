"""
Cookie Clicker - 8-bit retro incremental game.
Standalone Windows .exe build: see BUILD_EXE.md
"""
import io
import os
import struct
import sys
import json
import math
import random
import wave
import pygame
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

# Reference size for proportional layout (game draws at any window size)
REF_W, REF_H = 800, 600

# -----------------------------------------------------------------------------
# NES-style 8-bit color palette (indexed style)
# -----------------------------------------------------------------------------
class Palette:
    BACKGROUND = (28, 28, 50)        # Dark blue-black
    BACKGROUND_BOTTOM = (38, 38, 65) # Slightly lighter for gradient
    BACKGROUND_PANEL = (45, 45, 70)  # Slightly lighter panel
    BORDER = (80, 80, 120)
    TEXT = (255, 240, 180)           # Warm cream
    TEXT_DIM = (180, 170, 140)
    ACCENT = (255, 100, 100)         # Red accent
    GREEN = (100, 220, 100)          # Afford
    GOLD = (255, 215, 0)             # Cookie / highlight
    COOKIE_DOUGH = (210, 160, 100)
    COOKIE_CHIP = (80, 50, 30)
    WHITE = (255, 255, 255)


# -----------------------------------------------------------------------------
# Upgrade definition and cost/CPS math
# -----------------------------------------------------------------------------
UPGRADE_DEFS = [
    {"name": "Cursor", "base_cost": 15, "base_cps": 0.1},
    {"name": "Grandma", "base_cost": 100, "base_cps": 0.5},
    {"name": "Farm", "base_cost": 500, "base_cps": 4},
    {"name": "Mine", "base_cost": 3000, "base_cps": 10},
    {"name": "Factory", "base_cost": 10000, "base_cps": 40},
    {"name": "Bank", "base_cost": 40000, "base_cps": 100},
    {"name": "Temple", "base_cost": 200000, "base_cps": 400},
    {"name": "Wizard Tower", "base_cost": 1_300_000, "base_cps": 1600},
    {"name": "Shipment", "base_cost": 7_800_000, "base_cps": 6500},
    {"name": "Alchemy Lab", "base_cost": 44_000_000, "base_cps": 26000},
    {"name": "Portal", "base_cost": 260_000_000, "base_cps": 100000},
    {"name": "Time Machine", "base_cost": 1_400_000_000, "base_cps": 400000},
    {"name": "Antimatter", "base_cost": 7_100_000_000, "base_cps": 1_600_000},
    {"name": "Prism", "base_cost": 36_000_000_000, "base_cps": 6_400_000},
    {"name": "Chancemaker", "base_cost": 180_000_000_000, "base_cps": 25_000_000},
    {"name": "Fractal Engine", "base_cost": 900_000_000_000, "base_cps": 100_000_000},
    {"name": "JavaScript Console", "base_cost": 4_500_000_000_000, "base_cps": 400_000_000},
    {"name": "Idleverse", "base_cost": 22_000_000_000_000, "base_cps": 1_600_000_000},
    {"name": "Cortex Baker", "base_cost": 110_000_000_000_000, "base_cps": 6_400_000_000},
    {"name": "You", "base_cost": 550_000_000_000_000, "base_cps": 25_000_000_000},
    {"name": "Elder Pledge", "base_cost": 2_700_000_000_000_000, "base_cps": 100_000_000_000},
    {"name": "Elder Covenant", "base_cost": 13_000_000_000_000_000, "base_cps": 400_000_000_000},
    {"name": "Elder Ruin", "base_cost": 65_000_000_000_000_000, "base_cps": 1_600_000_000_000},
    {"name": "Black Hole", "base_cost": 320_000_000_000_000_000, "base_cps": 6_400_000_000_000},
    {"name": "Dimensional Rift", "base_cost": 1_600_000_000_000_000_000, "base_cps": 25_000_000_000_000},
    {"name": "Cookie Singularity", "base_cost": 8_000_000_000_000_000_000, "base_cps": 100_000_000_000_000},
    {"name": "Grandmaverse", "base_cost": 40_000_000_000_000_000_000, "base_cps": 400_000_000_000_000},
    {"name": "Reality Bender", "base_cost": 200_000_000_000_000_000_000, "base_cps": 1_600_000_000_000_000},
    {"name": "Omega Cursor", "base_cost": 1_000_000_000_000_000_000_000, "base_cps": 6_400_000_000_000_000},
    {"name": "The Void", "base_cost": 5_000_000_000_000_000_000_000, "base_cps": 25_000_000_000_000_000},
    {"name": "Infinity Oven", "base_cost": 25_000_000_000_000_000_000_000, "base_cps": 100_000_000_000_000_000},
    {"name": "Golden Monument", "base_cost": 125_000_000_000_000_000_000_000, "base_cps": 400_000_000_000_000_000},
]


class Upgrade:
    """Single upgrade type: cost scaling and multi-buy cost calculation."""
    MULTIPLIER = 1.15

    def __init__(self, name: str, base_cost: float, base_cps: float, count: int = 0):
        self.name = name
        self.base_cost = base_cost
        self.base_cps = base_cps
        self.count = count

    def cost_of_next_n(self, n: int) -> float:
        """Total cost to buy n more of this upgrade (next n from current count)."""
        if n <= 0:
            return 0.0
        # Sum of base_cost * 1.15^(count), base_cost * 1.15^(count+1), ... for n terms
        # Sum = base_cost * 1.15^count * (1.15^n - 1) / (1.15 - 1)
        r = self.MULTIPLIER
        start = self.count
        return self.base_cost * (r ** start) * ((r ** n) - 1) / (r - 1)

    def cps_for_count(self, c: int) -> float:
        return self.base_cps * c

    def total_cps(self) -> float:
        return self.cps_for_count(self.count)

    def max_affordable(self, cookies: float) -> int:
        """Largest n such that cost_of_next_n(n) <= cookies (binary search)."""
        if self.cost_of_next_n(1) > cookies:
            return 0
        lo, hi = 1, 1
        while self.cost_of_next_n(hi) <= cookies:
            hi = min(hi * 2, 1000000)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.cost_of_next_n(mid) <= cookies:
                lo = mid
            else:
                hi = mid
        return lo

    def to_dict(self) -> dict:
        return {"name": self.name, "base_cost": self.base_cost, "base_cps": self.base_cps, "count": self.count}

    @classmethod
    def from_def(cls, d: dict, count: int = 0) -> "Upgrade":
        return cls(d["name"], d["base_cost"], d["base_cps"], count)


# -----------------------------------------------------------------------------
# Floating text particle
# -----------------------------------------------------------------------------
class FloatingText:
    def __init__(self, x: float, y: float, text: str, font: pygame.font.Font, color=Palette.GOLD):
        self.x = x
        self.y = y
        self.text = text
        self.surf = font.render(text, True, color)
        self.life = 1.0  # 0..1, 1 = just spawned
        self.vy = -60  # pixels per second

    def update(self, dt: float) -> bool:
        self.y += self.vy * dt
        self.life -= dt * 1.2  # disappear in ~0.83s
        return self.life > 0

    def draw(self, screen: pygame.Surface, camera_y: float = 0, scale: float = 1.0):
        alpha = max(0, int(255 * self.life))
        s = self.surf.copy()
        s.set_alpha(alpha)
        if scale != 1.0 and scale > 0:
            w, h = max(1, int(s.get_width() * scale)), max(1, int(s.get_height() * scale))
            s = pygame.transform.scale(s, (w, h))
        screen.blit(s, (int(self.x - s.get_width() / 2), int(self.y + camera_y)))


# -----------------------------------------------------------------------------
# Falling cookie particle (for reset animation)
# -----------------------------------------------------------------------------
class FallingCookie:
    def __init__(self, x: float, window_h: int, size: int):
        self.x = x
        self.y = 0  # Always start at the top of the window
        self.size = max(4, size)
        self.vy = random.uniform(80, 200)
        self.vx = random.uniform(-40, 40)
        self.life = 1.0
        self.rot = random.uniform(0, 360)

    def update(self, dt: float) -> bool:
        self.y += self.vy * dt
        self.x += self.vx * dt
        self.life -= dt * 0.4
        return self.life > 0

    def draw(self, surf: pygame.Surface):
        r = max(2, self.size // 2)
        pygame.draw.circle(surf, Palette.COOKIE_DOUGH, (int(self.x), int(self.y)), r)
        pygame.draw.circle(surf, Palette.COOKIE_CHIP, (int(self.x), int(self.y)), max(1, r // 2))

# -----------------------------------------------------------------------------
# Flying Rainbow Cookie
# -----------------------------------------------------------------------------
class RainbowCookie:
    COLORS = [
        (255, 0, 0), (255, 128, 0), (255, 255, 0),
        (0, 255, 0), (0, 128, 255), (0, 0, 255), (128, 0, 255)
    ]
    def __init__(self, w, h):
        self.radius = max(24, min(w, h) // 18)
        self.x = -self.radius
        self.y = random.randint(self.radius, h // 2)
        self.speed = random.uniform(120, 200)
        self.active = True
        self.timer = 0

    def update(self, dt, w, h):
        self.x += self.speed * dt
        if self.x - self.radius > w:
            self.active = False

    def draw(self, surf):
        for i, color in enumerate(self.COLORS):
            pygame.draw.circle(surf, color, (int(self.x), int(self.y)), self.radius - i*3)
        pygame.draw.circle(surf, (255,255,255), (int(self.x), int(self.y)), self.radius//2)

    def rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius*2, self.radius*2)


# -----------------------------------------------------------------------------
# Confetti particle + Golden cookie
# -----------------------------------------------------------------------------
class Confetti:
    COLORS = [(255,20,147),(255,165,0),(60,179,113),(65,105,225),(255,215,0)]
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-120, 120)
        self.vy = random.uniform(-200, -40)
        self.life = random.uniform(0.6, 1.4)
        self.size = random.randint(2,6)
        self.color = random.choice(self.COLORS)

    def update(self, dt):
        self.vy += 400 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surf):
        r = max(1, int(self.size))
        pygame.draw.rect(surf, self.color, (int(self.x), int(self.y), r, r))


class GoldenCookie:
    def __init__(self, w, h):
        self.radius = max(18, min(w, h) // 24)
        self.x = random.randint(self.radius, w - self.radius)
        self.y = random.randint(self.radius, h // 2)
        self.life = 6.0  # seconds visible
        self.active = True

    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            self.active = False

    def draw(self, surf):
        # shiny gold concentric circles
        for i, col in enumerate([(255,223,0),(255,240,150),(255,200,50)]):
            pygame.draw.circle(surf, col, (int(self.x), int(self.y)), max(1, self.radius - i*3))

    def rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius*2, self.radius*2)


# -----------------------------------------------------------------------------
# Main Game
# -----------------------------------------------------------------------------
class Game:
    W = 660
    H = 350
    SAVE_INTERVAL = 30.0
    SAVE_PATH = "cookie_save.json"

    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        except Exception:
            pass
        pygame.display.set_caption("Cookie Clicker (8-bit)")
        self.screen = pygame.display.set_mode((self.W, self.H), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.load_fonts()
        self.snd_click = self._load_or_make_sound("click", 600, 0.06)
        self.snd_buy = self._load_or_make_sound("buy", 400, 0.1)
        self.snd_reset = self._load_or_make_sound("reset", 200, 0.15)
        self.reset_state()
        self.load_save()
        self.store_scroll = 0
        self.store_scroll_vel = 0
        self.multiplier_index = 0  # 0=1x, 1=10x, 2=100x, 3=Max
        self.multiplier_labels = ["1x", "10x", "100x", "Max"]
        self.cookie_scale = 1.0  # 1.0 = normal, <1 when clicked
        self.cookie_scale_vel = 0
        self.floating_texts: list[FloatingText] = []
        self.save_timer = 0.0
        self.playtime = 0.0
        self.running = True
        self.falling_cookies: list[FallingCookie] = []
        self.reset_pending = False
        self.reset_timer = 0.0
        self.rainbow_cookie = None
        self.rainbow_timer = random.uniform(15, 35)
        self.confetti: list[Confetti] = []
        self.golden: GoldenCookie | None = None
        self.golden_timer = random.uniform(20, 50)
        self.afk_mode = False
        self.afk_base_cps = 1.0
        self.afk_multiplier_index = 0
        self.afk_multiplier_labels = ["1x", "2x", "3x", "5x", "10x"]
        self.afk_multiplier_values = [1.0, 2.0, 3.0, 5.0, 10.0]
        self.afk_custom_active = False
        self.afk_custom_text = f"{self.afk_base_cps:.1f}"
        # click handling for single vs double click
        self._last_click_time = 0
        self._last_click_target = None
        self._double_click_ms = 400
        self.afk_custom_selected = False

    def load_fonts(self):
        """Load Roboto Bold or similar clean font; fallback to system bold."""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        font_paths = [
            os.path.join(base, "fonts", "Roboto-Bold.ttf"),
            os.path.join(base, "fonts", "Roboto-Bold.ttf"),
            os.path.join(base, "fonts", "PressStart2P-Regular.ttf"),
            "fonts/Roboto-Bold.ttf",
            "fonts/PressStart2P-Regular.ttf",
        ]
        path = None
        for p in font_paths:
            if os.path.isfile(p):
                path = p
                break
        if path:
            self.font_large = pygame.font.Font(path, 26)
            self.font_medium = pygame.font.Font(path, 18)
            self.font_small = pygame.font.Font(path, 14)
        else:
            self.font_large = pygame.font.SysFont("arial", 26, bold=True)
            self.font_medium = pygame.font.SysFont("arial", 18, bold=True)
            self.font_small = pygame.font.SysFont("arial", 14, bold=True)

    def _load_or_make_sound(self, name: str, freq: float = 440, duration: float = 0.1):
        """Load sound from sounds/name.wav or generate a short tone."""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        for path in [os.path.join(base, "sounds", f"{name}.wav"), os.path.join(self._save_dir(), "sounds", f"{name}.wav"), f"sounds/{name}.wav"]:
            if os.path.isfile(path):
                try:
                    return pygame.mixer.Sound(path)
                except Exception:
                    break
        try:
            buf = io.BytesIO()
            rate = 22050
            n = int(rate * duration)
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                for i in range(n):
                    val = int(32767 * 0.2 * math.sin(2 * math.pi * freq * i / rate))
                    val = max(-32767, min(32767, val))
                    w.writeframes(struct.pack("<h", val))
            buf.seek(0)
            return pygame.mixer.Sound(buf)
        except Exception:
            return None

    def _play(self, sound):
        if sound is not None:
            try:
                sound.play()
            except Exception:
                pass

    def _blit_text_scaled(self, surf: pygame.Surface, text_surf: pygame.Surface, x: int, y: int, scale: float, center: bool = False):
        """Blit text scaled by scale so it auto-resizes with window. If center, (x,y) is center of text."""
        if scale <= 0:
            return
        w, h = text_surf.get_size()
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        scaled = pygame.transform.smoothscale(text_surf, (sw, sh))
        if center:
            x, y = x - sw // 2, y - sh // 2
        surf.blit(scaled, (x, y))

    def _draw_background(self, surf: pygame.Surface, w: int, h: int):
        """Draw a nice gradient background with subtle texture."""
        for y in range(h):
            t = y / max(1, h)
            r = int(Palette.BACKGROUND[0] + t * (Palette.BACKGROUND_BOTTOM[0] - Palette.BACKGROUND[0]))
            g = int(Palette.BACKGROUND[1] + t * (Palette.BACKGROUND_BOTTOM[1] - Palette.BACKGROUND[1]))
            b = int(Palette.BACKGROUND[2] + t * (Palette.BACKGROUND_BOTTOM[2] - Palette.BACKGROUND[2]))
            pygame.draw.line(surf, (r, g, b), (0, y), (w, y))
        # Very subtle dot texture (every 24px, faint)
        step = 24
        for py in range(0, h, step):
            for px in range(0, w, step):
                pygame.draw.circle(surf, (35, 35, 58), (px, py), 1)

    def reset_state(self):
        self.cookies = 0.0
        self.cookies_accum = 0.0  # sub-integer accumulation
        self.upgrades = [Upgrade.from_def(d) for d in UPGRADE_DEFS]
        self.total_clicked = 0

    def total_cps(self) -> float:
        return sum(u.total_cps() for u in self.upgrades)

    def buy_multiplier(self) -> int:
        """Current buy amount: 1, 10, 100, or max for selected upgrade (computed per upgrade)."""
        idx = self.multiplier_index
        if idx == 0:
            return 1
        if idx == 1:
            return 10
        if idx == 2:
            return 100
        return -1  # Max: call max_affordable per upgrade

    def try_buy(self, upgrade: Upgrade) -> tuple[bool, float]:
        """Returns (success, cost_paid). cost_paid is 0 if failed."""
        n = self.buy_multiplier()
        if n == -1:
            n = upgrade.max_affordable(self.cookies)
        if n <= 0:
            return False, 0.0
        cost = upgrade.cost_of_next_n(n)
        if cost > self.cookies:
            return False, 0.0
        self.cookies -= cost
        upgrade.count += n
        return True, cost

    def add_floating(self, x: float, y: float, text: str):
        self.floating_texts.append(FloatingText(x, y, text, self.font_medium, Palette.GOLD))

    def play_error_sound(self):
        """Show Windows error dialog and play error sound when CPS exceeds limit."""
        if WINSOUND_AVAILABLE:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONERROR)
            except Exception:
                pass
        if TK_AVAILABLE:
            try:
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("Error", "CPS value exceeds maximum allowed (100,000,000,000)")
                root.destroy()
            except Exception:
                pass

    def draw_upgrade_icon(self, surf: pygame.Surface, name: str, x: int, y: int, size: int):
        """Draw a simple pixel-art icon for each upgrade type."""
        s2 = size // 2
        name_lower = name.lower()
        if "cursor" in name_lower and "omega" not in name_lower:
            # Hand / pointer
            pygame.draw.rect(surf, Palette.TEXT, (x + s2 - 4, y + 2, 6, 10))
            pygame.draw.rect(surf, Palette.TEXT_DIM, (x + s2 - 2, y + 10, 4, 6))
        elif "grandma" in name_lower:
            # Face + bun
            pygame.draw.circle(surf, Palette.TEXT, (x + s2, y + s2), s2 - 2)
            pygame.draw.circle(surf, Palette.COOKIE_DOUGH, (x + s2, y + 4), 4)
        elif "farm" in name_lower:
            # Barn: red rect + triangle roof
            pygame.draw.polygon(surf, Palette.ACCENT, [(x + s2, y + 2), (x + 2, y + size - 4), (x + size - 2, y + size - 4)])
            pygame.draw.rect(surf, Palette.ACCENT, (x + 4, y + size//2, size - 8, size//2 - 4))
        elif "mine" in name_lower:
            # Mine entrance (dark arch)
            pygame.draw.rect(surf, (60, 50, 40), (x + 2, y + 4, size - 4, size - 8))
            pygame.draw.rect(surf, Palette.TEXT_DIM, (x + s2 - 3, y + size - 10, 6, 6))
        elif "factory" in name_lower:
            # Factory block + smokestack
            pygame.draw.rect(surf, Palette.TEXT_DIM, (x + 2, y + 6, size - 4, size - 10))
            pygame.draw.rect(surf, (80, 80, 80), (x + size - 8, y + 2, 4, 8))
        elif "bank" in name_lower:
            # Pillars
            for i in range(3):
                pygame.draw.rect(surf, Palette.TEXT, (x + 4 + i * 6, y + 4, 4, size - 8))
        elif "temple" in name_lower:
            # Triangle + base
            pygame.draw.polygon(surf, Palette.TEXT, [(x + s2, y + 2), (x + 2, y + size - 4), (x + size - 2, y + size - 4)])
            pygame.draw.rect(surf, Palette.TEXT_DIM, (x + 6, y + size - 8, size - 12, 6))
        elif "wizard" in name_lower:
            # Cone (hat)
            pygame.draw.polygon(surf, (100, 50, 150), [(x + s2, y + 2), (x + 2, y + size - 2), (x + size - 2, y + size - 2)])
        elif "shipment" in name_lower:
            # Rocket / box
            pygame.draw.rect(surf, Palette.TEXT_DIM, (x + 4, y + 6, size - 8, size - 10))
            pygame.draw.polygon(surf, Palette.ACCENT, [(x + s2, y + size - 4), (x + 4, y + size - 2), (x + size - 4, y + size - 2)])
        elif "alchemy" in name_lower:
            # Flask
            pygame.draw.rect(surf, (80, 150, 80), (x + 6, y + 4, size - 12, size - 10))
            pygame.draw.rect(surf, Palette.TEXT, (x + s2 - 2, y + size - 6, 4, 6))
        elif "portal" in name_lower:
            pygame.draw.ellipse(surf, (150, 100, 255), (x + 2, y + 4, size - 4, size - 8))
        elif "prism" in name_lower:
            pygame.draw.polygon(surf, (200, 150, 255), [(x + s2, y + 2), (x + 2, y + size - 2), (x + size - 2, y + size - 2)])
        else:
            # Generic building
            pygame.draw.rect(surf, Palette.TEXT_DIM, (x + 4, y + 6, size - 8, size - 10))
            pygame.draw.rect(surf, Palette.BORDER, (x + 4, y + 6, size - 8, size - 10), 1)

    def draw_cookie(self, cx: int, cy: int, radius: int):
        """Pixelated cookie: draw in blocks for 8-bit look; size scales with resolution."""
        scale = max(0.85, self.cookie_scale)
        r = int(radius * scale)
        block = max(4, r // 18)  # Chunky pixels
        # Draw cookie as blocky circle
        for dy in range(-r, r + 1, block):
            for dx in range(-r, r + 1, block):
                if dx * dx + dy * dy <= r * r:
                    pygame.draw.rect(self.screen, Palette.COOKIE_DOUGH, (cx + dx, cy + dy, block, block))
        # Border (blocky)
        for dy in range(-r, r + 1, block):
            for dx in range(-r, r + 1, block):
                d = dx * dx + dy * dy
                if r * r < d <= (r + block * 2) ** 2:
                    pygame.draw.rect(self.screen, Palette.BORDER, (cx + dx, cy + dy, block, block))
        # Chips (blocky)
        chip_r = max(block, r // 6)
        for dx, dy in [(-r//2, -r//3), (r//3, -r//4), (-r//4, r//4), (r//3, r//3), (0, -r//2)]:
            for cy_ in range(-chip_r, chip_r + 1, block):
                for cx_ in range(-chip_r, chip_r + 1, block):
                    if cx_ * cx_ + cy_ * cy_ <= chip_r * chip_r:
                        pygame.draw.rect(self.screen, Palette.COOKIE_CHIP, (cx + dx + cx_, cy + dy + cy_, block, block))

    def draw_store_panel(self, panel_rect: pygame.Rect, line_h: int, start_y: int, toggle_y: int, ui_scale: float = 1.0):
        """Scrollable store with icons; prices update by multiplier. Text auto-resizes with ui_scale."""
        surf = self.screen
        pygame.draw.rect(surf, Palette.BACKGROUND_PANEL, panel_rect)
        pygame.draw.rect(surf, Palette.BORDER, panel_rect, 2)
        title = self.font_medium.render("STORE", True, Palette.TEXT)
        self._blit_text_scaled(surf, title, panel_rect.x + 12, panel_rect.y + 8, ui_scale)
        toggle_w = max(40, (panel_rect.width - 24) // 4 - 4)
        toggle_h = min(28, line_h - 8)
        for i, label in enumerate(self.multiplier_labels):
            rx = panel_rect.x + 8 + i * (toggle_w + 4)
            r = pygame.Rect(rx, toggle_y, toggle_w, toggle_h)
            col = Palette.ACCENT if i == self.multiplier_index else Palette.BACKGROUND
            pygame.draw.rect(surf, col, r)
            pygame.draw.rect(surf, Palette.BORDER, r, 1)
            t = self.font_small.render(label, True, Palette.TEXT)
            self._blit_text_scaled(surf, t, rx + toggle_w // 2, toggle_y + toggle_h // 2, ui_scale, center=True)
        # List of upgrades with icons (scrollable)
        icon_size = min(32, line_h - 12)
        clip = pygame.Rect(panel_rect.x, start_y, panel_rect.width, panel_rect.bottom - start_y)
        surf.set_clip(clip)
        for i, u in enumerate(self.upgrades):
            ny = start_y + i * line_h - int(self.store_scroll)
            if ny + line_h < start_y or ny > panel_rect.bottom:
                continue
            # Row background
            row_rect = pygame.Rect(panel_rect.x + 4, ny + 2, panel_rect.width - 8, line_h - 4)
            pygame.draw.rect(surf, Palette.BACKGROUND, row_rect)
            pygame.draw.rect(surf, Palette.BORDER, row_rect, 1)
            # Icon
            self.draw_upgrade_icon(surf, u.name, panel_rect.x + 8, ny + (line_h - icon_size) // 2, icon_size)
            # Name and price (auto-resize)
            name_text = self.font_small.render(f"{u.name} x{u.count}", True, Palette.TEXT)
            self._blit_text_scaled(surf, name_text, panel_rect.x + 46, ny + 6, ui_scale)
            n = self.buy_multiplier()
            if n == -1:
                n = u.max_affordable(self.cookies)
            cost = u.cost_of_next_n(n) if n > 0 else u.cost_of_next_n(1)
            can_afford = self.cookies >= cost and n > 0
            if n > 0:
                price_text = f"{int(cost)} C" + (" (x" + str(n) + ")" if n > 1 else "")
            else:
                price_text = f"{int(cost)} C (next)"
            color = Palette.GREEN if can_afford else Palette.TEXT_DIM
            price_surf = self.font_small.render(price_text, True, color)
            self._blit_text_scaled(surf, price_surf, panel_rect.x + 46, ny + 28, ui_scale)
        surf.set_clip(None)

    def get_store_item_at(self, panel_rect: pygame.Rect, mouse_y: int, line_h: int, start_y: int) -> int | None:
        """Return upgrade index under mouse_y in store, or None."""
        i = (mouse_y - start_y + int(self.store_scroll)) // line_h
        if 0 <= i < len(self.upgrades):
            return i
        return None

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.playtime += dt
            self.save_timer += dt
            if self.save_timer >= self.SAVE_INTERVAL:
                self.save_timer = 0
                self.save_save()

            # Rainbow cookie spawn logic
            if self.rainbow_cookie is None:
                self.rainbow_timer -= dt
                if self.rainbow_timer <= 0:
                    self.rainbow_cookie = RainbowCookie(self.W, self.H)
                    self.rainbow_timer = random.uniform(30, 60)
            else:
                self.rainbow_cookie.update(dt, self.W, self.H)
                if not self.rainbow_cookie.active:
                    self.rainbow_cookie = None

            # Golden cookie spawn logic
            if self.golden is None:
                self.golden_timer -= dt
                if self.golden_timer <= 0:
                    self.golden = GoldenCookie(self.W, self.H)
                    self.golden_timer = random.uniform(40, 90)
            else:
                self.golden.update(dt)
                if not self.golden.active:
                    self.golden = None

            # Recompute layout on resize (resolution-free)
            panel_width = max(180, int(220 * self.W / REF_W))
            panel_rect = pygame.Rect(self.W - panel_width, 0, panel_width, self.H)
            game_w = self.W - panel_width
            cookie_radius = int(min(game_w, self.H) * 0.26)
            cookie_rect_radius = int(cookie_radius * 1.15)
            cx = game_w // 2
            cy = self.H // 2
            reset_rect = pygame.Rect(int(12 * self.W / REF_W), self.H - int(40 * self.H / REF_H), int(90 * self.W / REF_W), int(32 * self.H / REF_H))
            afk_rect = pygame.Rect(reset_rect.right + int(12 * self.W / REF_W), reset_rect.y, int(110 * self.W / REF_W), reset_rect.height)
            # removed +/- buttons; multipliers start right after AFK toggle
            afk_mul1_rect = pygame.Rect(afk_rect.right + int(12 * self.W / REF_W), afk_rect.y, int(36 * self.W / REF_W), afk_rect.height)
            afk_mul2_rect = pygame.Rect(afk_mul1_rect.right + int(6 * self.W / REF_W), afk_rect.y, int(36 * self.W / REF_W), afk_rect.height)
            afk_mul3_rect = pygame.Rect(afk_mul2_rect.right + int(6 * self.W / REF_W), afk_rect.y, int(36 * self.W / REF_W), afk_rect.height)
            afk_mul4_rect = pygame.Rect(afk_mul3_rect.right + int(6 * self.W / REF_W), afk_rect.y, int(36 * self.W / REF_W), afk_rect.height)
            afk_mul5_rect = pygame.Rect(afk_mul4_rect.right + int(6 * self.W / REF_W), afk_rect.y, int(36 * self.W / REF_W), afk_rect.height)
            afk_custom_rect = pygame.Rect(afk_mul5_rect.right + int(8 * self.W / REF_W), afk_rect.y, int(90 * self.W / REF_W), afk_rect.height)
            line_h = max(44, int(58 * self.H / REF_H))
            start_y_store = int(68 * self.H / REF_H)
            toggle_y = int(36 * self.H / REF_H)
            toggle_w = max(40, (panel_rect.width - 24) // 4 - 4)
            toggle_h = min(28, line_h - 8)
            ui_scale = min(self.W / REF_W, self.H / REF_H)

            # Reset pending: countdown then reset
            if self.reset_pending:
                self.reset_timer -= dt
                if self.reset_timer <= 0:
                    self.reset_state()
                    self.reset_pending = False
                    self.falling_cookies.clear()

            # Falling cookies update
            self.falling_cookies = [fc for fc in self.falling_cookies if fc.update(dt)]
            # Confetti update
            self.confetti = [c for c in self.confetti if c.update(dt)]

            # Cookie scale animation
            if self.cookie_scale < 1.0:
                self.cookie_scale_vel += 800 * dt
                self.cookie_scale = min(1.0, self.cookie_scale + self.cookie_scale_vel * dt)
                if self.cookie_scale >= 1.0:
                    self.cookie_scale = 1.0
                    self.cookie_scale_vel = 0
            else:
                self.cookie_scale_vel *= 0.9

            # CPS (including AFK contribution)
            cps = self.total_cps()
            afk_cps = 0.0
            if self.afk_mode:
                afk_cps = self.afk_base_cps * self.afk_multiplier_values[self.afk_multiplier_index]
            self.cookies_accum += (cps + afk_cps) * dt
            add = int(self.cookies_accum)
            if add > 0:
                self.cookies += add
                self.cookies_accum -= add

            # Store scroll (clamp to content)
            clip_h = self.H - start_y_store - 8
            total_h = len(self.upgrades) * line_h
            max_scroll = max(0, total_h - clip_h)
            self.store_scroll = max(0, min(max_scroll, self.store_scroll + self.store_scroll_vel * dt))
            self.store_scroll_vel *= 0.9

            # Events (mouse in screen coords - resolution-free)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if e.button == 1:
                        mx, my = e.pos
                        # Rainbow cookie click
                        if self.rainbow_cookie and self.rainbow_cookie.rect().collidepoint(mx, my):
                            self._play(self.snd_click)
                            self.add_floating(mx, my, "RAINBOW!")
                            self.cookies *= 2
                            # confetti burst
                            for _ in range(40):
                                self.confetti.append(Confetti(mx + random.uniform(-20,20), my + random.uniform(-10,10)))
                            self.rainbow_cookie = None
                        # Golden cookie click
                        elif self.golden and self.golden.rect().collidepoint(mx, my):
                            self._play(self.snd_buy)
                            bonus = max(50, int(self.cookies * 0.1))
                            self.cookies += bonus
                            self.add_floating(mx, my, f"+{bonus}!")
                            for _ in range(60):
                                self.confetti.append(Confetti(self.golden.x + random.uniform(-30,30), self.golden.y + random.uniform(-20,20)))
                            self.golden = None
                        # AFK button and multiplier clicks (no +/- buttons anymore)
                        elif afk_rect.collidepoint(mx, my):
                            now = pygame.time.get_ticks()
                            same_target = self._last_click_target == "afk"
                            if same_target and (now - self._last_click_time) <= self._double_click_ms:
                                # double-click on AFK => open custom AFK dialog (same behavior as custom button)
                                self.afk_custom_active = True
                                self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                if TK_AVAILABLE:
                                    try:
                                        root = tk.Tk()
                                        root.withdraw()
                                        res = simpledialog.askstring("Custom AFK CPS", "Enter AFK CPS (e.g. 1.5):", initialvalue=f"{self.afk_base_cps:.2f}")
                                        root.destroy()
                                        if res is not None:
                                            try:
                                                v = float(res)
                                                if v > 100000000000:
                                                    self.play_error_sound()
                                                else:
                                                    self.afk_base_cps = max(0.0, v)
                                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                                    self.afk_custom_active = False
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            else:
                                # single click toggles AFK on/off
                                self.afk_mode = not self.afk_mode
                            self._last_click_time = now
                            self._last_click_target = "afk"
                        elif afk_mul1_rect.collidepoint(mx, my):
                            now = pygame.time.get_ticks()
                            same = self._last_click_target == "mul0"
                            if same and (now - self._last_click_time) <= self._double_click_ms:
                                # double-click: open custom AFK dialog
                                if TK_AVAILABLE:
                                    try:
                                        root = tk.Tk()
                                        root.withdraw()
                                        res = simpledialog.askstring("Custom AFK CPS", "Enter AFK CPS (e.g. 1.5):", initialvalue=f"{self.afk_base_cps:.2f}")
                                        root.destroy()
                                        if res is not None:
                                            try:
                                                v = float(res)
                                                if v > 100000000000:
                                                    self.play_error_sound()
                                                else:
                                                    self.afk_base_cps = max(0.0, v)
                                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            else:
                                # toggle: if already selected, deselect; otherwise select
                                if self.afk_multiplier_index == 0 and not self.afk_custom_selected:
                                    self.afk_multiplier_index = -1  # deselect
                                else:
                                    self.afk_multiplier_index = 0
                                    self.afk_custom_selected = False
                            self._last_click_time = now
                            self._last_click_target = "mul0"
                        elif afk_mul2_rect.collidepoint(mx, my):
                            now = pygame.time.get_ticks()
                            same = self._last_click_target == "mul1"
                            if same and (now - self._last_click_time) <= self._double_click_ms:
                                if TK_AVAILABLE:
                                    try:
                                        root = tk.Tk()
                                        root.withdraw()
                                        res = simpledialog.askstring("Custom AFK CPS", "Enter AFK CPS (e.g. 1.5):", initialvalue=f"{self.afk_base_cps:.2f}")
                                        root.destroy()
                                        if res is not None:
                                            try:
                                                v = float(res)
                                                if v > 100000000000:
                                                    self.play_error_sound()
                                                else:
                                                    self.afk_base_cps = max(0.0, v)
                                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            else:
                                if self.afk_multiplier_index == 1 and not self.afk_custom_selected:
                                    self.afk_multiplier_index = -1
                                else:
                                    self.afk_multiplier_index = 1
                                    self.afk_custom_selected = False
                            self._last_click_time = now
                            self._last_click_target = "mul1"
                        elif afk_mul3_rect.collidepoint(mx, my):
                            now = pygame.time.get_ticks()
                            same = self._last_click_target == "mul2"
                            if same and (now - self._last_click_time) <= self._double_click_ms:
                                if TK_AVAILABLE:
                                    try:
                                        root = tk.Tk()
                                        root.withdraw()
                                        res = simpledialog.askstring("Custom AFK CPS", "Enter AFK CPS (e.g. 1.5):", initialvalue=f"{self.afk_base_cps:.2f}")
                                        root.destroy()
                                        if res is not None:
                                            try:
                                                v = float(res)
                                                if v > 100000000000:
                                                    self.play_error_sound()
                                                else:
                                                    self.afk_base_cps = max(0.0, v)
                                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            else:
                                if self.afk_multiplier_index == 2 and not self.afk_custom_selected:
                                    self.afk_multiplier_index = -1
                                else:
                                    self.afk_multiplier_index = 2
                                    self.afk_custom_selected = False
                            self._last_click_time = now
                            self._last_click_target = "mul2"
                        elif afk_mul4_rect.collidepoint(mx, my):
                            now = pygame.time.get_ticks()
                            same = self._last_click_target == "mul3"
                            if same and (now - self._last_click_time) <= self._double_click_ms:
                                if TK_AVAILABLE:
                                    try:
                                        root = tk.Tk()
                                        root.withdraw()
                                        res = simpledialog.askstring("Custom AFK CPS", "Enter AFK CPS (e.g. 1.5):", initialvalue=f"{self.afk_base_cps:.2f}")
                                        root.destroy()
                                        if res is not None:
                                            try:
                                                v = float(res)
                                                if v > 100000000000:
                                                    self.play_error_sound()
                                                else:
                                                    self.afk_base_cps = max(0.0, v)
                                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            else:
                                if self.afk_multiplier_index == 3 and not self.afk_custom_selected:
                                    self.afk_multiplier_index = -1
                                else:
                                    self.afk_multiplier_index = 3
                                    self.afk_custom_selected = False
                            self._last_click_time = now
                            self._last_click_target = "mul3"
                        elif afk_mul5_rect.collidepoint(mx, my):
                            now = pygame.time.get_ticks()
                            same = self._last_click_target == "mul4"
                            if same and (now - self._last_click_time) <= self._double_click_ms:
                                if TK_AVAILABLE:
                                    try:
                                        root = tk.Tk()
                                        root.withdraw()
                                        res = simpledialog.askstring("Custom AFK CPS", "Enter AFK CPS (e.g. 1.5):", initialvalue=f"{self.afk_base_cps:.2f}")
                                        root.destroy()
                                        if res is not None:
                                            try:
                                                v = float(res)
                                                if v > 100000000000:
                                                    self.play_error_sound()
                                                else:
                                                    self.afk_base_cps = max(0.0, v)
                                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            else:
                                if self.afk_multiplier_index == 4 and not self.afk_custom_selected:
                                    self.afk_multiplier_index = -1
                                else:
                                    self.afk_multiplier_index = 4
                                    self.afk_custom_selected = False
                            self._last_click_time = now
                            self._last_click_target = "mul4"
                        elif afk_custom_rect.collidepoint(mx, my):
                            # single-click should select the custom option; double-click opens dialog (or fallback)
                            now = pygame.time.get_ticks()
                            same_target = self._last_click_target == "custom"
                            # single-click: toggle custom selection (select if not selected, deselect if already selected)
                            if self.afk_custom_selected and not same_target or (same_target and (now - self._last_click_time) > self._double_click_ms):
                                # just toggling, not double-clicking
                                self.afk_custom_selected = not self.afk_custom_selected
                            elif not self.afk_custom_selected:
                                self.afk_custom_selected = True
                            self.afk_custom_active = False
                            # clear multiplier selection
                            # (multipliers use afk_multiplier_index; keep it, but visually prefer custom when selected)
                            if same_target and (now - self._last_click_time) <= self._double_click_ms:
                                # double-click -> open OS dialog (or set in-game edit if tkinter unavailable)
                                if TK_AVAILABLE:
                                    try:
                                        root = tk.Tk()
                                        root.withdraw()
                                        res = simpledialog.askstring("Custom AFK CPS", "Enter AFK CPS (e.g. 1.5):", initialvalue=f"{self.afk_base_cps:.2f}")
                                        root.destroy()
                                        if res is not None:
                                            try:
                                                v = float(res)
                                                if v > 100000000000:
                                                    self.play_error_sound()
                                                else:
                                                    self.afk_base_cps = max(0.0, v)
                                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                                else:
                                    # fallback: activate in-game textbox for editing
                                    self.afk_custom_active = True
                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                            self._last_click_time = now
                            self._last_click_target = "custom"
                        # Reset button (only when not in reset animation)
                        elif not self.reset_pending and reset_rect.collidepoint(mx, my):
                            self._play(self.snd_reset)
                            self.reset_pending = True
                            self.reset_timer = 3.0
                            ps = max(8, int(20 * ui_scale))
                            for _ in range(80):
                                self.falling_cookies.append(FallingCookie(
                                    random.randint(0, self.W),
                                    self.H,
                                    random.randint(ps // 2, ps),
                                ))
                        # Cookie click: +1 cookie and falling cookies at click
                        elif (mx - cx) ** 2 + (my - cy) ** 2 <= cookie_rect_radius ** 2:
                            self._play(self.snd_click)
                            self.cookies += 1
                            self.total_clicked += 1
                            self.cookie_scale = 0.92
                            self.cookie_scale_vel = -200
                            self.add_floating(mx, my, "+1")
                            # Spawn falling cookies at click position (scaled)
                            ps = max(6, int(14 * ui_scale))
                            for _ in range(6):
                                self.falling_cookies.append(FallingCookie(
                                    mx + random.randint(-30, 30),
                                    self.H,
                                    random.randint(max(4, ps - 8), ps),
                                ))
                        # Multi-buy toggles
                        elif panel_rect.collidepoint(mx, my):
                            if toggle_y <= my < toggle_y + toggle_h:
                                idx = (mx - panel_rect.x - 8) // (toggle_w + 4)
                                if 0 <= idx < 4:
                                    self.multiplier_index = idx
                            # Store item click (buy)
                            idx = self.get_store_item_at(panel_rect, my, line_h, start_y_store)
                            if idx is not None:
                                u = self.upgrades[idx]
                                ok, cost_paid = self.try_buy(u)
                                if ok and cost_paid > 0:
                                    self._play(self.snd_buy)
                                    self.add_floating(panel_rect.x + panel_rect.width // 2, my, f"-{int(cost_paid)}")
                    elif e.button == 4:
                        if panel_rect.collidepoint(*e.pos):
                            self.store_scroll_vel -= 200
                    elif e.button == 5:
                        if panel_rect.collidepoint(*e.pos):
                            self.store_scroll_vel += 200
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_a:
                        self.afk_mode = not self.afk_mode
                    # (custom AFK dialog handled via OS dialog when possible)
                    elif self.afk_custom_active:
                        # handle textbox input for custom AFK CPS (fallback if tkinter unavailable)
                        if e.key == pygame.K_RETURN or e.key == pygame.K_KP_ENTER:
                            try:
                                v = float(self.afk_custom_text)
                                # Validate CPS doesn't exceed 100 billion
                                if v > 100000000000:
                                    self.play_error_sound()
                                    self.afk_custom_text = f"{self.afk_base_cps:.2f}"
                                else:
                                    self.afk_base_cps = max(0.0, v)
                            except Exception:
                                pass
                            self.afk_custom_active = False
                        elif e.key == pygame.K_ESCAPE:
                            self.afk_custom_active = False
                        elif e.key == pygame.K_BACKSPACE:
                            self.afk_custom_text = self.afk_custom_text[:-1]
                        else:
                            ch = e.unicode
                            if ch and (ch.isdigit() or ch == '.'):
                                self.afk_custom_text += ch
                elif e.type == pygame.VIDEORESIZE:
                    self.W, self.H = e.w, e.h
                    self.screen = pygame.display.set_mode((self.W, self.H), pygame.SCALED | pygame.RESIZABLE)

            # (Old interval-based AFK removed — AFK now contributes CPS directly)

            # Update floating texts
            self.floating_texts = [ft for ft in self.floating_texts if ft.update(dt)]

            # ---- Draw directly to screen (resolution-free, no stretch) ----
            self._draw_background(self.screen, self.W, self.H)
            for fc in self.falling_cookies:
                fc.draw(self.screen)
            # draw confetti
            for c in self.confetti:
                c.draw(self.screen)
            # Draw golden cookie if present
            if self.golden:
                self.golden.draw(self.screen)
            # Draw rainbow cookie if present
            if self.rainbow_cookie:
                self.rainbow_cookie.draw(self.screen)
            self.draw_cookie(cx, cy, cookie_radius)
            for ft in self.floating_texts:
                ft.draw(self.screen, scale=ui_scale)
            # Score and CPS with auto-resize text
            score_text = self.font_large.render(f"{int(self.cookies)} cookies", True, Palette.TEXT)
            self._blit_text_scaled(self.screen, score_text, int(20 * self.W / REF_W), int(20 * self.H / REF_H), ui_scale)
            cps_text = self.font_small.render(f"{self.total_cps():.1f} cookies per second", True, Palette.TEXT_DIM)
            self._blit_text_scaled(self.screen, cps_text, int(20 * self.W / REF_W), int(52 * self.H / REF_H), ui_scale)
            self.draw_store_panel(panel_rect, line_h, start_y_store, toggle_y, ui_scale)
            # Draw reset button
            pygame.draw.rect(self.screen, Palette.ACCENT, reset_rect)
            pygame.draw.rect(self.screen, Palette.BORDER, reset_rect, 2)
            reset_label = self.font_small.render("Reset", True, Palette.TEXT)
            self._blit_text_scaled(self.screen, reset_label, reset_rect.x + reset_rect.width // 2, reset_rect.y + reset_rect.height // 2, ui_scale, center=True)
            # Draw AFK button (NES-style: gold when active)
            afk_col = Palette.GOLD if self.afk_mode else Palette.BACKGROUND_PANEL
            pygame.draw.rect(self.screen, afk_col, afk_rect)
            pygame.draw.rect(self.screen, Palette.BORDER, afk_rect, 3)
            afk_label = self.font_small.render("AFK Mode", True, Palette.TEXT)
            self._blit_text_scaled(self.screen, afk_label, afk_rect.x + afk_rect.width // 2, afk_rect.y + afk_rect.height // 2, ui_scale, center=True)
            # AFK CPS label (show current base CPS and multiplier) - light up green when AFK is active
            afk_info = f"{self.afk_base_cps:.1f} cps {self.afk_multiplier_labels[self.afk_multiplier_index]}"
            afk_text_color = Palette.GREEN if self.afk_mode else Palette.TEXT_DIM
            interval_label = self.font_small.render(afk_info, True, afk_text_color)
            self._blit_text_scaled(self.screen, interval_label, afk_rect.right + int(6 * self.W / REF_W), afk_rect.y + afk_rect.height // 2, ui_scale, center=False)
            # Draw multiplier buttons (dynamic for available labels)
            mul_rects = [afk_mul1_rect, afk_mul2_rect, afk_mul3_rect, afk_mul4_rect, afk_mul5_rect]
            for i, rect in enumerate(mul_rects[:len(self.afk_multiplier_labels)]):
                # if custom is selected, multipliers are not highlighted; if multiplier_index == -1, none highlighted
                col = Palette.GREEN if (not self.afk_custom_selected and self.afk_multiplier_index == i) else Palette.BACKGROUND_PANEL
                pygame.draw.rect(self.screen, col, rect)
                pygame.draw.rect(self.screen, Palette.BORDER, rect, 2)
                lbl = self.font_small.render(self.afk_multiplier_labels[i], True, Palette.TEXT)
                self._blit_text_scaled(self.screen, lbl, rect.x + rect.width // 2, rect.y + rect.height // 2, ui_scale, center=True)
            # Custom AFK button (opens separate dialog). Show current AFK CPS and scale with resolution.
            # Custom AFK button background: green when selected, gray when not
            if self.afk_custom_selected:
                pygame.draw.rect(self.screen, Palette.GREEN, afk_custom_rect)
                pygame.draw.rect(self.screen, Palette.BORDER, afk_custom_rect, 2)
                txt = self.font_small.render(self.afk_custom_text + "_", True, Palette.TEXT)
                # scale text to fit inside the custom rect
                avail_w = max(8, afk_custom_rect.width - 12)
                scale = ui_scale
                if txt.get_width() * ui_scale > avail_w:
                    scale = avail_w / max(1, txt.get_width())
                self._blit_text_scaled(self.screen, txt, afk_custom_rect.x + 6, afk_custom_rect.y + afk_custom_rect.height // 2, scale, center=False)
            elif self.afk_custom_active:
                pygame.draw.rect(self.screen, (30, 30, 30), afk_custom_rect)
                pygame.draw.rect(self.screen, Palette.BORDER, afk_custom_rect, 2)
                txt = self.font_small.render(self.afk_custom_text + "_", True, Palette.TEXT)
                # scale text to fit inside the custom rect
                avail_w = max(8, afk_custom_rect.width - 12)
                scale = ui_scale
                if txt.get_width() * ui_scale > avail_w:
                    scale = avail_w / max(1, txt.get_width())
                self._blit_text_scaled(self.screen, txt, afk_custom_rect.x + 6, afk_custom_rect.y + afk_custom_rect.height // 2, scale, center=False)
            else:
                pygame.draw.rect(self.screen, Palette.BACKGROUND_PANEL, afk_custom_rect)
                pygame.draw.rect(self.screen, Palette.BORDER, afk_custom_rect, 2)
                lab_text = f"AFK {self.afk_base_cps:.1f} cps"
                lab = self.font_small.render(lab_text, True, Palette.TEXT)
                # ensure label fits in the button
                avail_w = max(8, afk_custom_rect.width - 12)
                scale = ui_scale
                if lab.get_width() * ui_scale > avail_w:
                    scale = avail_w / max(1, lab.get_width())
                self._blit_text_scaled(self.screen, lab, afk_custom_rect.x + afk_custom_rect.width // 2, afk_custom_rect.y + afk_custom_rect.height // 2, scale, center=True)
            # Draw AFK mode status
            if self.afk_mode:
                afk_text = self.font_small.render("AFK MODE: ON (press 'A' to toggle)", True, (180,255,180))
                self._blit_text_scaled(self.screen, afk_text, int(self.W/2), int(12 * self.H / REF_H), ui_scale, center=True)
            pygame.display.flip()

        self.save_save()
        pygame.quit()

    def _save_dir(self) -> str:
        """Directory for save file: next to .exe when frozen, else folder of script."""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def save_save(self):
        data = {
            "cookies": self.cookies,
            "cookies_accum": self.cookies_accum,
            "upgrades": [u.to_dict() for u in self.upgrades],
            "total_clicked": self.total_clicked,
            "playtime": self.playtime,
            # Persist AFK settings
            "afk_base_cps": float(self.afk_base_cps),
            "afk_multiplier_index": int(self.afk_multiplier_index),
            "afk_custom_text": str(self.afk_custom_text),
            "afk_mode": bool(self.afk_mode),
        }
        path = os.path.join(self._save_dir(), self.SAVE_PATH)
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_save(self):
        path = os.path.join(self._save_dir(), self.SAVE_PATH)
        if not os.path.isfile(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self.cookies = data.get("cookies", 0)
            self.cookies_accum = data.get("cookies_accum", 0)
            self.playtime = data.get("playtime", 0)
            self.total_clicked = data.get("total_clicked", 0)
            by_name = {u["name"]: u for u in data.get("upgrades", [])}
            for u in self.upgrades:
                if u.name in by_name:
                    u.count = by_name[u.name].get("count", 0)
            # Load AFK settings if present
            try:
                self.afk_base_cps = float(data.get("afk_base_cps", self.afk_base_cps))
            except Exception:
                self.afk_base_cps = max(0.0, getattr(self, "afk_base_cps", 1.0))
            try:
                idx = int(data.get("afk_multiplier_index", self.afk_multiplier_index))
            except Exception:
                idx = self.afk_multiplier_index
            # clamp index to available multipliers
            if idx < 0:
                idx = 0
            if idx >= len(self.afk_multiplier_values):
                idx = len(self.afk_multiplier_values) - 1
            self.afk_multiplier_index = idx
            self.afk_custom_text = str(data.get("afk_custom_text", f"{self.afk_base_cps:.1f}"))
            try:
                self.afk_mode = bool(data.get("afk_mode", self.afk_mode))
            except Exception:
                self.afk_mode = False
        except Exception:
            pass


def main():
    g = Game()
    g.run()


if __name__ == "__main__":
    main()
