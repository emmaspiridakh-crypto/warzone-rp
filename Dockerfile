FROM python:3.11-slim

WORKDIR /app

# Εγκατάσταση dependencies πρώτα (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Αντιγραφή όλου του κώδικα
COPY . .

# Fake port για Render / UptimeRobot (βλ. keep_alive.py)
EXPOSE 1000

CMD ["python", "main.py"]
