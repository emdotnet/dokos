from erpnext.erpnext_integrations.idempotency import IdempotencyKey, handle_idempotency
from erpnext.erpnext_integrations.doctype.stripe_settings.api.errors import handle_stripe_errors

class StripePaymentIntent:
	def __init__(self, gateway, payment_request):
		self.gateway = gateway
		self.payment_request = payment_request

	@handle_idempotency
	@handle_stripe_errors
	def create(self, amount, currency, **kwargs):
		return self.gateway.stripe.PaymentIntent.create(
			amount=amount,
			currency=currency,
			setup_future_usage='off_session',
			idempotency_key=IdempotencyKey("payment_intent", "create", self.payment_request.name).get(),
			automatic_payment_methods={
				'enabled': True,
			},
			**kwargs
		)

	@handle_stripe_errors
	def retrieve(self, id, client_secret):
		return self.gateway.stripe.PaymentIntent.retrieve(
			id,
			client_secret=client_secret
		)

	@handle_stripe_errors
	def update(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.modify(
			id,
			**kwargs
		)

	@handle_stripe_errors
	def confirm(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.confirm(
			id,
			**kwargs
		)

	@handle_stripe_errors
	def capture(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.attach(
			id,
			**kwargs
		)

	@handle_stripe_errors
	def cancel(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.detach(
			id,
			**kwargs
		)
