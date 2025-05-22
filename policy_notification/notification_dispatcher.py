import logging
from datetime import datetime
from itertools import islice
from typing import Type

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch

from policy.values import policy_values
from .apps import PolicyNotificationConfig
from .models import IndicationOfPolicyNotifications, IndicationOfPolicyNotificationsDetails
from .notification_eligibility_validators import PolicyNotificationEligibilityValidation
from .notification_gateways.abstract_sms_gateway import NotificationGatewayAbs
from .notification_templates import DefaultNotificationTemplates
from policy_notification.notification_triggers import NotificationTriggerEventDetectors
from .notification_triggers import NotificationTriggerAbs
from .notification_client import PolicyNotificationClient
from policy.models import Policy

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    NOTIFICATION_NOT_IN_INDICATION_TABLE = "Notification of type {notification} doesn't have representation " \
                                           "in IndicationOfPolicyNotifications table."

    def __init__(
        self,
        notification_provider: NotificationGatewayAbs,
        notification_templates_source: DefaultNotificationTemplates = DefaultNotificationTemplates,
        trigger_detector: NotificationTriggerAbs = NotificationTriggerEventDetectors,
        eligibility_validation: Type[PolicyNotificationEligibilityValidation] = PolicyNotificationEligibilityValidation
    ):
        self.notification_client = PolicyNotificationClient(notification_provider=notification_provider)
        self.templates = notification_templates_source
        self.trigger_detector = trigger_detector
        self.eligibility_validation = eligibility_validation

    def send_notification_new_active_policies(self):
        policies = self.trigger_detector.find_activated_policies()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_activation, 'activation_of_policy')

    def send_notification_starting_of_policy(self):
        policies = self.trigger_detector.find_newly_effective_policies()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_effective, 'starting_of_policy')

    def send_notification_new_renewed_policies(self):
        policies = self.trigger_detector.find_renewed_policies()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_renewal, 'renewal_of_policy')

    def send_notification_not_renewed_soon_expiring_policies(self):
        policies = self.trigger_detector.find_soon_expiring_policies()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_before_expiry, 'expiration_of_policy')

    def send_notification_not_renewed_expired_policies(self):
        policies = self.trigger_detector.find_recently_expired_policies()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_after_expiry, 'reminder_after_expiration')

    def send_notification_expiring_today_policies(self):
        policies = self.trigger_detector.find_expiring_today_policies()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_expiration, 'expiration_of_policy')
        
    def send_notification_request_payment_for_policiy_activation(self, policy, user):
        self._send_notification(
            policy, self.templates.notification_request_payment_for_policiy_activation, user)
        
        
    def send_notification_new_payment_request_for_paamg(self):
        policies = self.trigger_detector.find_paamg_policies_to_pay()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_request_payment_for_paamg, 'payment_request_for_paamg')
        
    def send_notification_new_periodic_payment(self):
        policies = self.trigger_detector.find_periodic_payment_policies()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_periodic_payment, 'payment_of_policy_periodic')
        
    def send_notification_new_periodic_payment_confirmation(self):
        policies = self.trigger_detector.find_policies_to_pay()
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_periodic_payment_confirmation, 'confirmation_of_policy_periodic_payment')

    def _policy_customs(self, policy: Policy, user):
        """
        Build dictionary of parameters which will be used as custom parameters in notification templates.
        :param policy: Policy for which notification will be sent
        :return: Dictionary which keys used in templates
        """
        head = policy.family.head_insuree
        customs = {
            'InsuranceID': head.chf_id,
            'Name': F"{head.other_names} {head.last_name}",
            'EffectiveDate': policy.effective_date,
            'ExpiryDate': policy.expiry_date,
            'ProductCode': policy.product.code,
            'ProductName': policy.product.name,
            'AmountToBePaid': policy_values(policy, policy.family, policy, user)[0].value
        }
        return customs

    def _send_notification_for_eligible_policies(self, policies, notification_template, type_of_notification):
        notification_sent_successfully = []
        for policies_chunk in self.__chunk_list(policies):
            notification_eligible_policies = self._get_eligible_policies(policies_chunk, type_of_notification)
            for policy in notification_eligible_policies:
                result = self._send_notification(policy, notification_template)
                if result:
                    notification_sent_successfully.append(policy)

                indication = self._get_or_create_policy_indication(policy)
                self._update_indication(indication, type_of_notification, result)

        return notification_sent_successfully

    def _send_notification(self, policy, notification_template, user = None):
        custom = self._policy_customs(policy, user)
        return self.notification_client.send_notification_from_template(policy, notification_template, custom)

    def _get_eligible_policies(self, policies_ids, type_of_notification):
        policies = Policy.objects.filter(id__in=policies_ids)
        validator = self.eligibility_validation(policies, type_of_notification)
        validator.validate_notification_eligibility()
        return validator.valid_collection

    def _get_or_create_policy_indication(self, policy):
        try:
            return policy.indication_of_notifications
        except ObjectDoesNotExist:
            return IndicationOfPolicyNotifications(policy=policy)

    def _update_indication(self, indication, type_of_notification, result):
        if not hasattr(indication, type_of_notification):
            logger.warning(self.NOTIFICATION_NOT_IN_INDICATION_TABLE.format(type_of_notification))
        else:
            if result:
                setattr(indication, type_of_notification, datetime.now())
                indication.save()
            else:
                setattr(indication, type_of_notification,
                        PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE)
                indication.save()
            self._create_indication_details(indication, type_of_notification, result)

    def _create_indication_details(self, indication, type_of_notification, result):
        indication_details = IndicationOfPolicyNotificationsDetails(**{
            'indication_of_notification': indication,
            'notification_type': type_of_notification,
            'status':
                IndicationOfPolicyNotificationsDetails.SendIndicationStatus.SENT_SUCCESSFULLY if bool(result) is True
                else IndicationOfPolicyNotificationsDetails.SendIndicationStatus.NOT_SENT_DUE_TO_ERROR,
            'details': None if bool(result) or result is None else result.output
        })
        indication_details.save()

    def __chunk_list(self, l, size=1000):
        return (l[index:index + size] for index in range(0, len(l), size))

