from datetime import date
from decimal import Decimal
from typing import Union

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, QuerySet, Sum
from django.db.models.functions import Cast
from django.utils import timezone

from dining.models import DiningList
from userdetails.models import Association, User
from .querysets import TransactionQuerySet, DiningTransactionQuerySet, \
    PendingDiningTrackerQuerySet, PendingTransactionQuerySet


class AbstractTransaction(models.Model):
    """Abstract model defining the Transaction models, can retrieve information from all its children."""

    # DO NOT CHANGE THIS ORDER, IT CAN CAUSE PROBLEMS IN THE UNION METHODS AT DATABASE LEVEL!
    source_user = models.ForeignKey(User, related_name="%(class)s_transaction_source",
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    verbose_name="The user giving the money")
    source_association = models.ForeignKey(Association, related_name="%(class)s_transaction_source",
                                           on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           verbose_name="The association giving the money")
    amount = models.DecimalField(verbose_name="Money transferred",
                                 decimal_places=2, max_digits=5,
                                 validators=[MinValueValidator(Decimal('0.01'))])
    target_user = models.ForeignKey(User, related_name="%(class)s_transaction_target",
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    verbose_name="The user receiving the money")
    target_association = models.ForeignKey(Association, related_name="%(class)s_transaction_target",
                                           on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           verbose_name="The association recieving the money")

    order_moment = models.DateTimeField(default=timezone.now)
    confirm_moment = models.DateTimeField(default=timezone.now, blank=True)
    description = models.CharField(default="", blank=True, max_length=50)

    balance_annotation_name = "balance"

    class Meta:
        abstract = True

    def clean(self):
        if self.source_user and self.source_association:
            raise ValidationError("Transaction can not have both a source user and source association.")
        if self.target_user and self.target_association:
            raise ValidationError("Transaction can not have both a target user and target association.")
        if self.source_user and self.source_user == self.target_user:
            raise ValidationError("Source and target user can't be the same.")
        if self.source_association and self.source_association == self.target_association:
            raise ValidationError("Source and target association can't be the same.")

    @classmethod
    def get_children(cls):
        """Returns all child classes that need to be combined."""
        return [FixedTransaction, AbstractPendingTransaction]

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """Gets all credit instances defined in its immediate children and present them as a queryset.

        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        """
        result = None
        # Get all child classes
        children = cls.get_children()

        # Loop over all children, get their respective transaction queries, union the transaction queries
        for child in children:
            if result is None:
                result = child.get_all_transactions(user, association)
            else:
                result = result.union(child.get_all_transactions(user, association))

        return result

    @classmethod
    def get_user_balance(cls, user):
        """Returns the user balance."""
        result = Decimal(0.00)
        children = cls.get_children()

        # Loop over all children and get the credits
        # It is not possible to summarize get_all_credits due to the union method (it blocks it)
        for child in children:
            child_value = child.get_user_balance(user)

            if child_value:
                result += child_value

        return result.quantize(Decimal('.00'))

    @classmethod
    def get_association_balance(cls, association):
        """Returns the association balance."""
        result = Decimal('0.00')
        children = cls.get_children()

        # Loop over all children and get the credits
        # It is not possible to summarize get_all_credits due to the union method (it blocks it)
        for child in children:
            child_value = child.get_association_balance(association)

            if child_value:
                result += child_value

        return result.quantize(Decimal('.00'))

    @classmethod
    def annotate_balance(cls, users=None, associations=None):
        """Returns a list of all users or associations with their respective credits.

        :param users: A list of users to annotate, defaults to users if none is given
        :param associations: a list of associations to annotate
        :return: The list annotated with 'balance'
        """
        if users is not None and associations is not None:
            raise ValueError("Either users or associations need to have a value, not both")

        # Set the query result
        if associations:
            result = associations
            q_type = "associations"
        else:
            # If users is none, the result becomes a list of all users automatically (set in query retrieval)
            result = users
            q_type = "users"

        # Get all child classes
        children = cls.get_children()

        # Loop over all children, get their respective transaction queries, union the transaction queries
        for child in children:
            result = child.annotate_balance(**{q_type: result})

        # Get the annotated name values of its immediate children
        sum_query = None
        for child in children:
            # If sumquery is not yet defined, define it, otherwise add add it to the query
            if sum_query:
                sum_query += F(child.balance_annotation_name)
            else:
                sum_query = F(child.balance_annotation_name)

        sum_query = Cast(sum_query, models.FloatField())

        # annotate the results of the children in a single variable name
        result = result.annotate(**{cls.balance_annotation_name: sum_query})

        return result

    def source(self):
        return self.source_association if self.source_association else self.source_user

    def target(self):
        return self.target_association if self.target_association else self.target_user


