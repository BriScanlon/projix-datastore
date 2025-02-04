# Use the official MongoDB image
FROM mongo:latest

# Set the MongoDB data directory
VOLUME /data/db

# Expose MongoDB port
EXPOSE 27017

# Command to run MongoDB
CMD ["mongod"]