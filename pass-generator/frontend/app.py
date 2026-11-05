"""
MandirMitra — Bulk Pilgrim Darshan Pass Generator (Tier 1 Frontend)

Stateless microservice that generates official PDF Darshan Passes and
Pilgrim E-Passes for Shri Mahakaleshwar Jyotirlinga (Ujjain) using ReportLab.
All passes are rendered in-memory via io.BytesIO.
Redis is used as the Tier 2 cache and counter backend.
"""

import csv
import hashlib
import io
import logging
import math
import os
import random
import string
import time

from flask import (
    Flask, request, jsonify, make_response, render_template_string
)
from prometheus_client import (
    Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as pdf_canvas

import redis

# ---------------------------------------------------------------------------
# Configuration (via environment variables)
# ---------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
MAX_BATCH = int(os.getenv("MAX_BATCH", "200"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))

# ---------------------------------------------------------------------------
# Flask app – logging set to CRITICAL to conserve Log Analytics free quota
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.logger.setLevel(logging.CRITICAL)
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)

# ---------------------------------------------------------------------------
# Redis Client (lazy connection with fail-safe error handling)
# ---------------------------------------------------------------------------
pool = redis.ConnectionPool(
    host=REDIS_HOST, port=REDIS_PORT, db=0,
    socket_connect_timeout=2, socket_timeout=2,
    decode_responses=False,
)
rclient = redis.Redis(connection_pool=pool)

# ---------------------------------------------------------------------------
# Prometheus Metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
PASSES_GENERATED = Counter(
    "passes_generated_total",
    "Total number of pilgrim darshan passes generated",
)

# ---------------------------------------------------------------------------
# Devotee Name Pool (for synthetic load generation without external calls)
# ---------------------------------------------------------------------------
DEVOTEE_FIRST = [
    "Aarav", "Aditi", "Ananya", "Arjun", "Bhavya", "Chetan", "Devendra",
    "Divya", "Gaurav", "Gayatri", "Harish", "Hemangi", "Ishaan", "Jaya",
    "Kavita", "Krishna", "Lakshmi", "Madhav", "Meera", "Mohan", "Naman",
    "Nikhil", "Omkar", "Pooja", "Pranav", "Priya", "Rahul", "Rakesh",
    "Rohan", "Sandhya", "Sanjay", "Shivani", "Sneha", "Subhash", "Suresh",
    "Tanvi", "Tarun", "Usha", "Varun", "Vidya", "Vijay", "Yash",
]
DEVOTEE_LAST = [
    "Mourya", "Patel", "Kushwah", "Sharma", "Verma", "Gupta", "Joshi",
    "Tiwari", "Pandey", "Mishra", "Shukla", "Dubey", "Tripathi", "Upadhyay",
    "Chouhan", "Rathore", "Pawar", "Solanki", "Yadav", "Malviya", "Bhatt",
    "Saxena", "Soni", "Agrawal", "Bansal", "Mehta", "Patidar", "Nagar",
]

DARSHAN_TYPES = [
    "Bhasma Aarti Darshan",
    "Sheeghra Darshan (VIP)",
    "General Devotee Darshan",
    "Garbha Griha Jalabhishek",
    "Mahakal Sandhya Aarti",
]

SLOT_TIMES = [
    "04:00 AM - 06:00 AM (Bhasma Aarti)",
    "07:30 AM - 09:30 AM (Morning Slot)",
    "10:30 AM - 01:00 PM (Madhyahna Slot)",
    "04:00 PM - 06:30 PM (Sayankal Slot)",
    "07:30 PM - 09:30 PM (Sandhya Aarti)",
]


def _random_devotee():
    return f"{random.choice(DEVOTEE_FIRST)} {random.choice(DEVOTEE_LAST)}"


# ---------------------------------------------------------------------------
# Redis Helpers (Fail-safe)
# ---------------------------------------------------------------------------
def _redis_ok():
    """Return True if Redis responds to PING."""
    try:
        return bool(rclient.ping())
    except Exception:
        return False


def _cache_get(key: bytes):
    try:
        return rclient.get(key)
    except Exception:
        return None


def _cache_set(key: bytes, value: bytes, ttl: int = CACHE_TTL):
    try:
        rclient.setex(key, ttl, value)
    except Exception:
        pass


