# Jumper Analytics Assignment - Deployment Guide

Complete deployment guide for setting up the PostgreSQL-based engagement analytics system.

## Table of Contents
- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Production Deployment](#production-deployment)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Software Dependencies
- **Docker** (20.10+) & Docker Compose (v2+)
- **Python** 3.11+
- **uv** (Python package manager)
- **PostgreSQL** 15 (containerized via Docker)
- **Nginx** (for production deployment with custom domain)

### System Resources
- **RAM**: Minimum 2GB, Recommended 4GB
- **Disk**: 1GB for database and dependencies
- **CPU**: 2+ cores recommended for concurrent API requests

### Port Requirements
Use `find-port` utility to find available ports if default ports are occupied:
```bash
find-port  # Returns next available port in your range
```

**Default Ports** (adjust based on your environment):
- PostgreSQL: 13177 (mapped from container's 5432)
- FastAPI: 13516
- HTTPS: 443 (via Nginx reverse proxy)

---

## Quick Start

### 1. Clone and Setup

```bash
cd /path/to/jumper-analytics-assignment

# Install Python dependencies using uv
uv sync

# Fix schema permissions (if needed)
chmod 644 schema/schema.sql
```

### 2. Start PostgreSQL Database

```bash
# Start PostgreSQL container (uses docker compose v2)
docker compose up -d

# Verify container is healthy
docker ps | grep engagement

# Check logs for successful schema loading
docker logs engagement_analytics_db

# Verify schema (should show 5 tables)
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "\dt"

# Verify indexes (should show 20 indexes)
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "\di"

# Verify materialized view
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "\dm"
```

### 3. Generate Sample Data

```bash
# Run data generator (creates 50 authors, 10K posts, 50K engagements)
uv run python src/data_generator.py

# Verify data loaded
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "
  SELECT 'authors' as table_name, COUNT(*) FROM authors
  UNION ALL SELECT 'posts', COUNT(*) FROM posts
  UNION ALL SELECT 'engagements', COUNT(*) FROM engagements
  UNION ALL SELECT 'users', COUNT(*) FROM users;
"
```

**Expected Output:**
```
 table_name   | count
--------------+-------
 authors      |    50
 posts        | 10000
 engagements  | 50000
 users        |  5000
```

### 4. Start FastAPI Application

```bash
cd api

# Run with uv (development mode with auto-reload)
uv run uvicorn main:app --host 127.0.0.1 --port 13516 --reload

# Or run in background
uv run uvicorn main:app --host 127.0.0.1 --port 13516 &

# Test API locally
curl http://127.0.0.1:13516/
```

### 5. Test API Endpoints

```bash
# Root endpoint
curl http://127.0.0.1:13516/

# Get engagement for specific post
curl http://127.0.0.1:13516/engagement/1

# Get author trends
curl http://127.0.0.1:13516/author/1/trends

# Get top categories
curl "http://127.0.0.1:13516/categories/top?limit=5"

# API documentation (open in browser)
open http://127.0.0.1:13516/docs
```

---

## Detailed Setup

### Finding Available Ports

The `find-port` utility automatically finds available ports in your user's range:

```bash
# Find two available ports (one for PostgreSQL, one for FastAPI)
POSTGRES_PORT=$(find-port --quiet)
FASTAPI_PORT=$(find-port --quiet)

echo "PostgreSQL: $POSTGRES_PORT"
echo "FastAPI: $FASTAPI_PORT"
```

### Updating Configuration Files

If you need to change ports from the defaults (13177 for PostgreSQL, 13516 for FastAPI):

**1. Update docker-compose.yml:**
```yaml
ports:
  - "127.0.0.1:<YOUR_POSTGRES_PORT>:5432"
```

**2. Update src/data_generator.py:**
```python
def get_db_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        port=<YOUR_POSTGRES_PORT>,  # Change this
        database="engagement_db",
        user="analytics",
        password="analytics_pass"
    )
```

**3. Update src/analyze.py:** (same as above)

**4. Update api/main.py:**
```python
def get_db_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        port=<YOUR_POSTGRES_PORT>,  # Change this
        ...
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=<YOUR_FASTAPI_PORT>)  # Change this
```

### Database Schema Details

The schema includes:

**Tables (5):**
- `authors` - Author information and categories
- `posts` - Blog posts with timestamps and metadata
- `engagements` - User interactions (view, like, comment, share)
- `post_metadata` - Tags and promotional flags
- `users` - User demographic information

**Indexes (20):**
- Composite indexes for common query patterns
- GIN index for array-based tag searches
- Partial index for promoted posts
- Timestamp-based indexes for time-series queries

**Materialized View:**
- `engagement_stats` - Pre-aggregated engagement metrics by post
- Refresh using: `REFRESH MATERIALIZED VIEW engagement_stats;`

---

## Production Deployment

### Setting Up Nginx Reverse Proxy

**1. Create nginx configuration:**

```nginx
# File: /etc/nginx/sites-enabled/jumper-analytics.yourdomain.com

# HTTP to HTTPS redirect
server {
    listen YOUR_SERVER_IP:80;
    server_name jumper-analytics.yourdomain.com;

    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen YOUR_SERVER_IP:443 ssl;
    server_name jumper-analytics.yourdomain.com;

    ssl_certificate /path/to/ssl/certificate.pem;
    ssl_certificate_key /path/to/ssl/private.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Proxy to FastAPI backend
    location / {
        proxy_pass http://127.0.0.1:13516;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for analytics queries
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**2. Test and reload nginx:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Running with PM2 (Production Process Manager)

```bash
# Install PM2 globally (if not already installed)
npm install -g pm2

# Start FastAPI with PM2
cd /path/to/jumper-analytics-assignment/api
pm2 start "uv run uvicorn main:app --host 127.0.0.1 --port 13516" --name jumper-analytics-api

# Save PM2 configuration
pm2 save

# Setup PM2 to start on system boot
pm2 startup

# View logs
pm2 logs jumper-analytics-api

# Monitor
pm2 monit

# Restart
pm2 restart jumper-analytics-api

# Stop
pm2 stop jumper-analytics-api
```

### Environment Variables (Best Practice)

Instead of hardcoding credentials, use environment variables:

**Create .env file:**
```bash
# Database Configuration
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=13177
POSTGRES_DB=engagement_db
POSTGRES_USER=analytics
POSTGRES_PASSWORD=analytics_pass

# API Configuration
API_HOST=127.0.0.1
API_PORT=13516
```

**Update Python files to use python-dotenv:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT')),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )
```

---

## Maintenance

### Viewing Logs

**PostgreSQL logs:**
```bash
docker logs engagement_analytics_db
docker logs engagement_analytics_db --tail 100 --follow
```

**FastAPI logs (if using PM2):**
```bash
pm2 logs jumper-analytics-api
pm2 logs jumper-analytics-api --lines 100
```

**Nginx logs:**
```bash
sudo tail -f /var/log/nginx/access.log | grep jumper-analytics
sudo tail -f /var/log/nginx/error.log
```

### Database Maintenance

**Refresh materialized view:**
```bash
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "REFRESH MATERIALIZED VIEW engagement_stats;"
```

**Vacuum database (reclaim space):**
```bash
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "VACUUM ANALYZE;"
```

**Check database size:**
```bash
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "
  SELECT pg_size_pretty(pg_database_size('engagement_db')) as size;
"
```

**Backup database:**
```bash
docker exec engagement_analytics_db pg_dump -U analytics engagement_db > backup_$(date +%Y%m%d).sql
```

**Restore from backup:**
```bash
cat backup_20251118.sql | docker exec -i engagement_analytics_db psql -U analytics -d engagement_db
```

### Stopping Services

**Stop FastAPI:**
```bash
# If running with PM2
pm2 stop jumper-analytics-api

# If running in foreground: Ctrl+C

# If running in background:
ps aux | grep uvicorn
kill <PID>
```

**Stop PostgreSQL:**
```bash
docker compose down          # Stops container, preserves data
docker compose down -v       # Stops container, DELETES data
```

### Restart Services

**Restart everything:**
```bash
# Restart PostgreSQL
docker compose restart

# Restart FastAPI
pm2 restart jumper-analytics-api

# Reload nginx configuration
sudo nginx -s reload
```

---

## Troubleshooting

### Issue: Container won't start

**Check Docker daemon:**
```bash
sudo systemctl status docker
sudo systemctl start docker
```

**Check for port conflicts:**
```bash
lsof -i :13177  # Check if port is in use
```

**View detailed error:**
```bash
docker compose up  # Run in foreground to see errors
docker logs engagement_analytics_db
```

### Issue: Schema not loading

**Symptom:** Error "Permission denied" when loading schema

**Solution:**
```bash
chmod 644 schema/schema.sql
docker compose down -v
docker compose up -d
```

### Issue: Cannot connect to database

**Check container is running:**
```bash
docker ps | grep engagement
```

**Verify port mapping:**
```bash
docker port engagement_analytics_db
```

**Test connection:**
```bash
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "SELECT 1;"
```

### Issue: API returns 500 errors

**Check database connection from API:**
```bash
# View API logs
pm2 logs jumper-analytics-api

# Or check if uvicorn is showing errors
```

**Verify database credentials match:**
```bash
# Check docker-compose.yml environment variables
# Check Python files have correct host/port
```

### Issue: Slow query performance

**Check indexes are being used:**
```bash
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "
  EXPLAIN ANALYZE SELECT * FROM engagement_stats WHERE category='Tech';
"
```

**Refresh materialized view:**
```bash
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "
  REFRESH MATERIALIZED VIEW engagement_stats;
"
```

**Vacuum and analyze:**
```bash
docker exec engagement_analytics_db psql -U analytics -d engagement_db -c "VACUUM ANALYZE;"
```

### Issue: Running out of disk space

**Check Docker volumes:**
```bash
docker system df
```

**Clean up unused Docker resources:**
```bash
docker system prune  # Remove unused containers/images
docker volume prune  # Remove unused volumes (CAREFUL: data loss)
```

---

## Performance Benchmarks

Based on testing with 30,000 posts and 50,000 engagements:

| Query | Execution Time | Notes |
|-------|---------------|-------|
| `top_authors.sql` | ~45ms | Uses materialized view |
| `engagement_stats` index scan | <2ms | Bitmap index scan |
| API `/engagement/{id}` | ~50-100ms | Including network overhead |
| API `/author/{id}/trends` | ~100-150ms | Complex CTEs |
| API `/categories/top` | ~150-200ms | Aggregation query |

**Expected Performance with Scale:**
- 100K posts: 2-3x slower
- 1M posts: May require query optimization and partitioning
- 10M+ posts: Requires partitioning by date/category

---

## Security Considerations

### Production Checklist

- [ ] Change default PostgreSQL password
- [ ] Use environment variables for credentials
- [ ] Enable SSL/TLS for PostgreSQL connections
- [ ] Restrict CORS origins in FastAPI (change from `allow_origins=["*"]`)
- [ ] Add rate limiting to API endpoints
- [ ] Enable API authentication (JWT/OAuth)
- [ ] Use HTTPS for all external connections
- [ ] Regular security updates for Docker images
- [ ] Backup encryption
- [ ] Network isolation (bind to 127.0.0.1 only)

### Current Security Status

**Good:**
✓ Services bound to localhost (127.0.0.1)
✓ HTTPS enabled via Nginx
✓ PostgreSQL not exposed to public internet
✓ Using official Alpine-based images

**Needs Improvement:**
⚠ Hardcoded credentials in source code
⚠ CORS allows all origins
⚠ No API authentication
⚠ No rate limiting
⚠ No connection pooling (potential DoS risk)

---

## Deployed Instance

This project is deployed at:
- **URL:** https://jumper-analytics.shaily.dev
- **API Documentation:** https://jumper-analytics.shaily.dev/docs
- **PostgreSQL:** localhost:13177 (not publicly accessible)
- **FastAPI:** localhost:13516 (proxied via Nginx)

**Test Endpoints:**
```bash
# Via HTTPS
curl https://jumper-analytics.shaily.dev/
curl https://jumper-analytics.shaily.dev/engagement/1
curl https://jumper-analytics.shaily.dev/author/1/trends
curl "https://jumper-analytics.shaily.dev/categories/top?limit=5"
```

---

## Additional Resources

- **PostgreSQL 15 Documentation:** https://www.postgresql.org/docs/15/
- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **Docker Compose:** https://docs.docker.com/compose/
- **uv Package Manager:** https://github.com/astral-sh/uv
- **PM2 Process Manager:** https://pm2.keymetrics.io/

---

## Support

For issues or questions:
- GitHub: https://github.com/SHAILY24/jumper-analytics-assignment
- Email: shailysharmawork@gmail.com

---

**Last Updated:** November 18, 2025
**Version:** 1.0.0
