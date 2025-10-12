# Dagster gRPC Connection Issues - Resolved

## Problem

Dagster UI sometimes shows this error when clicking "Materialize":

```
dagster._core.errors.DagsterUserCodeUnreachableError: Could not reach user code server. 
gRPC Error code: UNAVAILABLE
```

## Root Causes

1. **Amundsen Sync Sensor Running by Default**
   - The `amundsen_sync_sensor` was set to `RUNNING` by default
   - It tried to connect to Amundsen every 5 minutes
   - When Amundsen wasn't running, connection errors flooded logs
   - These errors could interfere with code location stability

2. **Code Reload Timeouts**
   - Default timeouts were too short for slow imports
   - When Dagster reloaded Python code, the gRPC connection could timeout
   - No explicit timeout configuration in `dagster.yaml`

## Solutions Applied

### 1. Disabled Amundsen Sensor by Default

**File:** `orchestration/weather_pipeline/sensors.py`

Changed:
```python
@sensor(
    name="amundsen_metadata_sync", 
    minimum_interval_seconds=300,
    default_status=DefaultSensorStatus.STOPPED  # ← Changed from RUNNING
)
```

**Why:** The sensor should only run when Amundsen is actually available. Users can manually enable it in the Dagster UI when needed.

### 2. Increased Code Server Timeouts

**File:** `orchestration/dagster_home/dagster.yaml`

Added:
```yaml
# Code server settings - increase timeouts
code_servers:
  local_startup_timeout: 180  # 3 minutes for initial startup
  reload_timeout: 180  # 3 minutes for code reload
  wait_for_local_processes_on_shutdown: true
```

**Why:** Gives Python code more time to load all imports and initialize before timing out.

### 3. Added Location Name

**File:** `orchestration/workspace.yaml`

Added:
```yaml
load_from:
  - python_module:
      module_name: weather_pipeline
      working_directory: /opt/dagster/app
      attribute: defs
      location_name: weather_pipeline_location  # ← Added explicit name
```

**Why:** Makes the code location easier to identify in logs and error messages.

## How to Use

### Normal Operation (Amundsen Disabled)

1. Start Dagster normally:
   ```bash
   docker-compose --profile standard up -d
   ```

2. Use Dagster UI at http://localhost:3000
3. Materialize assets - should work without gRPC errors

### With Amundsen (Optional)

1. Start Amundsen:
   ```bash
   docker-compose --profile amundsen up -d
   ```

2. Enable the sensor in Dagster UI:
   - Go to "Automation" tab
   - Find "amundsen_metadata_sync" sensor
   - Click "Start" to enable it

3. Sensor will sync metadata every 5 minutes

## Testing

After changes, test that materialization works:

```bash
# Check Dagster is running
curl http://localhost:3000/server_info

# Check code location loaded
docker-compose logs dagster --tail 20 | grep "Started Dagster code server"
```

Expected output:
```
Started Dagster code server for module weather_pipeline in process X
Serving dagster-webserver on http://0.0.0.0:3000 in process Y
```

## When to Enable Amundsen Sensor

✅ **Enable when:**
- Amundsen stack is running (`docker-compose --profile amundsen up -d`)
- You want automatic metadata sync to the data catalog
- You're actively using Amundsen for data discovery

❌ **Keep disabled when:**
- Amundsen is not running (prevents connection errors)
- You're just testing pipelines
- You don't need catalog integration yet

## Troubleshooting

If you still see gRPC errors:

1. **Check if Dagster container is running:**
   ```bash
   docker-compose ps dagster
   ```

2. **Check logs for actual errors:**
   ```bash
   docker-compose logs dagster --tail 50
   ```

3. **Restart Dagster:**
   ```bash
   docker-compose restart dagster
   ```

4. **Verify code location loads:**
   ```bash
   docker-compose exec dagster dagster code-location list
   ```

5. **Check if Python imports are slow:**
   ```bash
   docker-compose exec dagster python -c "import weather_pipeline; print('OK')"
   ```

## Summary

**Before:**
- ❌ Amundsen sensor running always → connection errors
- ❌ Short timeouts → gRPC disconnects during reload
- ❌ Unclear error messages

**After:**
- ✅ Amundsen sensor disabled by default
- ✅ 3-minute timeouts for code reload
- ✅ Explicit location name for better debugging
- ✅ Dagster stable without Amundsen running

The gRPC errors should now be resolved! 🎉