def _incr(key: str, amount: int = 1):
    try:
        rclient.incr(key, amount)
    except Exception:
        pass


def _get_int(key: str) -> int:
    try:
        v = rclient.get(key)
        return int(v) if v else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# PDF Generation — Shri Mahakaleshwar Pilgrim Darshan Pass
# ---------------------------------------------------------------------------
# Palette: Sacred Saffron, Maroon, Temple Gold, Deep Charcoal
_COLOR_SAFFRON = HexColor("#E65100")
_COLOR_MAROON = HexColor("#6B1724")
_COLOR_GOLD = HexColor("#D4AF37")
_COLOR_BORDER = HexColor("#4A0E17")
_COLOR_TEXT_DARK = HexColor("#1A202C")
_COLOR_TEXT_MUTED = HexColor("#555555")
_COLOR_BG_TINT = HexColor("#FFF8EE")


def _generate_pass_serial() -> str:
    """Generate unique security verification serial code."""
    ts = hex(int(time.time() * 1000))[2:].upper()
    rnd = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"MK-{ts}-{rnd}"


def _draw_darshan_pass(c, name: str, darshan_type: str, slot: str, date: str, serial: str):
    """
    Draw a single official Darshan Pass page on ReportLab canvas.
    Includes rich vector geometry, sacred concentric patterns, decorative borders,
    and security stamps so that batch generation generates measurable CPU load.
    """
    w, h = A4

    # Background subtle tint
    c.setFillColor(_COLOR_BG_TINT)
    c.rect(1 * cm, 1 * cm, w - 2 * cm, h - 2 * cm, fill=1, stroke=0)

    # --- Outer Border (Double Line) ---
    c.setStrokeColor(_COLOR_BORDER)
    c.setLineWidth(3.5)
    c.rect(1.5 * cm, 1.5 * cm, w - 3 * cm, h - 3 * cm)
    c.setLineWidth(1.2)
    c.rect(1.9 * cm, 1.9 * cm, w - 3.8 * cm, h - 3.8 * cm)

    # --- Inner Decorative Border with Corner Flourishes ---
    c.setStrokeColor(_COLOR_GOLD)
    c.setLineWidth(0.8)
    c.rect(2.4 * cm, 2.4 * cm, w - 4.8 * cm, h - 4.8 * cm)

    # Corner blocks (Temple gold squares with inner diamonds)
    c_size = 9 * mm
    for cx_, cy_ in [
        (2.4 * cm, 2.4 * cm),
        (w - 2.4 * cm - c_size, 2.4 * cm),
        (2.4 * cm, h - 2.4 * cm - c_size),
        (w - 2.4 * cm - c_size, h - 2.4 * cm - c_size),
    ]:
        c.setFillColor(_COLOR_MAROON)
        c.rect(cx_, cy_, c_size, c_size, fill=1, stroke=1)
        c.setFillColor(_COLOR_GOLD)
        c.circle(cx_ + c_size / 2, cy_ + c_size / 2, 2 * mm, fill=1, stroke=0)

    # --- CPU Intensive Geometric Mandala / Watermark Lines ---
    # Concentric patterned radiating rays in center (adds CPU computation)
    mid_x = w / 2
    mid_y = h / 2
    c.setStrokeColor(HexColor("#F5E6CC"))
    c.setLineWidth(0.25)
    for angle_deg in range(0, 360, 6):
        rad = math.radians(angle_deg)
        r_inner = 3.5 * cm
        r_outer = 6.5 * cm
        c.line(
            mid_x + r_inner * math.cos(rad),
            mid_y + r_inner * math.sin(rad),
            mid_x + r_outer * math.cos(rad),
            mid_y + r_outer * math.sin(rad),
        )

    # Horizontal background security lines (40 lines)
    for i in range(40):
        y_pos = 2.8 * cm + i * ((h - 5.6 * cm) / 40)
        c.setStrokeColor(HexColor("#F2DFC2"))
        c.setLineWidth(0.2)
        c.line(2.8 * cm, y_pos, w - 2.8 * cm, y_pos)

    # Top Header Bar
    c.setFillColor(_COLOR_MAROON)
    c.rect(2.4 * cm, h - 5.2 * cm, w - 4.8 * cm, 2.4 * cm, fill=1, stroke=0)

    # Sacred Title
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(mid_x, h - 3.5 * cm, "SHRI MAHAKALESHWAR JYOTIRLINGA TEMPLE")
    c.setFont("Helvetica", 11)
    c.setFillColor(_COLOR_GOLD)
    c.drawCentredString(mid_x, h - 4.2 * cm, "UJJAIN (M.P.) — SHREE MAHAKAL LOK CIRCUIT")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#FFE8CC"))
    c.drawCentredString(mid_x, h - 4.8 * cm, "OFFICIAL PILGRIM DARSHAN E-PASS / PRAVESH PATRA")

    # Divider bar
    c.setStrokeColor(_COLOR_GOLD)
    c.setLineWidth(2)
    c.line(3 * cm, h - 5.6 * cm, w - 3 * cm, h - 5.6 * cm)

    # Pass Subtitle
    c.setFillColor(_COLOR_MAROON)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(mid_x, h - 6.4 * cm, "PILGRIM ACCESS VERIFICATION PASS")

    # Devotee Name Box
    c.setFillColor(HexColor("#FFFFFF"))
    c.setStrokeColor(_COLOR_GOLD)
    c.setLineWidth(1)
    c.roundRect(3.5 * cm, h - 9.8 * cm, w - 7 * cm, 2.6 * cm, 4 * mm, fill=1, stroke=1)

    c.setFillColor(_COLOR_TEXT_MUTED)
    c.setFont("Helvetica", 11)
    c.drawCentredString(mid_x, h - 7.7 * cm, "Devotee / Pilgrim Name")

    c.setFillColor(_COLOR_SAFFRON)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(mid_x, h - 8.8 * cm, name)

    # Details Grid
    start_y = h - 11.2 * cm
    line_spacing = 1.3 * cm

    details = [
        ("Darshan Category :", darshan_type),
        ("Allocated Slot :", slot),
        ("Date of Visit :", date),
        ("Reporting Gate :", "Gate No. 4 (Bhasma Aarti / VIP) | Gate No. 1 (General)"),
        ("Pass Serial No. :", serial),
    ]

    for idx, (label, val) in enumerate(details):
        curr_y = start_y - (idx * line_spacing)

        # Label
        c.setFillColor(_COLOR_TEXT_DARK)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(3.8 * cm, curr_y, label)

        # Value
        c.setFont("Helvetica", 12)
        if "Category" in label:
            c.setFillColor(_COLOR_MAROON)
            c.setFont("Helvetica-Bold", 12)
        elif "Serial" in label:
            c.setFillColor(HexColor("#7B1113"))
            c.setFont("Courier-Bold", 12)
        else:
            c.setFillColor(_COLOR_TEXT_DARK)
        c.drawString(8.2 * cm, curr_y, val)

        # Dotted separator line
        c.setStrokeColor(HexColor("#E0D0B5"))
        c.setLineWidth(0.5)
        c.setDash(2, 2)
        c.line(3.8 * cm, curr_y - 3 * mm, w - 3.8 * cm, curr_y - 3 * mm)
        c.setDash()

    # Guidelines & Protocol Section
    guideline_y = 7.6 * cm
    c.setFillColor(HexColor("#FFF1E0"))
    c.roundRect(3.5 * cm, guideline_y - 2.8 * cm, w - 7 * cm, 2.8 * cm, 3 * mm, fill=1, stroke=0)

    c.setFillColor(_COLOR_MAROON)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(4 * cm, guideline_y - 0.7 * cm, "IMPORTANT PILGRIM GUIDELINES:")

    c.setFillColor(_COLOR_TEXT_DARK)
    c.setFont("Helvetica", 8.5)
    c.drawString(4 * cm, guideline_y - 1.3 * cm, "1. Carry Original Govt Photo ID (Aadhaar / Passport / Voter ID) for physical check.")
    c.drawString(4 * cm, guideline_y - 1.8 * cm, "2. Traditional Dress Code: Unstitched Dhoti-Sola for men, Saree for women in sanctum.")
    c.drawString(4 * cm, guideline_y - 2.3 * cm, "3. Mobile phones, electronic items, and leather goods are strictly prohibited inside.")

    # Security Verification Stamp & Authorized Sign
    sec_y = 3.6 * cm
    c.setStrokeColor(_COLOR_TEXT_DARK)
    c.setLineWidth(0.8)
    c.line(w - 8.5 * cm, sec_y + 0.8 * cm, w - 3.5 * cm, sec_y + 0.8 * cm)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(_COLOR_TEXT_DARK)
    c.drawCentredString(w - 6 * cm, sec_y + 0.3 * cm, "Temple Administrator Seal")
    c.setFont("Helvetica", 8)
    c.setFillColor(_COLOR_TEXT_MUTED)
    c.drawCentredString(w - 6 * cm, sec_y - 0.2 * cm, "Shri Mahakaleshwar Temple Trust")

    # Security Barcode Simulation
    c.setFillColor(_COLOR_TEXT_DARK)
    for b in range(45):
        bx = 3.8 * cm + b * 1.5 * mm
        bw = 0.6 * mm if (b % 3 == 0) else 1.1 * mm
        c.rect(bx, sec_y - 0.2 * cm, bw, 1.1 * cm, fill=1, stroke=0)
    c.setFont("Courier", 7.5)
    c.drawString(3.8 * cm, sec_y - 0.6 * cm, f"DIGITAL SIGNATURE HASH: {hashlib.sha1(serial.encode()).hexdigest()[:24].upper()}")

    # Top & Bottom Decorative Wavy Beads (deliberate math workload for CPU profiling)
    c.setFillColor(_COLOR_GOLD)
    for b in range(70):
        bx = 2.8 * cm + b * ((w - 5.6 * cm) / 70)
        by_top = h - 2.2 * cm + math.sin(b * 0.4) * 2 * mm
        c.circle(bx, by_top, 0.9 * mm, fill=1, stroke=0)

        by_bot = 2.2 * cm + math.cos(b * 0.4) * 2 * mm
        c.circle(bx, by_bot, 0.9 * mm, fill=1, stroke=0)


