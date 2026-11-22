FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md requirements.txt ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps . \
    && rm -rf /app/build /app/src/*.egg-info \
    && groupadd --gid 10001 climate \
    && useradd --uid 10001 --gid climate --no-create-home climate \
    && mkdir -p /storage/data_lake /storage/metadata \
    && chown -R climate:climate /storage
COPY scripts ./scripts
USER 10001:10001
ENV BASE_DIR=/storage DATA_LAKE_DIR=data_lake METADATA_DIR=metadata TEMP_DIR=data_lake/temp
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)"
CMD ["python", "-m", "uvicorn", "climate_platform.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
