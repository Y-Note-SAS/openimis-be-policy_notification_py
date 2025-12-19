import logging
from django.utils import translation

from policy_notification.notification_gateways.abstract_sms_gateway import NotificationGatewayAbs, \
    NotificationSendingResult
from policy_notification.notification_templates import DefaultNotificationTemplates
from policy_notification.utils import get_family_member_with_phone
from django.utils.translation import gettext as _


logger = logging.getLogger(__name__)


class PolicyNotificationClient:

    def __init__(self, notification_provider: NotificationGatewayAbs):
        self.provider = notification_provider

    def send_notification_from_template(self, policy, notification_template, template_customs, phone_number = None) \
            -> NotificationSendingResult:
        phone = policy.family.head_insuree.phone if not phone_number else  phone_number
        if not phone:
            family_member_with_phone = get_family_member_with_phone(policy.family)
            if family_member_with_phone:
                phone = family_member_with_phone.phone
            else:
                logger.error(
                    f"Failed to send notification for family with head {policy.family.head_insuree}, "
                    f"insuree doesn't have assigned phone number"
                )
                return NotificationSendingResult(
                    gateway_output=None,
                    success=False,
                    error_message=_("Family without phone number assigned"),
                )

        old_language = translation.get_language()
        try:
            translation.activate(policy.family.family_notification.language_of_notification)
            custom = template_customs
            message = notification_template % custom
            print(f"We send the message: {message} to {phone}")
            return self.provider.send_notification(message, family_number=phone)
        except Exception as e:
            logger.error(f"Failed to send notification for policy {policy}, error: {e}")
            return NotificationSendingResult(gateway_output=None, success=False, error_message=str(e))
        finally:
            translation.activate(old_language)
