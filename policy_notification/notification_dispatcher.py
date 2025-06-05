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
from django.contrib.contenttypes.models import ContentType
from policy.models import Policy
from invoice.models import Invoice
from insuree.models import Insuree
from django.utils import timezone
from datetime import timedelta
import json

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    NOTIFICATION_NOT_IN_INDICATION_TABLE = "Notification of type {notification} doesn't have representation " \
                                           "in IndicationOfPolicyNotifications table."

    def __init__(
        self,
        notification_provider: NotificationGatewayAbs,
        notification_templates_source: DefaultNotificationTemplates = DefaultNotificationTemplates,
        trigger_detector: NotificationTriggerAbs = NotificationTriggerEventDetectors,
        eligibility_validation: Type[PolicyNotificationEligibilityValidation] = PolicyNotificationEligibilityValidation,
        paamg_number = PolicyNotificationConfig.paamg_number
    ):
        self.notification_client = PolicyNotificationClient(notification_provider=notification_provider)
        self.templates = notification_templates_source
        self.trigger_detector = trigger_detector
        self.eligibility_validation = eligibility_validation
        self.paamg_number = paamg_number

    def send_notification_new_active_policies(self):
        policies = self.trigger_detector.find_activated_policies()
        print(f"we are in the send_notification_new_active_policies with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_activation, 'activation_of_policy')

    def send_notification_starting_of_policy(self):
        policies = self.trigger_detector.find_newly_effective_policies()
        print(f"we are in the send_notification_starting_of_policy with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_effective, 'starting_of_policy')

    def send_notification_new_renewed_policies(self):
        policies = self.trigger_detector.find_renewed_policies()
        print(f"we are in the send_notification_new_renewed_policies with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_renewal, 'renewal_of_policy')

    def send_notification_not_renewed_soon_expiring_policies(self):
        policies = self.trigger_detector.find_soon_expiring_policies()
        print(f"we are in the send_notification_not_renewed_soon_expiring_policies with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_before_expiry, 'expiration_of_policy')

    def send_notification_not_renewed_expired_policies(self):
        policies = self.trigger_detector.find_recently_expired_policies()
        print(f"we are in the send_notification_not_renewed_expired_policies with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_after_expiry, 'reminder_after_expiration')

    def send_notification_expiring_today_policies(self):
        policies = self.trigger_detector.find_expiring_today_policies()
        print(f"we are in the send_notification_expiring_today_policies with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_expiration, 'expiration_of_policy')
        
    def send_notification_request_payment_for_policiy_activation(self):
        policies = self.trigger_detector.find_policies_to_pay()
        print(f"we are in the send_notification_request_payment_for_policiy_activation with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_request_payment_for_policiy_activation, 'payment_request_for_policiy_activation')        
        
    def send_notification_new_payment_request_for_paamg(self):
        policies = self.trigger_detector.find_paamg_policies_to_pay()
        print(f"we are in the send_notification_new_payment_request_for_paamg with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_request_payment_for_paamg, 'payment_request_for_paamg')
        
    def send_notification_new_periodic_payment(self):
        policies = self.trigger_detector.find_periodic_payment_policies()
        print(f"we are in the send_notification_new_periodic_payment with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_periodic_payment, 'payment_of_policy_periodic')
        
    def send_notification_new_periodic_payment_confirmation(self):
        policies = self.trigger_detector.find_periodic_payment_confirmed_policies()
        print(f"we are in the send_notification_new_periodic_payment_confirmation with policies {policies}")
        self._send_notification_for_eligible_policies(
            policies, self.templates.notification_on_periodic_payment_confirmation, 'confirmation_of_policy_periodic_payment')

    def _policy_customs(self, policy: Policy, user):
        """
        Build dictionary of parameters which will be used as custom parameters in notification templates.
        :param policy: Policy for which notification will be sent
        :return: Dictionary which keys used in templates
        """
        head = policy.family.head_insuree
        json_ext = policy.contribution_plan.json_ext.get('calculation_rule', {}) if policy.contribution_plan else {}
        has_individual_contributions = any(json_ext.get(key) for key in ['lumpsum', 'childsum', 'adultmalesum', 'adultfemalesum'])
        has_government_contributions = any(json_ext.get(key) for key in ['governmentlumpsum', 'governmentchildsum', 'governmentadultmalesum', 'governmentadultfemalesum'])
        
        # Calcul du montant pour PAAMG
        government_amount = sum(
            float(json_ext.get(key, '0')) for key in [
                'governmentlumpsum', 'governmentchildsum', 'governmentadultmalesum', 'governmentadultfemalesum'
            ]
        )
        
        period = 1  # Par défaut pour solvables
        if has_individual_contributions and has_government_contributions:
            period = 3  # Vulnérables
        elif has_government_contributions and not has_individual_contributions:
            period = 12  # Démunis
            
        customs = {
            'InsuranceID': head.chf_id,
            'Name': F"{head.other_names} {head.last_name}",
            'EffectiveDate': policy.effective_date,
            'ExpiryDate': policy.expiry_date,
            'ProductCode': policy.product.code,
            'ProductName': policy.product.name,
            'AmountToBePaid': policy_values(policy, policy.family, policy, user)[0].value if has_individual_contributions else government_amount,
            'Period': period
        }
        return customs

    def _send_notification_for_eligible_policies(self, policies, notification_template, type_of_notification):
        print("we are in the sent eligible method")
        notification_sent_successfully = []
        seen_policy_ids = set()  # Garder une trace des polices déjà traitées
        for policies_chunk in self.__chunk_list(policies):
            notification_eligible_policies = self._get_eligible_policies(policies_chunk, type_of_notification)
            for policy in notification_eligible_policies:
                if policy.id in seen_policy_ids:
                    logger.warning(f"Policy {policy.id} already processed in this cycle, skipping.")
                    continue
                seen_policy_ids.add(policy.id)
                result = self._send_notification(policy, notification_template, type_of_notification)
                if result:
                    notification_sent_successfully.append(policy)

                indication = self._get_or_create_policy_indication(policy)
                self._update_indication(indication, type_of_notification, result)

        return notification_sent_successfully

    def _send_notification(self, policy, notification_template, type_of_notification, user = None):
        print("we are in the sent notification method")
        custom = self._policy_customs(policy, user)
        family = policy.family
        head_insuree = family.head_insuree
        
        # Récupérer la facture en cours pour l'assuré principal
        if head_insuree:
            insuree_content_type = ContentType.objects.get_for_model(Insuree)
            invoice_filter = {
                'subject_type': insuree_content_type,
                'subject_id': str(head_insuree.id), 
                'is_deleted': False
            }
    
        invoice = Invoice.objects.filter(**invoice_filter).first()
        if invoice:
            custom.update({
                'AmountToBePaid': invoice.amount_total
            })
         
        if type_of_notification == "payment_of_policy_periodic":
            # Vérifier la limite de 4 SMS par mois
            current_month = datetime.now().strftime('%Y-%m')
            sms_count = IndicationOfPolicyNotificationsDetails.objects.filter(
                indication_of_notification__policy=policy,
                notification_type=type_of_notification,
                validity_from__year=datetime.now().year,
                validity_from__month=datetime.now().month,
                status=IndicationOfPolicyNotificationsDetails.SendIndicationStatus.SENT_SUCCESSFULLY
            ).count()
            
            if sms_count >= 4:
                logger.debug(f"Max 4 SMS reached for policy {policy.id} in {current_month}, skipping.")
                return False
        
        # Vérifier si un SMS a déjà été envoyé pour cette facture 
        # if IndicationOfPolicyNotificationsDetails.objects.filter(
        #     indication_of_notification__policy=policy,
        #     notification_type=type_of_notification, 
        #     status=IndicationOfPolicyNotificationsDetails.SendIndicationStatus.SENT_SUCCESSFULLY
        # ).exists():
        #     logger.debug(f"SMS already sent for invoice {invoice.id} of policy {policy.id}, skipping.")
        #     return False 
        
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
        is_sent_successfully = bool(result) is True

        # On utilise result.output seulement si result est un objet et non un booléen
        details = None
        if not is_sent_successfully and result is not None and not isinstance(result, bool):
            details = result.output
        indication_details = IndicationOfPolicyNotificationsDetails(**{
            'indication_of_notification': indication,
            'notification_type': type_of_notification,
            'status':
                IndicationOfPolicyNotificationsDetails.SendIndicationStatus.SENT_SUCCESSFULLY if bool(result) is True
                else IndicationOfPolicyNotificationsDetails.SendIndicationStatus.NOT_SENT_DUE_TO_ERROR,
            # 'details': None if bool(result) or result is None else result.output
            'details': details
        })
        indication_details.save()

    def __chunk_list(self, l, size=1000):
        return (l[index:index + size] for index in range(0, len(l), size))

