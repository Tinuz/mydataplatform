"""
Schedules for Investigation Processing

Defines when jobs should automatically run
"""
from dagster import ScheduleDefinition


# Run analytics every day at 6 AM
analytics_schedule = ScheduleDefinition(
    name="daily_investigation_analytics",
    job_name="investigation_analytics_job",
    cron_schedule="0 6 * * *",  # Every day at 6:00 AM
    description="Daily aggregation of investigation data for analytics",
)
