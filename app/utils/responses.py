import json
import os

# Construye la ruta absoluta del archivo responses.json
responses_file_path = os.path.join(os.path.dirname(__file__), 'text', 'responses.json')

# Lee el archivo
with open(responses_file_path, "r", encoding="utf-8") as f:
    responses = json.load(f)
