FROM python:3.9

# Set working directory
WORKDIR /app

# Install dependencies
RUN pip install pymongo

# Copy initialization script
COPY scripts/init_db.py /app/init_db.py

# Run the database initialization script
CMD ["python", "/app/init_db.py"]