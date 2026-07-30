FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations
# Uncomment when deploying with a database
# RUN python manage.py migrate

EXPOSE 8000

# Start server
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "dapp_project.wsgi:application"]
