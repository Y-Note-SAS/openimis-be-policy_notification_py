import logging
from datetime import datetime

from core.schema import signal_mutation_module_after_mutating, signal_mutation_module_validate
from core.models import Language
from django.core.exceptions import ValidationError
from typing import List

from policy_notification.models import FamilyNotification
from insuree.models import Family
from .utils import get_notification_providers
from .apps import PolicyNotificationConfig
from .notification_dispatcher import NotificationDispatcher
from .notification_templates import DefaultNotificationTemplates
from policy_notification.notification_triggers.notification_triggers import NotificationTriggerEventDetectors

from policy_notification.utils import validate_family_notification_data, get_default_notification_data
logger = logging.getLogger(__name__)


def create_family_notification_policy(family_uuid: str, family_notification_data=None) -> FamilyNotification:
    """
    Create new familySMS for given family.
    :param family_uuid: UUID of family for which FamilyNotification will be created
    :param family_notification_data: dictionary with two optional keys:
        * 'approvalOfNotification' - boolean informing whether family is accepting SMS messages,
        * 'languageOfNotification' - language code for language in which family will receive messages.
        If parameter is empty, default values are used. False for approval and code for first language
        from sorted core.models.Language.
    :return: newly created FamilyNotification object
    :raises ValidationError: if given language code is not specified in tblLanguages or approvalOfNotification is not boolean.
    """
    if family_notification_data is None:
        family_notification_data = get_default_notification_data()

    validate_family_notification_data(family_notification_data)
    family = Family.objects.get(uuid=family_uuid)

    if FamilyNotification.objects.filter(family=family, validity_to__isnull=True).exists():
        raise ValidationError(F"FamilyNotification for family {family_uuid} already exists")

    family_notification = FamilyNotification(family=family,
                                             approval_of_notification=family_notification_data.get('approvalOfNotification'),
                                             language_of_notification=family_notification_data.get('languageOfNotification')
                                             )
    family_notification.save()
    return family_notification


def update_family_notification_policy(family_uuid: str, updated_family_notification_fields: dict = None) -> FamilyNotification:
    """
    Update familySMS for given family.
    :param family_uuid: UUID of family for which FamilyNotification will be created
    :param updated_family_notification_fields: dictionary with two optional keys:
        * 'approvalOfNotification' - boolean informing whether family is accepting SMS messages,
        * 'languageOfNotification' - language code for language in which family will receive messages.
    :return: updated FamilyNotification object
    :raises ValidationError: if given language code is not specified in tblLanguages.
    """
    if not updated_family_notification_fields:
        return None

    family = Family.objects.get(uuid=family_uuid)
    current_family_notification = FamilyNotification.objects.filter(family__uuid=family.uuid, validity_to__isnull=True).first()

    if current_family_notification is None:
        logger.warning(F"Update FamilyNotification for family {family} has failed, family doesn't have sms policy assigned, "
                       "default one is being created.")
        # create default family SMS policy
        current_family_notification = create_family_notification_policy(family_uuid)

    updated_approval = updated_family_notification_fields.get('approvalOfNotification', None)
    updated_language = updated_family_notification_fields.get('languageOfNotification', None)

    if updated_approval is not None:
        current_family_notification.approval_of_notification = updated_approval
    if updated_language is not None:
        if not Language.objects.filter(code=updated_language).exists():
            raise ValidationError(F"Language code {updated_language} not listed in available language codes")
        else:
            current_family_notification.language_of_notification = updated_language

    current_family_notification.save()
    return current_family_notification


def delete_family_notification_policy(family_uuids: List[str]) -> List[FamilyNotification]:
    """
    Delete FamilyNotification for given families. FamilyNotification is in 1:1 relation with Family, therefore if it's deleted from
    active family, status is reset to default one and not removed completely. If family is deactivated
    (has ValidityTo != null), then validityTo is also set for FamilyNotification.
    :param family_uuids: UUIDs of families for which FamilyNotification will be deleted
    :return: list of deleted families
    """
    families = Family.objects.filter(uuid__in=family_uuids)
    ids = [x.id for x in families]
    families_sms = FamilyNotification.objects.filter(family__id__in=ids)

    deleted = []
    for sms in families_sms:
        if sms.family.validity_to is None:
            default = get_default_notification_data()
            sms.approval_of_notification = default['approvalOfNotification']
            sms.language = default['languageOfNotification']
        else:
            sms.validity_to = datetime.now()
        sms.save()
        deleted.append(sms)
    return deleted

class Sms_Send_Service:
    
    def __init__(self, user):
        self._user = user
        
        
    def sms_payment_request_for_policiy_activation(policy, user):
        try:
            notification_providers = get_notification_providers()
            logger.info(F"send_notification_messages called at {datetime.now()}")
            eligible_notification_types = PolicyNotificationConfig.eligible_notification_types

            event_detector = NotificationTriggerEventDetectors()
            # Ensure time intervals are loaded properly
            event_detector.assign_default_intervals()

            for provider in notification_providers:
                # All gateways are used to inform insurees
                dispatcher = NotificationDispatcher(
                    notification_provider=provider(),
                    notification_templates_source=DefaultNotificationTemplates(),
                    trigger_detector=event_detector,
                )
                if eligible_notification_types.get('payment_request_for_policiy_activation', False):
                    dispatcher.send_notification_request_payment_for_policiy_activation(policy, user)
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(F"Failed to execute notification sending, error: {traceback.format_exc()}")
    
