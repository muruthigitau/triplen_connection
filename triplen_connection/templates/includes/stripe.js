frappe.ready(function() {
    var publishable_key = "{{ publishable_key }}";
    
    if (!publishable_key || publishable_key === "None") {
        console.error("Stripe Publishable Key is missing.");
        $('#card-errors').text("Configuration error: Stripe API key not found.");
        $('#submit').prop('disabled', true);
        return;
    }

    var stripe = Stripe(publishable_key);
    var elements = stripe.elements();

    var style = {
        base: {
            color: 'green',
            lineHeight: '18px',
            fontWeight: 700,
            fontFamily: '"Helvetica Neue", Helvetica, sans-serif',
            fontSmoothing: 'antialiased',
            fontSize: '16px',
            '::placeholder': { color: '#aab7c4' }
        },
        invalid: {
            color: '#fa755a',
            iconColor: '#fa755a'
        }
    };

    var card = elements.create('card', { hidePostalCode: true, style: style });
    card.mount('#card-element');

    card.on('change', function(event) {
        var displayError = document.getElementById('card-errors');
        displayError.textContent = event.error ? event.error.message : '';
    });

    $('#submit').off("click").on("click", function(e) {
        e.preventDefault();
        
        var btn = $(this);
        btn.prop('disabled', true).html("{{ _('Processing...') }}");
        $('.error').hide();

        var extraDetails = {
            name: $('#cardholder-name').val(),
            email: $('#cardholder-email').val()
        };

        stripe.createToken(card, extraDetails).then(function(result) {
            if (result.error) {
                $('#card-errors').text(result.error.message);
                btn.prop('disabled', false).html("{{ _('Pay') }} {{ amount }}");
            } else {
                executeFrappePayment(result.token.id);
            }
        });
    });

    function executeFrappePayment(tokenId) {
        frappe.call({
            method: "triplen_connection.www.stripe.make_payment",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            args: {
                "stripe_token_id": tokenId,
                "stripe_request_id": "{{ stripe_request_id }}",
                "data": JSON.stringify({{ frappe.form_dict|json }}),
                "reference_doctype": "{{ reference_doctype }}",
                "reference_docname": "{{ reference_docname }}",
                "payment_gateway": "{{ payment_gateway }}"
            },
            callback: function(r) {
                if (r.message && r.message.status == "Completed") {
                    $('#payment-form').hide();
                    $('#header-title').text("{{ _('Payment Successful') }}");
                    $('.success').show();
                    setTimeout(function() {
                        window.location.href = r.message.redirect_to;
                    }, 2000);
                } else {
                    $('#submit').prop('disabled', false).html("{{ _('Pay') }} {{ amount }}");
                    var msg = (r.message && r.message.error) ? r.message.error : "{{ _('Payment failed') }}";
                    $('.error').text(msg).show();
                }
            }
        });
    }
});