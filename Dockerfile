FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    PORT=8501

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN pip install --upgrade pip && \
    pip install \
        "pandas>=2.2.3" \
        "pandera>=0.31.1" \
        "streamlit>=1.44.0" \
        "watchdog>=6.0.0" \
        "z3-solver>=4.13.0"

COPY . .

EXPOSE 8501

CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0"]
