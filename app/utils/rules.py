import json
import os

# Construye la ruta absoluta del archivo rulesGPT.json
responses_file_path = os.path.join(os.path.dirname(__file__), 'text', 'rulesGPT.json')

# Lee el archivo
with open(responses_file_path, "r", encoding="utf-8") as f:
    rules = json.load(f)["rules"]  # rules es una lista de cadenas