class FixedTransaction(AbstractTransaction):
    """Transaction model for immutable final transactions."""

    objects = TransactionQuerySet.as_manager()
    balance_annotation_name = "balance_fixed"

    def save(self, *args, **kwargs):
        if self.id is None:
            self.confirm_moment = timezone.now()
            super(FixedTransaction, self).save(*args, **kwargs)

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """Get all credit instances defined in its immediate children and present them as a queryset.

        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        :return: A queryset of all credit instances
        """
        # Get all objects
        return cls.objects.filter_user(user).filter_association(association)

    @classmethod
    def get_user_balance(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association: Association) -> Decimal:
        """Compute the balance according to this model based on the given association."""
        return cls.objects.compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations=associations, output_name=output_name)
        else:
            return cls.objects.annotate_user_balance(users=users, output_name=output_name)


class AbstractPendingTransaction(AbstractTransaction):
    balance_annotation_name = "balance_pending"

    class Meta:
        abstract = True

    @classmethod
    def get_children(cls):
        return [PendingTransaction, PendingDiningTransaction]

    def finalise(self):
        raise NotImplementedError()

    @classmethod
    def finalise_all_expired(cls):
        """Moves all pending transactions to the fixed transactions table.

        Returns:
            The new entries that were added to the fixed transactions table.
        """
        # Get all child classes
        children = cls.get_children()

        # Loop over all children, finalise them and add all retrieved items to a combined list
        result = []
        for child in children:
            result = result + child.finalise_all_expired()

        return result


class PendingTransaction(AbstractPendingTransaction):
    objects = PendingTransactionQuerySet.as_manager()
    balance_annotation_name = "balance_pending_normal"

    def clean(self):
        """Performs entry checks on model contents."""
        super().clean()

        # Check whether balance does not exceed set limit on balance
        # Checked here as this is primary user interaction. Check in fixed introduces possible problems where old
        # entries are not yet removed resulting in new fixed entries not allowed
        if self.source_user:
            balance = AbstractTransaction.get_user_balance(self.source_user)
            # If the object is being altered instead of created, take difference into account
            if self.pk:
                change = self.amount - self.objects.get(id=self.id).amount
            else:
                change = self.amount
            new_balance = balance - change
            if new_balance < settings.MINIMUM_BALANCE_FOR_USER_TRANSACTION:
                raise ValidationError("Balance becomes too low")

    def finalise(self):
        """Moves the pending transaction over as a fixed transaction."""
        # Create the fixed database entry
        fixed_transaction = FixedTransaction(source_user=self.source_user, source_association=self.source_association,
                                             target_user=self.target_user, target_association=self.target_association,
                                             amount=self.amount,
                                             order_moment=self.order_moment, description=self.description)
        # Move the transaction to the other database
        with transaction.atomic():
            self.delete()
            fixed_transaction.save()

        return fixed_transaction

    def save(self, *args, **kwargs):
        # If no confirm moment is given, set it to the standard
        if not self.confirm_moment:
            self.confirm_moment = self.order_moment + settings.TRANSACTION_PENDING_DURATION

        super(PendingTransaction, self).save(*args, **kwargs)

    @classmethod
    def finalise_all_expired(cls):
        # Get all finalised items
        expired_transactions = cls.objects.get_expired_transactions()
        new_transactions = []
        for transaction_obj in expired_transactions:
            # finalise transaction
            new_transactions.append(transaction_obj.finalise())

        return new_transactions

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """Get all credit instances defined in its immediate children and present them as a queryset.

        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        """
        # Get all objects
        return cls.objects.filter_user(user).filter_association(association)

    @classmethod
    def get_user_balance(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association) -> Decimal:
        """Compute the balance according to this model based on the given association."""
        return cls.objects.compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations=associations, output_name=output_name)
        else:
            return cls.objects.annotate_user_balance(users=users, output_name=output_name)


