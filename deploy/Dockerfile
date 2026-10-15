FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Empty base URL sends browser requests to the same HTTPS origin.
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY deploy/web.py deploy/start.py ./
COPY --from=frontend /frontend/dist /app/public
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["python", "start.py"]
