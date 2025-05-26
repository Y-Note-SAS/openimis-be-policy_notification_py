from datetime import datetime

from django.apps import AppConfig
import logging

MODULE_NAME = "policy_notification"

DEFAULT_CONFIG = {
    "providers": {
        "eGASMSGateway": {
            "GateUrl": "http://127.0.0.1:8000",
            "SmsResource": "/api/policy_notification/test_sms/",
            "PrivateKey": "",
            "UserId": "",
            "SenderId": "",
            "ServiceId": "",
            "RequestType": "",
            "HeaderKeys": "X-Auth-Request-Hash,X-Auth-Request-Id,X-Auth-Request-Type",
            "HeaderValues": "PrivateKey,UserId,RequestType"
        },
        "TextNotificationProvider": {
            "DestinationFolder": "sent_notification"
        }
    },
    "eligibleNotificationTypes": {
        "activation_of_policy": False,
        "starting_of_policy": False,
        "need_for_renewal": False,
        "expiration_of_policy": False,
        "reminder_after_expiration": False,
        "renewal_of_policy": False,
        "payment_request_for_policiy_activation": False,
        "payment_request_for_paamg": False,
        "payment_of_policy_periodic": False,
        "confirmation_of_policy_periodic_payment": False
    },
    "family_policy_notification_report_perms": ["131224"],
    "trigger_time_interval_hours": 4,
    "trigger_first_call_hour": 8,
    "trigger_last_call_hour": 20,
    "reminder_before_expiry_days": 14,
    "reminder_after_expiry_days": 5,
    "policy_activation_relevance_maximum_days_timedelta": 5,
    "policy_renewal_relevance_maximum_days_timedelta": 5,
    "paamg_number":"2545565588552"
}

logger = logging.getLogger(__name__)


class PolicyNotificationConfig(AppConfig):
    __SCHEDULED_TASK_NAME = 'policy_notification.tasks.send_notification_messages'

    # Used to flag unsuccessful notification attempts in IndicationOfPolicyNotifications
    UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE = datetime.min

    name = MODULE_NAME

    providers = {}
    eligible_notification_types = {}
    family_policy_notification_report_perms = []
    trigger_time_interval_hours = None
    trigger_first_call_hour = None
    trigger_last_call_hour = None
    reminder_before_expiry_days = None
    reminder_after_expiry_days = None
    policy_activation_relevance_maximum_days_timedelta = None
    policy_renewal_relevance_maximum_days_timedelta = None
    paamg_number = None

    def _configure_perms(self, cfg):
        PolicyNotificationConfig.providers = cfg["providers"]
        PolicyNotificationConfig.eligible_notification_types = cfg["eligibleNotificationTypes"]
        PolicyNotificationConfig.family_policy_notification_report_perms = \
            cfg["family_policy_notification_report_perms"]
        self.__load_trigger_scheduled_config(cfg)
        PolicyNotificationConfig.reminder_before_expiry_days = cfg['reminder_before_expiry_days']
        PolicyNotificationConfig.reminder_after_expiry_days = cfg['reminder_after_expiry_days']
        PolicyNotificationConfig.policy_activation_relevance_maximum_days_timedelta =\
            cfg['policy_activation_relevance_maximum_days_timedelta']
        PolicyNotificationConfig.policy_renewal_relevance_maximum_days_timedelta = \
            cfg['policy_renewal_relevance_maximum_days_timedelta']
        PolicyNotificationConfig.paamg_number = cfg["paamg_number"]

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CONFIG)
        self._configure_perms(cfg)

    def __load_trigger_scheduled_config(self, cfg):
        try:
            from openIMIS.settings import SCHEDULER_JOBS
            scheduled_task_config = [d for d in SCHEDULER_JOBS
                                     if d.get('method', None) == self.__SCHEDULED_TASK_NAME]
            if len(scheduled_task_config) >= 1:
                if len(scheduled_task_config) > 1:
                    logger.warning("Multiple tasks execution found using timelines form configuration, "
                                   f"first one ({scheduled_task_config[0]}) is used for trigger configuration")
                self.__assign_trigger_times_from_scheduled_task(scheduled_task_config[0])
            else:
                if len(scheduled_task_config) == 0:
                    logger.warning('policy_notification.tasks.send_notification_messages task is not listed '
                                   'as scheduled task in the settings.py')
                self.__assign_trigger_times_from_config(cfg)
        except Exception as e:
            logger.error(f"exception ocurred during loading trigger execution configuation, error: {e}")
            self.__assign_trigger_times_from_config(cfg)

    def __assign_trigger_times_from_config(self, cfg):
        PolicyNotificationConfig.trigger_time_interval_hours = cfg['trigger_time_interval_hours']
        PolicyNotificationConfig.trigger_first_call_hour = cfg['trigger_first_call_hour']
        PolicyNotificationConfig.trigger_last_call_hour = cfg['trigger_last_call_hour']

    def __assign_trigger_times_from_scheduled_task(self, task_config):
        # execution in hours in instant intervals is expected
        hour = task_config['kwargs']['hour']
        if isinstance(hour, int) or hour.isdigit():
            hour = int(hour)
            PolicyNotificationConfig.trigger_time_interval_hours = 24
            PolicyNotificationConfig.trigger_first_call_hour = hour
            PolicyNotificationConfig.trigger_last_call_hour = hour

        else:
            if ',' in hour:
                # Example: "8,12,16,20", execution with interval of 4 hours between 8 a.m. and 20 p.m.
                hours =[int(x) for x in hour.split(',')]
                PolicyNotificationConfig.trigger_time_interval_hours = hours[0]-hours[1]
                PolicyNotificationConfig.trigger_first_call_hour = hours[0]
                PolicyNotificationConfig.trigger_last_call_hour = hours[-1]
            elif '-' in hour:
                # Example: 8-16, hourly execution between 8 and 16
                hours =[int(x) for x in hour.split('-')]
                PolicyNotificationConfig.trigger_time_interval_hours = 1
                PolicyNotificationConfig.trigger_first_call_hour = hours[0]
                PolicyNotificationConfig.trigger_last_call_hour = hours[1]
            else:
                raise NotImplementedError(f"Evaluating for crone execution with hour value {hour} not implemented")