class PendingDiningTransactionManager(models.Manager):
    # Created specially due to the different behaviour of the model (different database and model use)

    @staticmethod
    def get_queryset(user=None, dining_list=None):
        return DiningTransactionQuerySet.generate_queryset(user=user, dining_list=dining_list)

    @staticmethod
    def annotate_users_balance(users, output_name=None):
        return DiningTransactionQuerySet.annotate_user_balance(users=users, output_name=output_name)

    @staticmethod
    def annotate_association_balance(associations, output_name=None):
        return DiningTransactionQuerySet.annotate_association_balance(associations=associations,
                                                                      output_name=output_name)


class PendingDiningTransaction(AbstractPendingTransaction):
    """Model for the Pending Dining Transactions.

    Does NOT create a table, information is obtained elsewhere as specified in the manager/queryset.
    """
    balance_annotation_name = "balance_pending_dining"
    objects = PendingDiningTransactionManager()

    class Meta:
        managed = False  # There's no actual table in the database

    @classmethod
    def finalise_all_expired(cls):
        # Get all finished dining lists
        results = []
        for dining_list in PendingDiningListTracker.objects.filter_lists_expired():
            results += dining_list.finalise()
        return results

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        if association:
            # Return none, no associations can be involved in dining lists
            return cls.objects.none()
        return cls.objects.get_queryset(user=user)

    @classmethod
    def get_user_balance(cls, user):
        return cls.objects.all().compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association):
        return cls.objects.all().compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations, output_name=cls.balance_annotation_name)
        else:
            return cls.objects.annotate_users_balance(users, output_name=cls.balance_annotation_name)

    @classmethod
    def get_association_credit(cls, association):
        return Decimal('0.00')

    def finalise(self):
        raise NotImplementedError("PendingDiningTransactions are read-only")

    def _get_fixed_form(self):
        return FixedTransaction(source_user=self.source_user, source_association=self.source_association,
                                target_user=self.target_user, target_association=self.target_association,
                                amount=self.amount,
                                order_moment=self.order_moment, description=self.description)


class PendingDiningListTracker(models.Model):
    """Model to track all Dining Lists that are pending.

    Used for creating Pending Dining Transactions.
    """
    dining_list = models.OneToOneField(DiningList, on_delete=models.CASCADE)

    objects = PendingDiningTrackerQuerySet.as_manager()

    def finalise(self):
        # Generate the initial list
        transactions = []

        # Get all corresponding dining transactions
        # loop over all items and make the transactions
        for dining_transaction in PendingDiningTransaction.objects.get_queryset(dining_list=self.dining_list):
            transactions.append(dining_transaction._get_fixed_form())

        # Save the changes
        with transaction.atomic():
            for fixed_transaction in transactions:
                fixed_transaction.save()
            self.delete()

        return transactions

    @classmethod
    def finalise_to_date(cls, d: date):
        """Finalises all pending dining list transactions.

        Args:
            d: The date until which all tracked dining lists need to be finalised.
        """
        query = cls.objects.filter_lists_for_date(d)
        for pending_dining_list_tracker in query:
            pending_dining_list_tracker.finalise()


# User and association views


