# Streamlit app over the saved outputs. Build from the repository root after running `python run_all.py --from-final`:
#   docker build -t air-quality-app .
#   docker run -p 8501:8501 air-quality-app
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY outputs/tables/ outputs/tables/
COPY outputs/figures/ outputs/figures/

EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
