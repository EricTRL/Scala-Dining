from decimal import Decimal, ROUND_UP

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError, BadRequest
from django.db import transaction
from django.forms import DecimalField
from django.shortcuts import redirect
# Create your views here.
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView

from dining.views import DiningListEditMixin
from groceries.forms import PaymentCreateForm
from groceries.models import Payment


class PaymentsView(LoginRequiredMixin, TemplateView):
    template_name = 'groceries/payment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payments = Payment.objects.order_by('-created_at')
        context.update({
            'payer': payments.exclude(receiver=self.request.user).filter(entries__user=self.request.user,
                                                                         entries__external_name=""),
            'payee': payments.filter(receiver=self.request.user),
        })
        return context


# Borrowing the DiningListEditMixin here (to make sure only owners can create a payment)
class PaymentCreateView(LoginRequiredMixin, DiningListEditMixin, TemplateView):
    template_name = 'groceries/payment_create.html'

    def has_cost(self) -> bool:
        """Returns if a total cost value is provided by the user."""
        return 'total_cost' in self.request.GET

    def get_total_cost(self) -> Decimal:
        """Validates and returns the total cost from the GET parameters."""
        # Use a DecimalField to let Django do the validation for us
        field = DecimalField(min_value=Decimal('0.01'), max_digits=8, decimal_places=2)
        try:
            return field.clean(self.request.GET['total_cost'])
        except ValidationError as e:
            raise BadRequest(e)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dining_list = self.get_object()

        if self.has_cost():
            # Use earlier payment for initial info
            previous = Payment.objects.filter(receiver=self.request.user).order_by('created_at').last()
            if previous:
                initial = {
                    'payment_link': previous.payment_link,
                    'phone_number': previous.phone_number,
                    'include_email': previous.include_email,
                    'remarks': previous.remarks,
                }
            else:
                initial = None

            context.update({
                'form': PaymentCreateForm(instance=Payment(dining_list=dining_list, receiver=self.request.user,
                                                           total_cost=self.get_total_cost()), initial=initial),
                'entries': dining_list.entries.order_by('external_name', 'user__first_name', 'user__last_name')
            })
        return context

    def post(self, request, *args, **kwargs):
        if not self.has_cost():
            raise BadRequest("Cost unknown")
        form = PaymentCreateForm(data=request.POST,
                                 instance=Payment(dining_list=self.get_object(), receiver=self.request.user,
                                                  total_cost=self.get_total_cost()))
        if form.is_valid():
            with transaction.atomic():
                payment = form.save()
                # TODO: send mail
            return redirect('groceries:payment-detail', pk=payment.pk)

        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)


class PaymentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Payment

    def test_func(self):
        # Can only use this page if user is receiver
        payment = self.get_object()  # type: Payment
        return payment.receiver == self.request.user