class UserCredit(models.Model):
    """User credit model, implemented as Database VIEW (see migrations/usercredit_view.py)."""

    user = models.OneToOneField(User, primary_key=True,
                                db_column='id',
                                on_delete=models.DO_NOTHING)
    balance = models.DecimalField(blank=True, null=True,
                                  db_column=AbstractTransaction.balance_annotation_name,
                                  decimal_places=2,
                                  max_digits=6)
    balance_fixed = models.DecimalField(blank=True,
                                        null=True,
                                        db_column=FixedTransaction.balance_annotation_name,
                                        decimal_places=2,
                                        max_digits=6)

    def negative_since(self):
        """Computes the date from the balance_fixed table when the users balance has become negative."""
        balance = self.balance_fixed
        if balance >= 0:
            # balance is already positive, return nothing
            return None

        # Loop over all transactions from new to old, reverse its balance
        transactions = FixedTransaction.get_all_transactions(user=self.user).order_by('-order_moment')
        for fixed_transaction in transactions:
            balance += fixed_transaction.amount
            # If balance is positive now, return the current transaction date
            if balance >= 0:
                return fixed_transaction.order_moment

        # This should not be reached, it would indicate that the starting balance was below 0
        raise RuntimeError("Balance started as negative, negative_since could not be computed")

    @classmethod
    def view(cls):
        """This method returns the SQL string that creates the view."""
        qs = AbstractTransaction.annotate_balance(
            users=User.objects.all()).values('id',
                                             AbstractTransaction.balance_annotation_name,
                                             FixedTransaction.balance_annotation_name)
        return str(qs.query)


class Account(models.Model):
    """Money account which can be used as a transaction source or target."""

    # An account can only have one of user or association
    user = models.OneToOneField(User, on_delete=models.PROTECT, null=True)
    association = models.OneToOneField(Association, on_delete=models.PROTECT, null=True)

    # We can have special accounts which are not linked to a user or association,
    #  e.g. an account where the kitchen payments can be sent to.
    # special = models.CharField(max_length=30, unique=True, blank=True)

    def get_balance(self) -> Decimal:
        tx = Transaction.objects.filter_valid()
        # 2 separate queries for the source and target sums
        # If there are no rows, the value will be 0.00
        source_sum = tx.filter(source=self).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
        target_sum = tx.filter(target=self).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
        return target_sum - source_sum

    def get_entity(self) -> Union[User, Association, None]:
        """Returns the user or association for this account.

        Returns None when this is a special account.
        """
        if self.user:
            return self.user
        if self.association:
            return self.association
        return None

    def __str__(self):
        return str(self.get_entity())


class TransactionQuerySet2(QuerySet):
    def filter_valid(self):
        """Filters transactions that have not been cancelled."""
        return self.filter(cancelled__isnull=True)


class Transaction(models.Model):
    # We do not enforce that source != target because those rows are not harmful,
    #  balance is not affected when source == target.
    source = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transaction_source_set')
    target = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transaction_target_set')
    amount = models.DecimalField(decimal_places=2, max_digits=8, validators=[MinValueValidator(Decimal('0.01'))])
    moment = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=150)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='transaction_set')

    # Implementation note on cancellation: instead of an extra 'cancelled'
    # column we could also write a method that creates a new
    # transaction that reverses this transaction. In that case however it
    # is not possible to check whether a transaction is already cancelled.
    cancelled = models.DateTimeField(null=True)
    cancelled_by = models.ForeignKey(User,
                                     on_delete=models.PROTECT,
                                     null=True,
                                     related_name='transaction_cancelled_set')

    objects = TransactionQuerySet2.as_manager()

    def cancel(self, user: User):
        """Sets the transaction as cancelled.

        Don't forget to save afterwards.
        """
        if self.cancelled:
            raise ValueError("Already cancelled")
        self.cancelled = timezone.now()
        self.cancelled_by = user

    def is_cancelled(self) -> bool:
        return bool(self.cancelled)