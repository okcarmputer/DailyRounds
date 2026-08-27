FROM python:3.12-slim
ENV TZ=America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
COPY sql/ sql/
COPY config/ config/
CMD ["python", "src/main.py"]
