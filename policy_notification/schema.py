import logging

import graphene
from core.schema import signal_mutation_module_after_mutating
from insuree.models import Family, Insuree
from insuree.signals import signal_before_family_query
from graphene_django.filter import DjangoFilterConnectionField
from django.db.models import Q

from policy_notification.gql_queries import FamilyNotificationGQLType
from policy_notification.services import update_family_notification_policy, create_family_notification_policy, delete_family_notification_policy
from policy_notification.filters import communication_approval_filter
logger = logging.getLogger(__name__)


class Query(graphene.ObjectType):
    family_notification = DjangoFilterConnectionField(FamilyNotificationGQLType)


def on_family_create_mutation(mutation_args):
    head_of_family_chf = mutation_args['data'].get('head_insuree', {}).get('chf_id', None)
    try:
        head_of_family = Insuree.objects.get(chf_id=head_of_family_chf)
        family_uuid = Family.objects.get(head_insuree=head_of_family, validity_to__isnull=True).uuid
        if not family_uuid:
            return []
        family_notification_policy = mutation_args['data'].get('contribution', {}).get('PolicyNotification', {})
        create_family_notification_policy(family_uuid, family_notification_policy)
        
    except (Family.DoesNotExist, Insuree.DoesNotExist) as e:
        logger.warning(F"Family with head insuree with chf {head_of_family_chf} not found, FamilyNotification was not created")
    except Exception as e:
        import traceback
        logger.error("Error ocurred during creating new familySMS, traceback: ")
        traceback.print_exc()
    return []


def on_family_update_mutation(mutation_args):
    family_uuid = mutation_args['data'].get('uuid', None)
    family_notification_policy_update = mutation_args['data'].get('contribution', {}).get('PolicyNotification', {})

    if not family_uuid:
        return []

    if not family_notification_policy_update:
        logger.warning(F"FamilyNotification is being updated but contribution.policySms is empty, "
                       F"content of contribution field:\n {mutation_args['data'].get('contribution', {})}.")
        return []

    update_family_notification_policy(family_uuid, family_notification_policy_update)


def on_families_delete_mutation(mutation_args):
    family_uuids = mutation_args['data'].get('uuids', None)

    if not family_uuids:
        return []

    delete_family_notification_policy(family_uuids)


def after_family_mutation(sender, **kwargs):
    return {
        "CreateFamilyMutation": lambda x: on_family_create_mutation(x),
        "UpdateFamilyMutation": lambda x: on_family_update_mutation(x),
        "DeleteFamiliesMutation": lambda x: on_families_delete_mutation(x),
    }.get(sender._mutation_class, lambda x: [])(kwargs)


def on_family_query_filter(sender, **kwargs):
    # OFS-257: Create dynamic filters for the payment mutation
    user = kwargs.get("user", None)
    policy_notification_filters = kwargs.get('additional_filter', {}).get('policyNotification', {})
    if policy_notification_filters:
        mode = policy_notification_filters.get('mode', {})
        if not mode:
            logger.warning("policyNotification additional filter created but notification enabled filter not provided.")

        mode = mode.get('value', 0)
        return communication_approval_filter(mode)
    return Q()


def bind_signals():
    signal_mutation_module_after_mutating["insuree"].connect(after_family_mutation)
    signal_before_family_query.connect(on_family_query_filter)
