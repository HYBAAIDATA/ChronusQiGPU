FROM python:3.12-slim
WORKDIR /workspace
COPY . /workspace
RUN pip install --no-cache-dir fastapi uvicorn httpx pytest hypothesis numpy pydantic
CMD ["python", "scripts/execute_sprint_1_to_4_pipeline.py"]
