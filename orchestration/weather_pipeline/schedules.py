"""
Schedules for the weather data pipeline
"""

from dagster import (
    ScheduleDefinition,
    DefaultScheduleStatus,
    AssetSelection,
)


# Run weather pipeline every hour
weather_hourly_schedule = ScheduleDefinition(
    name="weather_hourly",
    target=AssetSelection.all(),
    cron_schedule="0 * * * *",  # Every hour at minute 0
    default_status=DefaultScheduleStatus.STOPPED,  # Start manually for demo
    description="Fetch weather data every hour from Open-Meteo API"
)
