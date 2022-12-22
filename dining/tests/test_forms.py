from datetime import timedelta, datetime, time
from decimal import Decimal

from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django.conf import settings
from django.forms import ModelForm
from django.http import HttpRequest
from django.test import TestCase
from django.utils import timezone

from creditmanagement.models import Account, Transaction
from dining.forms import CreateSlotForm, DiningEntryUserCreateForm, DiningEntryExternalCreateForm, \
    DiningEntryDeleteForm, DiningInfoForm, DiningPaymentForm, DiningCommentForm, SendReminderForm, DiningListDeleteForm
from dining.models import DiningList, DiningEntryUser, DiningEntryExternal, DiningEntry, DiningComment
from general.forms import ConcurrenflictFormMixin
from userdetails.models import Association, User, UserMembership
from utils.testing import TestPatchMixin, patch, FormValidityMixin
from utils.testing.patch_utils import patch_time


class CreateSlotFormTestCase(TestCase):
    def setUp(self):
        self.association1 = Association.objects.create(name="Quadrivium")
        self.user1 = User.objects.create_user('jan')
        UserMembership.objects.create(related_user=self.user1, association=self.association1, is_verified=True,
                                      verified_on=timezone.now())
        # Date two days in the future
        self.dining_date = timezone.now().date() + timedelta(days=2)
        self.form_data = {'dish': 'Kwark', 'association': str(self.association1.pk), 'max_diners': '18',
                          'serve_time': '17:00'}
        self.dining_list = DiningList(date=self.dining_date)
        self.form = CreateSlotForm(self.user1, self.form_data, instance=self.dining_list)

    def test_creation(self):
        self.assertTrue(self.form.is_valid())
        dining_list = self.form.save()
        dining_list.refresh_from_db()

        # Assert
        self.assertEqual('Kwark', dining_list.dish)
        self.assertEqual(self.association1, dining_list.association)
        self.assertEqual(18, dining_list.max_diners)
        self.assertEqual(time(17, 00), dining_list.serve_time)
        self.assertEqual(self.dining_date, dining_list.date)

    def test_invalid_association(self):
        """Tests using an association which the user is not a member of.

        NOTE: when there is 1 available association, the form sets the association field to disabled. This means that
        the value that is sent with the form is totally ignored in favor of the initial value of the field. Therefore
        setting a different invalid association in the form data results in the form data actually being valid, but it
        does not use this association, instead it uses the other association which the user is actually a member of.

        Source: https://docs.djangoproject.com/en/2.2/ref/forms/fields/#disabled
        """
        association = Association.objects.create(name='Knights')
        form_data = {'dish': 'Boter', 'association': str(association.pk), 'max_diners': '20',
                     'serve_time': '18:00'}
        form = CreateSlotForm(self.user1, form_data, instance=DiningList(date=self.dining_date))
        self.assertTrue(form.is_valid())
        # Check that the actual association is not Knights but Quadrivium
        self.assertEqual(self.association1, form.instance.association)

    def test_association_unique_for_date(self):
        """Tests that there can be only one dining slot for an association for each date."""
        # Save one dining list
        self.form.save()

        # Try creating another one with same association
        dl = DiningList(date=self.dining_date)
        data = {'dish': 'Kwark', 'association': str(self.association1.pk), 'max_diners': '18',
                'serve_time': '17:00'}
        form = CreateSlotForm(self.user1, data, instance=dl)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('association'))

    def test_insufficient_balance(self):
        Transaction.objects.create(source=self.user1.account,
                                   target=self.association1.account,
                                   amount=Decimal('99'),
                                   created_by=self.user1)
        self.assertFalse(self.form.is_valid())

    def test_insufficient_balance_exception(self):
        Transaction.objects.create(source=self.user1.account,
                                   target=self.association1.account,
                                   amount=Decimal('99'),
                                   created_by=self.user1)
        # Make user member of another association that has the exception
        association = Association.objects.create(name='Q', has_min_exception=True)
        UserMembership.objects.create(related_user=self.user1, association=association, is_verified=True,
                                      verified_on=timezone.now())
        self.assertTrue(self.form.is_valid())

    def test_serve_time_too_late(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '23:30'
        self.assertFalse(self.form.is_valid())

    def test_serve_time_too_early(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '11:00'
        self.assertFalse(self.form.is_valid())


class TestDiningEntryUserCreateForm(FormValidityMixin, TestCase):
    fixtures = ['base', 'base_credits', 'dining_lists']
    form_class = DiningEntryUserCreateForm

    def setUp(self):
        self.dining_list = DiningList.objects.get(id=3)
        self.user = User.objects.get(id=2)

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('dining_list', self.dining_list)
        kwargs.setdefault('created_by', self.user)
        return super(TestDiningEntryUserCreateForm, self).get_form_kwargs(**kwargs)

    def test_widget_replacements(self):
        form = self.build_form({})
        self.assertIsInstance(form.fields['user'].widget, ModelSelect2)

    @patch_time()
    def test_form_valid(self):
        """Asserts that the testing environment standard is valid."""
        # Check for self creation, useful to guarantee a baseline of current testing environment
        self.assert_form_valid({'user': self.user})

    @patch_time()
    def test_entry_db_creation(self):
        """Tests the database object creation for an entry."""
        form = self.assert_form_valid({'user': User.objects.get(id=4)})
        instance = form.save()

        self.assertTrue(DiningEntryUser.objects.filter(id=instance.id).exists())
        instance.refresh_from_db()
        self.assertEqual(instance.user, User.objects.get(id=4))
        self.assertEqual(instance.created_by, self.user)

    @patch_time()
    def test_transation_db_creation(self):
        """Asserts that the correct transaction is created."""
        # Adjust kitchen cost so we can test it takes that value
        self.dining_list.kitchen_cost = 0.42
        self.dining_list.save()

        added_user = User.objects.get(id=4)

        # Save the instance
        form = self.assert_form_valid({'user': added_user})
        instance = form.save()

        self.assertIsNotNone(instance.transaction)
        self.assertEqual(instance.transaction.amount, self.dining_list.kitchen_cost)
        self.assertEqual(instance.transaction.source, added_user.account)
        self.assertEqual(instance.transaction.target, Account.objects.get(special='kitchen_cost'))
        self.assertEqual(instance.created_by, self.user)

    @patch_time()
    def test_prevent_doubles(self):
        DiningEntryUser.objects.create(
            dining_list=self.dining_list,
            user=self.user,
            created_by=self.user
        )
        self.assert_form_has_error({'user': self.user}, code='user_already_present')

    @patch_time(dt=datetime(2022, 4, 26, 18, 0))
    def test_sign_up_deadline(self):
        """Asserts that the form can not be used after the timelimit."""
        # Verify testcase data
        self.assertNotIn(self.user, self.dining_list.owners.all(), "Incorrect test data, user should not be owner")
        self.assert_form_has_error({'user': self.user}, code='closed')
        self.assert_form_valid({'user': self.user}, created_by=self.dining_list.owners.first())

    @patch_time()
    def test_room(self):
        """Asserts that the form can not be used after the timelimit."""
        # Verify testcase data
        self.assertNotIn(self.user, self.dining_list.owners.all(), "Incorrect test data, user should not be owner")
        # Fill the dininglist with meaningless entries
        other_user = User.objects.get(id=1)
        for i in range(14):
            DiningEntryExternal.objects.create(dining_list=self.dining_list, user=other_user, created_by=other_user)
        self.dining_list.max_diners = 14

        self.assert_form_has_error({'user': self.user}, code='full')
        self.assert_form_valid({'user': self.user}, created_by=self.dining_list.owners.first())

    @patch_time()
    def test_association_only_limitation(self):
        """Asserts that the form can not be used after the timelimit."""
        # Verify testcase data
        self.dining_list.limit_signups_to_association_only = True
        self.dining_list.save()
        self.assertNotIn(self.user, self.dining_list.owners.all(), "Incorrect test data, user should not be owner")
        # user 2 is member of the association
        self.assert_form_valid({'user': self.user})
        # user 4 is not a member
        self.assert_form_has_error({'user': User.objects.get(id=4)}, code='members_only')
        # owners can override
        self.assert_form_valid({'user': User.objects.get(id=4)}, created_by=self.dining_list.owners.first())

    @patch_time()
    def test_minimum_balance(self):
        with self.settings(MINIMUM_BALANCE_FOR_DINING_SIGN_UP=100):
            # For minimum balance, nobody has an exception, not even admins
            self.assert_form_has_error({'user': self.user}, code='nomoneyzz')
            self.assert_form_has_error({'user': self.user}, created_by=self.dining_list.owners.first(), code='nomoneyzz')
            admin = User.objects.filter(is_superuser=True).first()
            self.assert_form_has_error({'user': admin}, created_by=admin, code='nomoneyzz')

    @patch_time(dt=datetime(2022, 5, 30, 12, 0))
    def test_form_editing_time_limit(self):
        """Asserts that the form can not be used after the timelimit."""
        self.assert_form_has_error({'user': self.user}, code='closed')


class TestDiningEntryExternalCreateForm(FormValidityMixin, TestCase):
    fixtures = ['base', 'base_credits', 'dining_lists']
    form_class = DiningEntryExternalCreateForm

    def setUp(self):
        self.dining_list = DiningList.objects.get(id=3)
        self.user = User.objects.get(id=2)

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('dining_list', self.dining_list)
        kwargs.setdefault('created_by', self.user)
        return super(TestDiningEntryExternalCreateForm, self).get_form_kwargs(**kwargs)

    @patch_time()
    def test_form_valid(self):
        """Asserts that the testing environment standard is valid."""
        # Check for self creation, useful to guarantee a baseline of current testing environment
        self.assert_form_valid({'name': 'my_guest'})

    @patch_time()
    def test_entry_db_creation(self):
        """Tests the database object creation for an entry."""
        form = self.assert_form_valid({'name': 'my guest'})
        instance = form.save()

        self.assertTrue(DiningEntryExternal.objects.filter(id=instance.id).exists())
        instance.refresh_from_db()
        self.assertEqual(instance.user, self.user)
        self.assertEqual(instance.created_by, self.user)
        self.assertEqual(instance.name, 'my guest')

    @patch_time()
    def test_transation_db_creation(self):
        """Asserts that the correct transaction is created."""
        # Adjust kitchen cost so we can test it takes that value
        self.dining_list.kitchen_cost = 0.37
        self.dining_list.save()

        # Save the instance
        form = self.assert_form_valid({'name': 'my guest'})
        instance = form.save()

        self.assertIsNotNone(instance.transaction)
        self.assertEqual(instance.transaction.amount, self.dining_list.kitchen_cost)
        self.assertEqual(instance.transaction.source, self.user.account)
        self.assertEqual(instance.transaction.target, Account.objects.get(special='kitchen_cost'))
        self.assertEqual(instance.created_by, self.user)

    @patch_time(dt=datetime(2022, 4, 26, 18, 0))
    def test_sign_up_deadline(self):
        # Verify testcase data
        self.assertNotIn(self.user, self.dining_list.owners.all(), "Incorrect test data, user should not be owner")
        self.assert_form_has_error({'name': 'my guest'}, code='closed')
        self.assert_form_valid({'name': 'my guest'}, created_by=self.dining_list.owners.first())

    @patch_time()
    def test_room(self):
        # Verify testcase data
        self.assertNotIn(self.user, self.dining_list.owners.all(), "Incorrect test data, user should not be owner")
        # Fill the dininglist with meaningless entries
        other_user = User.objects.get(id=1)
        for i in range(14):
            DiningEntryExternal.objects.create(dining_list=self.dining_list, user=other_user, created_by=other_user)
        self.dining_list.max_diners = 14

        self.assert_form_has_error({'name': 'my guest'}, code='full')
        self.assert_form_valid({'name': 'my guest'}, created_by=self.dining_list.owners.first())

    @patch_time()
    def test_association_only_limitation(self):
        # Verify testcase data
        self.dining_list.limit_signups_to_association_only = True
        self.dining_list.save()
        self.assertNotIn(self.user, self.dining_list.owners.all(), "Incorrect test data, user should not be owner")
        # user 2 is member of the association
        self.assert_form_valid({'name': 'my guest'})
        # user 4 is not a member
        self.assert_form_has_error({'name': 'my guest'}, code='members_only', created_by=User.objects.get(id=4))
        # owners can override
        self.assert_form_valid({'name': 'my guest'}, created_by=self.dining_list.owners.first())

    @patch_time()
    def test_minimum_balance(self):
        with self.settings(MINIMUM_BALANCE_FOR_DINING_SIGN_UP=100):
            # For minimum balance, nobody has an exception, not even admins
            self.assert_form_has_error({'name': 'my guest'}, code='nomoneyzz')
            self.assert_form_has_error({'name': 'my guest'}, created_by=self.dining_list.owners.first(), code='nomoneyzz')
            admin = User.objects.filter(is_superuser=True).first()
            self.assert_form_has_error({'name': 'my guest'}, created_by=admin, code='nomoneyzz')

    @patch_time(dt=datetime(2022, 5, 30, 12, 0))
    def test_form_editing_time_limit(self):
        """Asserts that the form can not be used after the timelimit."""
        self.assert_form_has_error({'name': 'my guest'}, code='closed')


class TestDiningEntryDeleteForm(FormValidityMixin, TestCase):
    fixtures = ['base', 'dining_lists']
    form_class = DiningEntryDeleteForm

    def setUp(self):
        self.entry = DiningEntryUser.objects.get(id=2)
        self.user = self.entry.user
        self.dining_list = self.entry.dining_list

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('entry', self.entry)
        kwargs.setdefault('deleter', self.user)
        return super(TestDiningEntryDeleteForm, self).get_form_kwargs(**kwargs)

    @patch_time()
    def test_form_valid(self):
        self.assert_form_valid({})
        # Test an external user that this user added
        self.assert_form_valid({}, entry=DiningEntryExternal.objects.get(id=4))

    @patch_time()
    def test_db_entry_deletion(self):
        form = self.assert_form_valid({})
        form.execute()

        self.assertFalse(DiningEntry.objects.filter(id=self.entry.id).exists())

    @patch_time(dt=datetime(2022, 4, 26, 14, 23))
    def test_db_transacton_deletion(self):
        self.assert_form_valid({}).execute()
        self.entry.transaction.refresh_from_db()

        self.assertEqual(self.entry.transaction.cancelled, timezone.make_aware(datetime(2022, 4, 26, 14, 23)))
        self.assertEqual(self.entry.transaction.cancelled_by, self.user)

    @patch_time(dt=datetime(2022, 4, 26, 18, 0))
    def test_sign_up_deadline(self):
        """Asserts that the form can not be used after the sign-up deadline unless owner."""
        # Verify testcase data
        self.assertNotIn(self.user, self.dining_list.owners.all(), "Incorrect test data, user should not be owner")
        self.assert_form_has_error({}, code='closed')
        self.assert_form_valid({}, deleter=self.dining_list.owners.first())

    @patch_time()
    def test_ownership(self):
        self.assert_form_has_error({}, code='not_owner', deleter=User.objects.get(id=5))

    @patch_time(dt=datetime(2022, 5, 30, 12, 0))
    def test_form_editing_time_limit(self):
        """Asserts that the form can not be used after the timelimit."""
        self.assert_form_has_error({}, code='locked')


class TestDiningListDeleteForm(FormValidityMixin, TestCase):
    fixtures = ['base', 'dining_lists']
    form_class = DiningListDeleteForm

    def setUp(self):
        self.user = User.objects.get(id=1)
        self.dining_list = DiningList.objects.get(id=1)

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('instance', self.dining_list)
        kwargs.setdefault('deleted_by', self.user)
        return super(TestDiningListDeleteForm, self).get_form_kwargs(**kwargs)

    @patch_time()
    def test_form_valid(self):
        """Asserts that the testing environment standard is valid."""
        self.assert_form_valid({})

    @patch_time()
    def test_db_list_deletion(self):
        dining_list_id = self.dining_list.id
        self.assert_form_valid({}).execute()

        self.assertFalse(DiningEntryUser.objects.filter(dining_list__id=dining_list_id).exists())
        self.assertFalse(DiningEntryExternal.objects.filter(dining_list__id=dining_list_id).exists())

    @patch_time()
    def test_db_transaction_cancellation(self):
        """Tests that the correct transactions are cancelled."""
        diner_count = self.dining_list.dining_entries.count()
        old_cancelled_transaction_count = Transaction.objects.filter(cancelled__isnull=False).count()

        self.assert_form_valid({}).execute()

        # Ensure that the
        self.assertEqual(
            Transaction.objects.filter(cancelled__isnull=False).count(),
            old_cancelled_transaction_count + diner_count
        )

    @patch_time()
    def test_owner_deletion(self):
        self.dining_list.owners.clear()
        self.assert_form_has_error({}, code="not_owner")

    @patch_time(dt=datetime(2022, 5, 30, 12, 0))
    def test_form_editing_time_limit(self):
        """Asserts that the form can not be used after the timelimit."""
        self.assert_form_has_error({}, code='locked')


class TestDiningInfoForm(FormValidityMixin, TestCase):
    fixtures = ['base', 'dining_lists']
    form_class = DiningInfoForm

    def setUp(self):
        self.dining_list = DiningList.objects.get(id=1)
        self.user = User.objects.get(id=1)

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('instance', self.dining_list)
        return super(TestDiningInfoForm, self).get_form_kwargs(**kwargs)

    def test_class(self):
        self.assertTrue(issubclass(self.form_class, ModelForm))
        self.assertTrue(issubclass(self.form_class, ConcurrenflictFormMixin))

    def test_widget_replacements(self):
        form = self.build_form({})
        self.assertIsInstance(form.fields['owners'].widget, ModelSelect2Multiple)

    @patch_time()
    def test_form_valid(self):
        self.assert_form_valid({
            'owners': [1],
            'dish': "My delicious dish",
            'serve_time': time(18, 00),
            'min_diners': 4,
            'max_diners': 15,
            'sign_up_deadline': datetime(2022, 4, 26, 15, 0),
        })

    @patch_time()
    def test_db_update(self):
        updated_dining_list = self.assert_form_valid({
            'owners': [4],
            'dish': "New dish",
            'serve_time': time(17, 5),
            'min_diners': 6,
            'max_diners': 14,
            'sign_up_deadline': datetime(2022, 4, 26, 12, 00),
        }).save()

        # Update the dining_list
        self.dining_list.refresh_from_db()

        self.assertNotIn(self.user, updated_dining_list.owners.all())
        self.assertIn(User.objects.get(id=4), updated_dining_list.owners.all())
        self.assertEqual(updated_dining_list.dish, "New dish")
        self.assertEqual(updated_dining_list.serve_time, time(17, 5))
        self.assertEqual(updated_dining_list.min_diners, 6)
        self.assertEqual(updated_dining_list.max_diners, 14)
        self.assertNotEqual(updated_dining_list.sign_up_deadline.time(), self.dining_list.sign_up_deadline)

    @patch_time(dt=datetime(2022, 5, 30, 12, 0))
    def test_form_editing_time_limit(self):
        """Asserts that the form can not be used after the timelimit."""
        self.assert_form_has_error({}, code='closed')

    @patch_time()
    def test_kitchen_open_time_validity(self):
        """Asserts that the meal can't be served before the kitchen opening time."""
        dt = datetime.combine(timezone.now().today(), settings.KITCHEN_USE_START_TIME) - timedelta(minutes=1)
        self.assert_form_has_error({
            'serve_time': dt.time()
        }, code='kitchen_start_time')

    @patch_time()
    def test_kitchen_close_time_validity(self):
        """Asserts that the meal can't be served after the kitchen closing time."""
        dt = datetime.combine(timezone.now().today(), settings.KITCHEN_USE_END_TIME) + timedelta(minutes=1)
        self.assert_form_has_error({
            'serve_time': dt.time()
        }, code='kitchen_close_time')


class TestDiningPaymentForm(FormValidityMixin, TestCase):
    fixtures = ['base', 'dining_lists']
    form_class = DiningPaymentForm

    def setUp(self):
        self.dining_list = DiningList.objects.get(id=1)
        self.user = User.objects.get(id=1)

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('instance', self.dining_list)
        return super(TestDiningPaymentForm, self).get_form_kwargs(**kwargs)

    def test_class(self):
        self.assertTrue(issubclass(self.form_class, ModelForm))
        self.assertTrue(issubclass(self.form_class, ConcurrenflictFormMixin))

    @patch_time()
    def test_form_valid(self):
        self.assert_form_valid({
            'payment_link': "https://www.google.com/",
        })
        self.assert_form_valid({})

    @patch_time()
    def test_dining_cost_conflict(self):
        """Assert that an error is raised when both dinner_cost and dinner_cost_total are defined."""
        self.assert_form_has_error({
            'dining_cost_total': 12,
            'dining_cost': 4,
        }, code='duplicate_cost', field='dining_cost')
        self.assert_form_has_error({
            'dining_cost_total': 12,
            'dining_cost': 4,
        }, code='duplicate_cost', field='dining_cost_total')

    @patch_time()
    def test_dining_cost_total_empty_diners(self):
        """Assert an error is raised for costs when there are no diners on the dining list."""
        self.dining_list.dining_entries.all().delete()
        self.assert_form_has_error({
            'dining_cost_total': 12,
        }, code='costs_no_diners')

    @patch_time()
    def test_dining_cost_total(self):
        """Test that dining cost is correctly computed from total cost."""
        form = self.assert_form_valid({'dining_cost_total': 16})
        self.assertIsNone(form.cleaned_data['dining_cost_total'])
        self.assertEqual(form.cleaned_data['dining_cost'], 2)

        # Test that it rounds up
        form = self.assert_form_valid({'dining_cost_total': 15.95})
        self.assertIsNone(form.cleaned_data['dining_cost_total'])
        self.assertEqual(form.cleaned_data['dining_cost'], 2)


class TestDiningCommentForm(FormValidityMixin, TestCase):
    fixtures = ['base', 'dining_lists']
    form_class = DiningCommentForm

    def setUp(self):
        self.dining_list = DiningList.objects.get(id=1)
        self.user = User.objects.get(id=1)

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('dining_list', self.dining_list)
        kwargs.setdefault('poster', self.user)
        return super(TestDiningCommentForm, self).get_form_kwargs(**kwargs)

    def test_valid(self):
        """Tests basic validity functionality."""
        posted_msg = 'My very message'
        form = self.assert_form_valid({'message': posted_msg})
        form.save()

        # Assert copy on database:
        self.assertTrue(DiningComment.objects.filter(id=form.instance.id).exists())
        form.instance.refresh_from_db()  # Get database states
        self.assertEqual(form.instance.message, posted_msg)
        self.assertEqual(form.instance.dining_list, self.dining_list)
        self.assertEqual(form.instance.poster, self.user)
        self.assertEqual(form.instance.pinned_to_top, False)

    def test_pinning(self):
        """Tests that a message can be pinned."""
        posted_msg = "A stickied message"
        form = self.assert_form_valid({'message': posted_msg}, pinned=True)
        form.save()
        self.assertEqual(form.instance.pinned_to_top, True)


class TestSendReminderForm(FormValidityMixin, TestPatchMixin, TestCase):
    fixtures = ['base', 'dining_lists']
    form_class = SendReminderForm

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('dining_list', self.dining_list)
        return super(TestSendReminderForm, self).get_form_kwargs(**kwargs)

    def setUp(self):
        self.dining_list = DiningList.objects.get(id=1)

    def test_is_valid(self):
        """Tests that the form is normally valid."""
        self.assert_form_valid({})

    def test_invalid_all_paid(self):
        # Make all users paid
        self.dining_list.dining_entries.update(has_paid=True)
        self.assert_form_has_error({}, code='all_paid')

    def test_invalid_missing_payment_link(self):
        self.dining_list.payment_link = ""
        self.dining_list.save()
        self.assert_form_has_error({}, code='payment_url_missing')

    @patch('dining.forms.send_templated_mail')
    def test_no_unpaid_users_sending(self, mock_mail):
        """Asserts that when all users have paid, no mails are send to remind people."""
        DiningEntryUser.objects.update(has_paid=True)
        DiningEntryExternal.objects.all().delete()
        form = self.build_form({})
        request = HttpRequest()
        request.user = User.objects.get(id=1)
        form.send_reminder(request=request)

        mock_mail.assert_not_called()

    @patch('dining.forms.send_templated_mail')
    def test_mail_sending_users(self, mock_mail):
        form = self.assert_form_valid({})
        request = HttpRequest()
        request.user = User.objects.get(id=1)
        form.send_reminder(request=request)

        calls = self.assert_has_call(mock_mail, arg_1="mail/dining_payment_reminder")
        # Assert that the correct number of recipients are documented
        self.assertEqual(
            len(calls[0]['args'][1]),
            DiningEntryUser.objects.filter(
                dining_list=self.dining_list,
                has_paid=False,
            ).count()
        )

        self.assertEqual(calls[0]['context']['dining_list'], self.dining_list)
        self.assertEqual(calls[0]['context']['reminder'], User.objects.get(id=1))

    @patch('dining.forms.send_templated_mail')
    def test_mail_sending_external(self, mock_mail):
        """Tests handling of messaging for external guests added by a certain user."""
        form = self.assert_form_valid({})
        request = HttpRequest()
        request.user = User.objects.get(id=1)
        form.send_reminder(request=request)

        calls = self.assert_has_call(mock_mail, arg_1="mail/dining_payment_reminder_external")
        self.assertEqual(len(calls), 2)  # ids 2 and 3 added unpaid guests

        self.assertEqual(calls[0]['context']['dining_list'], self.dining_list)
        self.assertEqual(calls[0]['context']['reminder'], User.objects.get(id=1))
        self.assertEqual(calls[0]['args'][1], User.objects.get(id=2))
        self.assertEqual(len(calls[0]['context']['guests']), 2)
        self.assertEqual(calls[1]['args'][1], User.objects.get(id=3))
        self.assertEqual(len(calls[1]['context']['guests']), 1)