def _make_single_pass_pdf(name: str, darshan_type: str, slot: str, date: str) -> bytes:
    """Render a single Darshan Pass PDF in-memory and return raw bytes."""
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=A4)
    serial = _generate_pass_serial()
    _draw_darshan_pass(c, name, darshan_type, slot, date, serial)
    c.showPage()
    c.save()
    return buf.getvalue()


def _make_bulk_pass_pdf(names: list[str], darshan_type: str, slot: str, date: str) -> bytes:
    """Render multi-page PDF with one pass per devotee."""
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=A4)
    for name in names:
        serial = _generate_pass_serial()
        _draw_darshan_pass(c, name, darshan_type, slot, date, serial)
        c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# HTML UI Template (Ivory / Saffron / Maroon aesthetic)
# ---------------------------------------------------------------------------
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MandirMitra — Bulk Pilgrim Darshan Pass Generator</title>
    <style>
        :root {
            --saffron: #E65100;
            --maroon: #6B1724;
            --gold: #D4AF37;
            --bg-ivory: #FAF7F2;
            --card-bg: #FFFFFF;
            --text-dark: #2C3E50;
            --border-color: #EADBC8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-ivory);
            color: var(--text-dark);
            line-height: 1.6;
            padding: 20px;
        }
        .header {
            text-align: center;
            background: linear-gradient(135deg, var(--maroon), #4A0E17);
            color: #FFFFFF;
            padding: 30px 20px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(107, 23, 36, 0.25);
            border-bottom: 4px solid var(--gold);
        }
        .header h1 { font-size: 2.2rem; letter-spacing: 1px; margin-bottom: 8px; }
        .header p { color: #FFE8CC; font-size: 1.05rem; }
        .badge {
            display: inline-block;
            background: var(--saffron);
            color: #FFF;
            padding: 4px 12px;
            font-size: 0.8rem;
            border-radius: 20px;
            margin-top: 10px;
            font-weight: bold;
        }
        .container {
            max-width: 1050px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
        }
        @media (max-width: 768px) {
            .container { grid-template-columns: 1fr; }
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        .card h2 {
            color: var(--maroon);
            font-size: 1.35rem;
            margin-bottom: 18px;
            padding-bottom: 10px;
            border-bottom: 2px solid #F5E6CC;
        }
        label {
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
            font-size: 0.9rem;
            color: var(--maroon);
        }
        input, select, textarea {
            width: 100%;
            padding: 10px 12px;
            border: 1.5px solid var(--border-color);
            border-radius: 6px;
            margin-bottom: 16px;
            font-size: 0.95rem;
            background: #FFFAF5;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--saffron);
            background: #FFFFFF;
        }
        .btn {
            background: linear-gradient(135deg, var(--saffron), #BF360C);
            color: #FFFFFF;
            border: none;
            padding: 12px 20px;
            font-size: 1rem;
            font-weight: bold;
            border-radius: 6px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s ease;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(230, 81, 0, 0.3);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            max-width: 1050px;
            margin: 25px auto 0 auto;
        }
        .stat-box {
            background: #FFFFFF;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.6rem;
            font-weight: bold;
            color: var(--maroon);
        }
        .stat-label {
            font-size: 0.8rem;
            color: var(--text-dark);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .footer {
            text-align: center;
            margin-top: 35px;
            font-size: 0.85rem;
            color: #777;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>MandirMitra — Bulk Pilgrim Pass Generator</h1>
        <p>Shri Mahakaleshwar Jyotirlinga &bull; Ujjain Temple Circuit</p>
        <span class="badge">Cloud Computing Lab 2 &bull; 2-Tier Azure AKS Microservice</span>
    </div>

    <div class="container">
        <!-- Single Pass Card -->
        <div class="card">
            <h2>Single Darshan Pass</h2>
            <form action="/generate" method="POST" target="_blank">
                <label for="name">Devotee Full Name</label>
                <input type="text" id="name" name="name" placeholder="e.g. Hemangi Mourya" required>

                <label for="darshan_type">Darshan Category</label>
                <select id="darshan_type" name="darshan_type">
                    <option value="Bhasma Aarti Darshan">Bhasma Aarti Darshan</option>
                    <option value="Sheeghra Darshan (VIP)" selected>Sheeghra Darshan (VIP Pass)</option>
                    <option value="General Devotee Darshan">General Devotee Darshan</option>
                    <option value="Garbha Griha Jalabhishek">Garbha Griha Jalabhishek</option>
                    <option value="Mahakal Sandhya Aarti">Mahakal Sandhya Aarti</option>
                </select>

                <label for="slot">Allocated Slot</label>
                <select id="slot" name="slot">
                    <option value="04:00 AM - 06:00 AM (Bhasma Aarti)">04:00 AM - 06:00 AM (Bhasma Aarti)</option>
                    <option value="07:30 AM - 09:30 AM (Morning Slot)" selected>07:30 AM - 09:30 AM (Morning Slot)</option>
                    <option value="10:30 AM - 01:00 PM (Madhyahna Slot)">10:30 AM - 01:00 PM (Madhyahna Slot)</option>
                    <option value="04:00 PM - 06:30 PM (Sayankal Slot)">04:00 PM - 06:30 PM (Sayankal Slot)</option>
                    <option value="07:30 PM - 09:30 PM (Sandhya Aarti)">07:30 PM - 09:30 PM (Sandhya Aarti)</option>
                </select>

                <label for="date">Date of Visit</label>
                <input type="date" id="date" name="date" value="{{ today }}" required>

                <button type="submit" class="btn">Generate Single PDF Pass</button>
            </form>
        </div>

        <!-- Bulk Pass Card -->
        <div class="card">
            <h2>Bulk Pilgrim Passes (Multi-Page PDF)</h2>
            <form action="/bulk" method="POST" enctype="multipart/form-data" target="_blank">
                <label for="bulk_darshan_type">Darshan Category</label>
                <select id="bulk_darshan_type" name="darshan_type">
                    <option value="Sheeghra Darshan (VIP)" selected>Sheeghra Darshan (VIP Pass)</option>
                    <option value="Bhasma Aarti Darshan">Bhasma Aarti Darshan</option>
                    <option value="General Devotee Darshan">General Devotee Darshan</option>
                </select>

                <label for="bulk_slot">Allocated Slot</label>
                <select id="bulk_slot" name="slot">
                    <option value="07:30 AM - 09:30 AM (Morning Slot)" selected>07:30 AM - 09:30 AM (Morning Slot)</option>
                    <option value="04:00 PM - 06:30 PM (Sayankal Slot)">04:00 PM - 06:30 PM (Sayankal Slot)</option>
                </select>

                <label for="bulk_date">Date of Visit</label>
                <input type="date" id="bulk_date" name="date" value="{{ today }}" required>

                <label for="names_list">Enter Pilgrim Names (one per line, up to {{ max_batch }})</label>
                <textarea id="names_list" name="names_list" rows="3" placeholder="Aarav Sharma&#10;Hemangi Mourya&#10;Naman Patel&#10;Priya Verma"></textarea>

                <label for="csv_file">Or Upload CSV File (first column as name)</label>
                <input type="file" id="csv_file" name="csv_file" accept=".csv">

                <button type="submit" class="btn">Generate Bulk PDF Passes</button>
            </form>
        </div>
    </div>

    <!-- Live Telemetry Stats -->
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-value">{{ passes_generated }}</div>
            <div class="stat-label">Passes Issued</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{{ cache_hits }}</div>
            <div class="stat-label">Redis Cache Hits</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{{ cache_misses }}</div>
            <div class="stat-label">Cache Misses</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" style="color: {{ 'green' if redis_status == 'CONNECTED' else 'red' }};">{{ redis_status }}</div>
            <div class="stat-label">Redis Tier 2</div>
        </div>
    </div>

    <div class="footer">
        <p>MandirMitra &bull; Scalable Microservices Architecture on Microsoft Azure &bull; AKS Horizontal Pod Autoscaling</p>
    </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP Endpoints
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    REQUEST_COUNT.labels("GET", "/", "200").inc()
    today_str = time.strftime("%Y-%m-%d")
    redis_alive = _redis_ok()
    return render_template_string(
        INDEX_HTML,
        today=today_str,
        max_batch=MAX_BATCH,
        passes_generated=_get_int("mandir:passes_generated"),
        cache_hits=_get_int("mandir:cache_hits"),
        cache_misses=_get_int("mandir:cache_misses"),
        redis_status="CONNECTED" if redis_alive else "DISCONNECTED",
    )


@app.route("/generate", methods=["POST"])
def generate():
    t0 = time.time()
    name = request.form.get("name", "").strip() or request.json.get("name", "").strip() if request.is_json else ""
    darshan_type = request.form.get("darshan_type", "Sheeghra Darshan (VIP)")
    slot = request.form.get("slot", "07:30 AM - 09:30 AM (Morning Slot)")
    date = request.form.get("date", time.strftime("%Y-%m-%d"))

    if not name:
        REQUEST_COUNT.labels("POST", "/generate", "400").inc()
        return jsonify({"error": "Devotee name is required"}), 400

    # Redis cache check (SHA-256 key)
    cache_key = f"pass:{hashlib.sha256(f'{name}:{darshan_type}:{slot}:{date}'.encode()).hexdigest()}".encode()
    cached_pdf = _cache_get(cache_key)

    if cached_pdf:
        _incr("mandir:cache_hits")
        pdf_bytes = cached_pdf
        source = "cache"
    else:
        _incr("mandir:cache_misses")
        pdf_bytes = _make_single_pass_pdf(name, darshan_type, slot, date)
        _cache_set(cache_key, pdf_bytes, CACHE_TTL)
        _incr("mandir:passes_generated")
        PASSES_GENERATED.inc()
        source = "generated"

    dur = time.time() - t0
    REQUEST_DURATION.labels("POST", "/generate").observe(dur)
    REQUEST_COUNT.labels("POST", "/generate", "200").inc()

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="Mahakal_Pass_{name.replace(" ", "_")}.pdf"'
    response.headers["X-Pass-Source"] = source
    return response


@app.route("/bulk", methods=["POST"])
def bulk():
    t0 = time.time()
    darshan_type = request.form.get("darshan_type", "Sheeghra Darshan (VIP)")
    slot = request.form.get("slot", "07:30 AM - 09:30 AM (Morning Slot)")
    date = request.form.get("date", time.strftime("%Y-%m-%d"))

    names = []
    # Names from textarea
    names_raw = request.form.get("names_list", "")
    if names_raw.strip():
        names = [line.strip() for line in names_raw.splitlines() if line.strip()]

    # Names from uploaded CSV
    if "csv_file" in request.files:
        f = request.files["csv_file"]
        if f.filename:
            content = f.read().decode("utf-8", errors="ignore")
            reader = csv.reader(content.splitlines())
            for row in reader:
                if row and row[0].strip():
                    names.append(row[0].strip())

    # De-duplicate while preserving order
    unique_names = list(dict.fromkeys(names))[:MAX_BATCH]

    if not unique_names:
        REQUEST_COUNT.labels("POST", "/bulk", "400").inc()
        return jsonify({"error": "No valid devotee names provided"}), 400

    pdf_bytes = _make_bulk_pass_pdf(unique_names, darshan_type, slot, date)
    _incr("mandir:passes_generated", len(unique_names))
    PASSES_GENERATED.inc(len(unique_names))

    dur = time.time() - t0
    REQUEST_DURATION.labels("POST", "/bulk").observe(dur)
    REQUEST_COUNT.labels("POST", "/bulk", "200").inc()

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="Mahakal_Bulk_Passes_{len(unique_names)}.pdf"'
    return response


@app.route("/load", methods=["GET"])
def load_endpoint():
    """
    CPU-Intensive Load Generation Endpoint for HPA Autoscaling.
    Renders n passes with vector geometry and decorative patterns.
    Query parameters:
      - n: number of passes (default 50, capped at MAX_BATCH)
      - unique: 1 for random names (bypasses cache), 0 to allow caching
    """
    t0 = time.time()
    try:
        n = min(int(request.args.get("n", 50)), MAX_BATCH)
    except (ValueError, TypeError):
        n = 50

    unique = request.args.get("unique", "0") == "1"
    today_str = time.strftime("%Y-%m-%d")

    if unique:
        names = [_random_devotee() for _ in range(n)]
    else:
        fixed_devotees = ["Hemangi Mourya", "Naman Patel", "Aarav Sharma", "Priya Verma"]
        names = [fixed_devotees[i % len(fixed_devotees)] for i in range(n)]

    # Generate multi-page PDF in-memory (stresses CPU)
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=A4)
    for name in names:
        serial = _generate_pass_serial()
        darshan = random.choice(DARSHAN_TYPES)
        slot = random.choice(SLOT_TIMES)
        _draw_darshan_pass(c, name, darshan, slot, today_str, serial)
        c.showPage()
    c.save()
    pdf_size = len(buf.getvalue())

    _incr("mandir:passes_generated", n)
    PASSES_GENERATED.inc(n)

    dur = time.time() - t0
    REQUEST_DURATION.labels("GET", "/load").observe(dur)
    REQUEST_COUNT.labels("GET", "/load", "200").inc()

    return jsonify({
        "status": "success",
        "passes_rendered": n,
        "unique_names": unique,
        "pdf_bytes": pdf_size,
        "duration_seconds": round(dur, 4),
        "passes_per_second": round(n / dur, 2) if dur > 0 else 0,
    }), 200


@app.route("/stats", methods=["GET"])
def stats():
    REQUEST_COUNT.labels("GET", "/stats", "200").inc()
    return jsonify({
        "passes_generated": _get_int("mandir:passes_generated"),
        "cache_hits": _get_int("mandir:cache_hits"),
        "cache_misses": _get_int("mandir:cache_misses"),
        "redis_connected": _redis_ok(),
        "max_batch": MAX_BATCH,
        "cache_ttl": CACHE_TTL,
    }), 200


@app.route("/health", methods=["GET"])
def health():
    """Liveness probe: returns 200 OK without external dependencies."""
    REQUEST_COUNT.labels("GET", "/health", "200").inc()
    return "OK", 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness probe: requires Redis to respond to PING."""
    if _redis_ok():
        REQUEST_COUNT.labels("GET", "/ready", "200").inc()
        return "READY", 200
    REQUEST_COUNT.labels("GET", "/ready", "503").inc()
    return "SERVICE UNAVAILABLE: Redis not reachable", 503


@app.route("/metrics", methods=["GET"])
def metrics():
    """Prometheus exposition metrics."""
    return make_response(generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
