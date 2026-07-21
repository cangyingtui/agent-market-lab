# Distill Service

Independent HTTP service for the student sentiment-consistency model. Keep this
environment separate from the main backend so `torch` and `transformers` do not
enter the main runtime.

## Run

```powershell
cd D:\agentsim
python -m venv .distill-venv
.\.distill-venv\Scripts\pip.exe install -r distill_service\requirements.txt
$env:DISTILL_MODEL_DIR="D:\agentsim\knowledge_model\sentiment"
$env:DISTILL_MODEL_VERSION="sentiment_student_v1"
.\.distill-venv\Scripts\python.exe -m uvicorn distill_service.app:app --host 127.0.0.1 --port 9000
```

## Endpoints

- `GET /health`
- `GET /v1/model-info`
- `POST /v1/predict`
- `POST /v1/batch-predict`
- `POST /v1/consistency-check`
- `POST /consistency-check` for legacy compatibility

