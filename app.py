import base64
import io
import re
from flask import Flask, request, jsonify
from PIL import Image
import pytesseract

app = Flask(__name__)

# -------------------------------
# OCR + measurement extraction
# -------------------------------
def extract_measurement_text(image):
    text = pytesseract.image_to_string(image)
    return text


def find_measurement_in_text(text):
    # Examples it detects: 4200 mm, 4.2 m, 3,5m, 1200mm, etc.
    pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*(mm|cm|m)")
    matches = pattern.findall(text)

    if not matches:
        return None, None

    value, unit = matches[0]
    value = float(value.replace(",", "."))

    # convert to meters
    if unit == "mm":
        value_m = value / 1000
    elif unit == "cm":
        value_m = value / 100
    else:
        value_m = value

    return value_m, f"{value} {unit}"


def measure_pixel_length(image):
    # Detect the first horizontal non-white line
    img = image.convert("L")
    width, height = img.size
    pixels = img.load()

    row = int(height * 0.5)

    start = None
    end = None

    for x in range(width):
        if pixels[x, row] < 200:  # first dark pixel
            start = x
            break

    if start is None:
        return None

    for x in range(start + 1, width):
        if pixels[x, row] > 230:  # white again → end
            end = x
            break

    if end is None:
        end = width

    return end - start


@app.route("/scale", methods=["POST"])
def scale():
    data = request.json.get("image")
    if not data:
        return jsonify({"error": "Missing image"}), 400

    try:
        img_bytes = base64.b64decode(data)
        img = Image.open(io.BytesIO(img_bytes))
    except:
        return jsonify({"error": "Invalid base64"}), 400

    # ---------------------------
    # 1. Run OCR
    # ---------------------------
    text = extract_measurement_text(img)

    # ---------------------------
    # 2. Extract measurement
    # ---------------------------
    real_m, measurement_text = find_measurement_in_text(text)

    if real_m is None:
        return jsonify({
            "px_per_meter": None,
            "error": "No measurement found"
        }), 200

    # ---------------------------
    # 3. Pixel measurement
    # ---------------------------
    px_len = measure_pixel_length(img)

    if px_len is None:
        return jsonify({
            "px_per_meter": None,
            "error": "No measurable line found"
        }), 200

    # ---------------------------
    # 4. Calculate scale
    # ---------------------------
    px_per_meter = px_len / real_m

    return jsonify({
        "measurement_text": measurement_text,
        "real_meters": real_m,
        "pixel_length": px_len,
        "px_per_meter": px_per_meter
    })
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
