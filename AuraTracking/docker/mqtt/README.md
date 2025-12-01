# AuraTracking - Docker MQTT Broker

## Quick Start

### Build and Run

```bash
# Navigate to the mqtt directory
cd docker/mqtt

# Build and start the container
docker-compose up -d

# Check if running
docker-compose ps

# View logs
docker-compose logs -f mosquitto
```

### Stop

```bash
docker-compose down
```

### Stop and remove volumes (clear all data)

```bash
docker-compose down -v
```

## Configuration

### Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 1883 | MQTT | Standard MQTT connections |
| 9001 | WebSocket | MQTT over WebSocket |

### Topics

The broker is configured to allow all topics under:

```
aura/tracking/#
```

Suggested topic structure:

```
aura/tracking/{equipment_id}/telemetry    - GPS + IMU data
aura/tracking/{equipment_id}/status       - Device status
aura/tracking/{equipment_id}/events       - Events and alerts
```

### Testing Connection

```bash
# Subscribe to all tracking topics
mosquitto_sub -h localhost -p 1883 -t "aura/tracking/#" -v

# Publish a test message
mosquitto_pub -h localhost -p 1883 -t "aura/tracking/test/telemetry" -m '{"lat":0,"lng":0}'
```

## Security Notes

**Current configuration is for development only!**

For production:

1. Disable anonymous access
2. Configure username/password authentication
3. Set up TLS/SSL encryption
4. Configure proper ACL rules
5. Use a reverse proxy if exposing to internet

## Data Persistence

Data is stored in Docker volumes:

- `aura-mosquitto-data` - Message persistence
- `aura-mosquitto-logs` - Log files

To backup data:

```bash
docker run --rm -v aura-mosquitto-data:/data -v $(pwd):/backup alpine tar cvf /backup/mqtt-data-backup.tar /data
```
