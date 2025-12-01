# Eclipse Mosquitto MQTT Broker
# Using the official Mosquitto image version 2
FROM eclipse-mosquitto:2

# Labels
LABEL maintainer="AuraTracking Team"
LABEL description="MQTT Broker for AuraTracking telemetry"
LABEL version="1.0"

# Create directories for data and logs
RUN mkdir -p /mosquitto/data /mosquitto/log

# Set permissions
RUN chown -R mosquitto:mosquitto /mosquitto

# Copy configuration file
COPY mosquitto.conf /mosquitto/config/mosquitto.conf

# Expose MQTT ports
# 1883 - Standard MQTT port
# 9001 - MQTT over WebSocket
EXPOSE 1883 9001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD mosquitto_sub -t '$$SYS/#' -C 1 -i healthcheck -W 3 || exit 1

# Run Mosquitto
CMD ["mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
