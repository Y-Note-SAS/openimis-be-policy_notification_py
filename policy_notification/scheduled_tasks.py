# policy_notification/scheduled_tasks.py
from .tasks import send_notification_messages
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler

def schedule_tasks(scheduler: BackgroundScheduler):
    scheduler.add_job(
        send_notification_messages,
        trigger=CronTrigger(
            day_of_week='*',
            hour='9-20',
            minute='*/5'
        ),
        id="openimis_notification_batch",
        replace_existing=True,
        max_instances=1
    )