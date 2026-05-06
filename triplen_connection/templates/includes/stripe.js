var stripe = Stripe("{{ publishable_key }}");
var elements = stripe.elements();

var style = {
	base: {
		color: "#425466",
		fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
		fontSmoothing: "antialiased",
		fontSize: "16px",
		"::placeholder": {
			color: "#aab7c4",
		},
	},
	invalid: {
		color: "#df1b41",
		iconColor: "#df1b41",
	},
};

var card = elements.create("card", {
	style: style,
	hidePostalCode: true,
});

card.mount("#card-element");

card.on("change", function (event) {
	var displayError = document.getElementById("card-errors");
	displayError.textContent = event.error ? event.error.message : "";
});

frappe.ready(function () {
	var form = document.getElementById("payment-form");
	if (!form) return;

	form.addEventListener("submit", function (e) {
		e.preventDefault();

		var btn = document.getElementById("submit");
		var errorDisplay = document.getElementById("payment-error");

		btn.disabled = true;
		btn.textContent = "{{ _('Processing...') }}";
		errorDisplay.hidden = true;

		var extraDetails = {
			name: document.getElementById("cardholder-name").value,
			email: document.getElementById("cardholder-email").value,
		};

		stripe.createToken(card, extraDetails).then(function (result) {
			if (result.error) {
				btn.disabled = false;
				btn.textContent = "{{ _('Pay') }} {{ amount }}";
				errorDisplay.textContent = result.error.message;
				errorDisplay.hidden = false;
			} else {
				makeFrappePayment(result.token.id);
			}
		});
	});
});

function makeFrappePayment(tokenId) {
	frappe.call({
		method: "payments.templates.pages.stripe_checkout.make_payment",
		args: {
			stripe_token_id: tokenId,
			stripe_request_id: "{{ stripe_request_id }}",
		},
		callback: function (r) {
			if (r.message && r.message.status === "Completed") {
				var form = document.getElementById("payment-form");
				if (form) form.style.display = "none";

				document.getElementById("header-title").textContent =
					"{{ _('Payment Successful') }}";
				document.getElementById("header-description").textContent =
					"{{ _('Thank you for your payment.') }}";

				var successDiv = document.getElementById("success-container");
				successDiv.style.display = "block";

				setTimeout(function () {
					window.location.href = r.message.redirect_to || "{{ redirect_url }}";
				}, 3000);
			} else {
				var btn = document.getElementById("submit");
				var errorDisplay = document.getElementById("payment-error");
				errorDisplay.textContent =
					(r.message && r.message.error) ||
					"{{ _('Payment failed. Please try again.') }}";
				errorDisplay.hidden = false;
				btn.disabled = false;
				btn.textContent = "{{ _('Pay') }} {{ amount }}";
			}
		},
	});
}
