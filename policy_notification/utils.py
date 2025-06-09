import logging

from core.models import Language
from core.utils import get_first_or_default_language
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q

from policy_notification.apps import PolicyNotificationConfig

logger = logging.getLogger(__name__)


def get_default_notification_data():
    return {
        'approvalOfNotification': False,
        'languageOfNotification': get_first_or_default_language().code
    }


def validate_family_notification_data(data):
    approval = data.get('approvalOfNotification', False)
    language_of_notification = data.get('languageOfNotification', 'fr')

    if not isinstance(approval, bool):
        raise ValidationError(F"approvalOfNotification has to be boolean, not {type(approval)}")

    if not Language.objects.filter(code=language_of_notification).exists():
        raise ValidationError(F"Language code {language_of_notification} not listed in available language codes")

    data['approvalOfNotification'] = approval
    data['languageOfNotification'] = language_of_notification
    return data


def get_notification_providers():
    """
    In order for an notification provider to be used for sending notifications, it must meet two conditions:
    - it must be included in the configuration in the providers field,
    - secondly from the notification_gateways submodule there must be imported a class with the same name as the provider
    (the class name is case insensitive) that inherits from NotificationGatewayAbs, and implements the
    send_notification(notification_content, family_number) method.

    :return: list of notification providers eligible for sending notifications
    """
    notification_module = __import__("policy_notification.notification_gateways", fromlist=['*'])
    available_providers = dict(
        [(name.lower(), cls) for name, cls in notification_module.__dict__.items() if isinstance(cls, type)]
    )
    providers_from_config = [v.lower() for v in PolicyNotificationConfig.providers.keys()]
    adaptors = []
    for provider_config in providers_from_config:
        implementation = available_providers.get(provider_config, None)
        if not implementation:
            logger.error(f"Configuration for provider adaptor {provider_config} found, but given adaptor "
                         f"does not have available implementation, allowed implementations are: "
                         f"{available_providers.keys()} (case insensitive)")
        else:
            adaptors.append(implementation)

    return adaptors


def get_family_member_with_phone(family):
    query = family.members.filter((Q(phone__isnull=False) & ~Q(phone='')))
    if query.exists():
        return query.first()
    else:
        return None
    
def get_auxiliary_contributor_with_phone(family):
    """
    Récupère le chef de la famille parente (s'il existe) avec un numéro de téléphone.
    """
    if family.parent and family.parent.head_insuree.phone and family.parent.head_insuree.phone.strip():
        return family.parent.head_insuree 
    return None


def get_notification_indication_filter(notification_type):
    # Confirm that for given policy notification was not sent, or was sent with error
    from policy_notification.models import IndicationOfPolicyNotificationsDetails

    def __notification_not_sent_filter(type_of_notification):
        return Q(**{f"indication_of_notifications__{type_of_notification}__isnull": True})

    def __notification_failed_filter(type_of_notification):
        return Q(**{
            f"indication_of_notifications__{type_of_notification}":
                PolicyNotificationConfig.UNSUCCESSFUL_NOTIFICATION_ATTEMPT_DATE
        }) & Q(**{
            f"indication_of_notifications__details__status":
                IndicationOfPolicyNotificationsDetails.SendIndicationStatus.NOT_SENT_DUE_TO_ERROR,
            f"indication_of_notifications__details__notification_type": type_of_notification
        })

    def __indication_filter(type_of_notification):
        # Confirm that for given policy notification was not sent, or was sent with error
        indication_not_exit = Q(indication_of_notifications__isnull=True)
        indication_not_sent = __notification_not_sent_filter(type_of_notification)
        indication_failed = __notification_failed_filter(type_of_notification)
        return indication_not_exit | indication_not_sent | indication_failed

    return __indication_filter(notification_type)
