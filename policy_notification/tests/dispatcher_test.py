import datetime
from datetime import timedelta, date
from unittest.mock import patch, PropertyMock

from django.test import TestCase
from policy.test_helpers import create_test_policy
from insuree.test_helpers import create_test_insuree
from product.test_helpers import create_test_product

from policy.values import policy_values
from policy_notification.apps import PolicyNotificationConfig
from policy_notification.models import IndicationOfPolicyNotifications, IndicationOfPolicyNotificationsDetails
from policy_notification.notification_dispatcher import NotificationDispatcher
from policy_notification.notification_gateways import TextNotificationProvider, NotificationSendingResult
from policy_notification.notification_templates import DefaultNotificationTemplates
from policy_notification.services import *
from policy_notification.notification_triggers.notification_triggers import NotificationTriggerEventDetectors
from contribution_plan.tests.helpers import create_test_contribution_plan
from core.test_helpers import create_test_interactive_user
from core.models import User
from django.core.exceptions import ObjectDoesNotExist


class DispatcherTest(TestCase):
    TEST_PROVIDER = TextNotificationProvider
    TEST_TEMPLATES = DefaultNotificationTemplates
    TEST_TRIGGER_DETECTOR = NotificationTriggerEventDetectors

    def setUp(self):
        super(DispatcherTest, self).setUp()
        self.create_policy()

    def create_policy(self):
        self.test_insuree = create_test_insuree(with_family=True, custom_props={"phone": 123123123})
        self.test_contribution_plan = create_test_contribution_plan()
        try:
            user = User.objects.get(username='Le-positif')
        except ObjectDoesNotExist:
            user = create_test_interactive_user(username='Le-positif', password="positif123")
            
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
        self.test_family = self.test_insuree.family
        self.test_family.family_notification = FamilyNotification(approval_of_notification=True,
                                                                  language_of_notification='fr')
        self.test_family.family_notification.save()
        self.test_family.save()
        self.policy = create_test_policy( 
            product=self.test_product,
            contribution_plan=self.test_contribution_plan,
            insuree=self.test_insuree,
            custom_props={
                "status": 2,
                "validity_from": datetime(2021, 6, 1, 10),
                "effective_date": date(2019, 1, 1),
                "enroll_date": date(2019, 1, 1),
                "start_date": date(2019, 1, 1),
            })

        self.test_custom_props = {
            'InsuranceID': self.test_insuree.chf_id,
            'Name': F"{self.test_insuree.other_names} {self.test_insuree.last_name}",
            'EffectiveDate': self.policy.effective_date,
            'ExpiryDate': self.policy.expiry_date,
            'ProductCode': self.policy.product.code,
            'ProductName': self.policy.product.name,
            'AmountToBePaid': policy_values(self.policy, self.policy.family, self.policy, user)[0].value
        }

    @patch('policy_notification.notification_triggers.NotificationTriggerEventDetectors.find_activated_policies')
    @patch('policy_notification.notification_eligibility_validators.notification_eligibility_validation.datetime')
    def test_send_notification_for_eligible_policies(self, mocked_dt, find_policies):
        mocked_dt.today.return_value = datetime(2021, 5, 30, 12)
        find_policies.return_value = [self.policy.id]
        with patch.object(TextNotificationProvider, 'send_notification',
                          return_value=NotificationSendingResult(success=True)) as mock_sent:
            provider = TextNotificationProvider()

            dispatcher = NotificationDispatcher(provider, self.TEST_TEMPLATES(), self.TEST_TRIGGER_DETECTOR())
            dispatcher.send_notification_new_active_policies()

            expected_msg = self.TEST_TEMPLATES().notification_on_activation % self.test_custom_props
            details_status = self.policy.indication_of_notifications.details \
                .get(notification_type='activation_of_policy').status

            mock_sent.assert_called_once_with(expected_msg, family_number='123123123')
            self.assertIsNotNone(self.policy.indication_of_notifications.activation_of_policy)
            self.assertNotEqual(self.policy.indication_of_notifications.activation_of_policy,
                                PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE)
            self.assertEqual(details_status,
                             IndicationOfPolicyNotificationsDetails.SendIndicationStatus.SENT_SUCCESSFULLY)

    @patch('policy_notification.notification_triggers.NotificationTriggerEventDetectors.find_activated_policies')
    @patch('policy_notification.notification_eligibility_validators.notification_eligibility_validation.datetime')
    def test_not_send_notification_for_non_eligible_policies(self, mocked_dt, find_policies):
        mocked_dt.today.return_value = datetime(2021, 6, 20, 20)
        find_policies.return_value = [self.policy.id]
        with patch.object(TextNotificationProvider, 'send_notification',
                          return_value=NotificationSendingResult(success=True)) as mock_sent:
            provider = TextNotificationProvider()

            dispatcher = NotificationDispatcher(provider, self.TEST_TEMPLATES(), self.TEST_TRIGGER_DETECTOR())
            dispatcher.send_notification_new_active_policies()
            details_status = self.policy.indication_of_notifications.details \
                .get(notification_type='activation_of_policy').status

            mock_sent.assert_not_called()
            self.assertIsNotNone(self.policy.indication_of_notifications.activation_of_policy)
            self.assertEqual(self.policy.indication_of_notifications.activation_of_policy,
                             PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE)
            self.assertEqual(
                details_status,
                IndicationOfPolicyNotificationsDetails.SendIndicationStatus.NOT_SENT_NOTIFICATION_FOR_OBSOLETE_EVENT)

    @patch('policy_notification.notification_triggers.NotificationTriggerEventDetectors.find_activated_policies')
    def test_send_notification_for_eligible_policies_already_sent(self, find_policies):
        self.policy.indication_of_notifications = IndicationOfPolicyNotifications()
        self.policy.indication_of_notifications.activation_of_policy = datetime.now()
        self.policy.effective_date = self.policy.effective_date + timedelta(days=1)
        self.policy.indication_of_notifications.save()
        self.policy.save()

        find_policies.return_value = [self.policy.id]
        with patch.object(TextNotificationProvider, 'send_notification', return_value=None) as mock_sent:
            provider = TextNotificationProvider()

            dispatcher = NotificationDispatcher(provider, self.TEST_TEMPLATES(), self.TEST_TRIGGER_DETECTOR())
            dispatcher.send_notification_new_active_policies()

            self.assertNotEqual(
                self.policy.indication_of_notifications.activation_of_policy,
                PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE
            )
            mock_sent.assert_not_called()

    @patch('policy_notification.notification_triggers.NotificationTriggerEventDetectors.find_activated_policies')
    def test_send_notification_for_eligible_policies_no_approval(self, find_policies):
        self.test_family.family_notification.approval_of_notification = False
        self.test_family.family_notification.save()

        find_policies.return_value = [self.policy.id]
        with patch.object(TextNotificationProvider, 'send_notification',
                          return_value=NotificationSendingResult(success=True)) as mock_sent:
            provider = TextNotificationProvider()

            dispatcher = NotificationDispatcher(provider, self.TEST_TEMPLATES(), self.TEST_TRIGGER_DETECTOR())
            dispatcher.send_notification_new_active_policies()

            self.assertEqual(
                self.policy.indication_of_notifications.activation_of_policy,
                PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE
            )
            self.assertEqual(
                self.policy.indication_of_notifications.details.get(notification_type='activation_of_policy').status,
                IndicationOfPolicyNotificationsDetails.SendIndicationStatus.NOT_SENT_NO_PERMISSION_FOR_NOTIFICATIONS
            )

            self.assertEqual(
                self.policy.indication_of_notifications.details.get(notification_type='activation_of_policy').details,
                "Rejected due to family denied notifications."
            )

            # Resend for same policy after accepting notifications should fails
            self.test_family.family_notification.approval_of_notification = True
            self.test_family.family_notification.save()
            dispatcher.send_notification_new_active_policies()

            self.assertEqual(
                self.policy.indication_of_notifications.activation_of_policy,
                PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE
            )

            mock_sent.assert_not_called()

    @patch('policy_notification.notification_triggers.NotificationTriggerEventDetectors.find_activated_policies')
    @patch('policy_notification.notification_eligibility_validators'
           '.notification_eligibility_validation.datetime')
    def test_send_notification_for_eligible_policies_resend_after_sending_error(self, dt_mock, find_policies):
        dt_mock.today.return_value = datetime(2021, 6, 1, 1)
        self.test_family.family_notification.approval_of_notification = False
        self.test_family.family_notification.save()

        find_policies.return_value = [self.policy.id]
        with patch.object(TextNotificationProvider, 'send_notification',
                          return_value=NotificationSendingResult(success=True)) as mock_sent:
            provider = TextNotificationProvider()
            dispatcher = NotificationDispatcher(provider, self.TEST_TEMPLATES(), self.TEST_TRIGGER_DETECTOR())
            dispatcher.send_notification_new_active_policies()
            # Override status
            details = self.policy.indication_of_notifications.details.get(notification_type='activation_of_policy')
            details.status = IndicationOfPolicyNotificationsDetails.SendIndicationStatus.NOT_SENT_DUE_TO_ERROR
            details.save()

            # Resend after undefined error should succeed
            self.test_family.family_notification.approval_of_notification = True
            self.test_family.family_notification.save()
            dispatcher.send_notification_new_active_policies()

            self.policy.refresh_from_db()
            self.assertNotEqual(
                self.policy.indication_of_notifications.activation_of_policy,
                PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE
            )

            expected_msg = self.TEST_TEMPLATES().notification_on_activation % self.test_custom_props
            mock_sent.assert_called_once_with(expected_msg, family_number='123123123')

    @patch('policy_notification.notification_triggers.NotificationTriggerEventDetectors.find_activated_policies')
    def test_no_active_notification_for_policy_starting_same_day(self, find_policies):
        find_policies.return_value = [self.policy.id]
        self.policy.effective_date = datetime.now()
        self.policy.save()
        with patch('policy_notification.notification_eligibility_validators.'
                   'notification_eligibility_validation.PolicyNotificationConfig.eligible_notification_types',
                   new_callable=PropertyMock, return_value={'starting_of_policy': True}):
            with patch.object(TextNotificationProvider, 'send_notification',
                              return_value=NotificationSendingResult('out', success=True)) as mock_sent:
                provider = TextNotificationProvider()

                dispatcher = NotificationDispatcher(provider, self.TEST_TEMPLATES(), self.TEST_TRIGGER_DETECTOR())
                dispatcher.send_notification_new_active_policies()

                self.assertEqual(
                    self.policy.indication_of_notifications.activation_of_policy,
                    PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE
                )

                self.policy.refresh_from_db()
                detail = self.policy.indication_of_notifications.details.get(notification_type='activation_of_policy')

                self.assertEqual(
                    detail.status, IndicationOfPolicyNotificationsDetails.SendIndicationStatus.NOT_PASSED_VALIDATION
                )
                expected_details = 'Policy is being activated on day of policy start, ' \
                                   'only start of policy notification is sent.'
                self.assertEqual(detail.details, expected_details)
                mock_sent.assert_not_called()
