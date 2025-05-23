from datetime import timedelta
from django.test import TestCase
from policy.test_helpers import create_test_policy
from insuree.test_helpers import create_test_insuree
from policy.models import Policy
from product.test_helpers import create_test_product
from contribution_plan.tests.helpers import create_test_contribution_plan

from policy_notification.services import *
from policy_notification.notification_triggers.notification_triggers import NotificationTriggerEventDetectors


class BaseTriggerTestCase(TestCase):
    TEST_TRIGGER_DETECTOR = NotificationTriggerEventDetectors
    TEST_TRIGGER_DETECTOR.TIME_INTERVAL_HOURS = 1  # interval between task executions is set to 24h
    TEST_TRIGGER_DETECTOR.REMINDER_BEFORE_EXPIRY_DAYS = 5
    TEST_TRIGGER_DETECTOR.REMINDER_AFTER_EXPIRY_DAYS = 5

    def setUp(self):
        super(BaseTriggerTestCase, self).setUp()
        self.create_policy()

    def create_policy(self):
        self.test_insuree = create_test_insuree(with_family=True)
        self.test_product = create_test_product("PROD1111", custom_props={
            "max_members": 5,
            "administration_period": 0,
            "lump_sum": 0,
            "premium_adult": 300,
            "premium_child": 200,
            "registration_lump_sum": 250,
            "general_assembly_lump_sum": 130,
            "insurance_period": 12,
        })
        self.test_contribution_plan = create_test_contribution_plan()
        self.test_family = self.test_insuree.family
        self.policy = create_test_policy(
            product=self.test_product,
            contribution_plan=self.test_contribution_plan,
            insuree=self.test_insuree,
            custom_props={
                "status": 2,
                "validity_from": datetime(2021, 6, 1, 10)
            })
        self.history_policy = None
        self.renewed_policy = None

    def _create_policy_history(self, history_status=1):
        self.policy.validity_from = datetime(2021, 5, 31)
        self.policy.validity_to = datetime(2021, 5, 31)
        self.policy.status = history_status
        self.policy.save()
        histo_id = self.policy.save_history()
        self.history_policy = Policy.objects.get(id=histo_id)

        self.policy.validity_from = datetime(2021, 6, 1, 12)
        self.policy.validity_to = None
        self.policy.status = Policy.STATUS_ACTIVE
        self.policy.save()

    def _create_policy_renewal(self, expiry_date):
        self.renewed_policy = create_test_policy(
            product=self.test_product,
            contribution_plan=self.test_contribution_plan,
            insuree=self.test_insuree,
            custom_props={
                "status": 2,
                "start_date": expiry_date + timedelta(days=1),
                "expiry_date": expiry_date + timedelta(days=365)
            })

        self.renewed_policy.save()
