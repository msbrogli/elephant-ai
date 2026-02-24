FROM python:3.12-slim
RUN apt-get update && apt-get install -y git curl wget \
    && rm -rf /var/lib/apt/lists/*
RUN wget -qO /usr/local/bin/yq \
    https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
    && chmod +x /usr/local/bin/yq
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src
RUN git config --global user.name "My Little Elephant" \
    && git config --global user.email "elephant@family.local"
CMD ["python", "-m", "elephant.main"]
