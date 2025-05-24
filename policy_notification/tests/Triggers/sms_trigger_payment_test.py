from datetime import date
from unittest.mock import patch

from policy_notification.services import *
from policy_notification.notification_triggers.notification_triggers import NotificationTriggerEventDetectors
from policy_notification.tests.Triggers.base_trigger_test_class import BaseTriggerTestCase
from datetime import datetime, timedelta
from policy.models import Policy


class TestPaymentPolicyTrigger(BaseTriggerTestCase):

    @patch('policy_notification.notification_triggers.notification_triggers.datetime')
    def test_all_new_policies_needing_payment_no_notification(self, mocked_dt):
        now = datetime(2025, 5, 23, 12, 0)
        mocked_dt.now.return_value = now
        self.policy.status = Policy.STATUS_IDLE
        self.policy.validity_from = now - timedelta(minutes=2)
        self.policy.validity_to = None
        self.policy.save()
        policy_ids = NotificationTriggerEventDetectors.all_new_policies_needing_payment()
        self.assertEqual(len(policy_ids), 1)
        self.assertEqual(policy_ids[0], self.policy.id)


    @patch('policy_notification.notification_triggers.notification_triggers.datetime')
    def test_find_policies_to_pay_already_called(self, mocked_dt):
        now = datetime(2025, 5, 23, 12, 0)
        mocked_dt.now.return_value = now
        mocked_dt.today.return_value = now.date()
        self.policy.status = Policy.STATUS_IDLE
        self.policy.validity_from = now - timedelta(minutes=2)
        self.policy.validity_to = None
        self.policy.save()
        NotificationTriggerEventDetectors.TIME_INTERVAL_HOURS = 0.05
        mocked_dt.now.return_value = now + timedelta(minutes=1)  # Second appel dans la même journée
        policy_ids = NotificationTriggerEventDetectors.find_policies_to_pay()
        self.assertEqual(len(policy_ids), 0)
