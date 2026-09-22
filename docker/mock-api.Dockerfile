FROM python:3.14-slim-bookworm
RUN useradd --create-home --uid 10001 app
COPY docker/mock-api/server.py /app/server.py
COPY data/coffeeshop_daily_sales_report.csv /srv/data/sales.csv
USER app
EXPOSE 8080
ENTRYPOINT ["python", "/app/server.py"]
