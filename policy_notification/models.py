from django.db import models
from core import models as core_models
from core.utils import get_first_or_default_language
from insuree.models import Family
from policy.models import Policy
from enum import IntEnum


class FamilyNotification(core_models.BaseVersionedModel):
    class FamilyComunicationModes(IntEnum):
        ALL = 0
        FULL_COMMUNICATION_ENABLED_CODE = 1
        APPROVAL_NO_PHONE_NUMBER_CODE = 2
        NO_APPROVAL_PHONE_NUMBER_CODE = 3
        NO_APPROVAL_NO_PHONE_NUMBER_CODE = 4

    # id field is required by Django ORM, however not included in legacy version of model
    family = models.OneToOneField(Family, models.CASCADE, db_column='FamilyID',
                                  related_name="family_notification", primary_key=True)
    approval_of_notification = models.BooleanField(db_column='ApprovalOfSMS', default=False, null=False)
    language_of_notification = models.CharField(db_column='LanguageOfSMS', max_length=5,
                                                default=get_first_or_default_language().code, null=False)

    class Meta:
        managed = True
        db_table = 'tblFamilySMS'


class IndicationOfPolicyNotifications(core_models.BaseVersionedModel):
    # id field is required by Django ORM, however not included in legacy version of model
    policy = models.OneToOneField(Policy, models.CASCADE, db_column='PolicyID',
                                  related_name="indication_of_notifications", primary_key=True)

    activation_of_policy = models.DateTimeField(db_column='NotificationOnActivationSent', null=True)
    starting_of_policy = models.DateTimeField(db_column='NotificationOnEffectiveSent', null=True)
    need_for_renewal = models.DateTimeField(db_column='NotificationBeforeExpirySent', null=True)
    expiration_of_policy = models.DateTimeField(db_column='NotificationOnExpirationSent', null=True)
    reminder_after_expiration = models.DateTimeField(db_column='NotificationAfterExpirationSent', null=True)
    renewal_of_policy = models.DateTimeField(db_column='NotificationOnRenewalSent', null=True)
    payment_request_for_policiy_activation = models.DateTimeField(db_column='NotificationOnPaymentRequestSent', null=True)
    payment_request_for_policiy_activation_vulnerable = models.DateTimeField(db_column='NotificationOnPaymentRequestSentVulnerable', null=True)
    payment_request_for_paamg = models.DateTimeField(db_column='NotificationOnPaymentRequestPAAMGSent', null=True)
    payment_of_policy_periodic = models.DateTimeField(db_column='NotificationOnPolicyPeriodicPaymentSent', null=True)
    confirmation_of_policy_periodic_payment = models.DateTimeField(db_column='NotificationOnPolicyPeriodicConfirmationSent', null=True)

    class Meta:
        db_table = 'tblIndicationOfPolicyNotifications'


class IndicationOfPolicyNotificationsDetails(core_models.BaseVersionedModel):
    class SendIndicationStatus(models.IntegerChoices):
        UNDEFINED = 0
        SENT_SUCCESSFULLY = 1
        NOT_SENT_NO_PERMISSION_FOR_NOTIFICATIONS = 2
        NOT_SENT_NOTIFICATION_FOR_OBSOLETE_EVENT = 3
        NOT_SENT_DUE_TO_ERROR = 4
        NOT_PASSED_VALIDATION = 5

    indication_of_notification = models.ForeignKey(
        IndicationOfPolicyNotifications, models.CASCADE, db_column='indicationID', related_name="details"
    )
    notification_type = models.CharField(db_column='notification_type', max_length=255, null=False)
    status = models.SmallIntegerField(
        db_column='Status', null=False, choices=SendIndicationStatus.choices, default=SendIndicationStatus.UNDEFINED
    )
    details = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'tblIndicationOfPolicyNotificationsDetails'

