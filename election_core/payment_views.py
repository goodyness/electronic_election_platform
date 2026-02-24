import json
import hashlib
import hmac
import uuid
import requests
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Election, ElectionPayment, PlanPricing, ElectionOrganizer
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail


def select_plan(request, short_id):
    election = get_object_or_404(Election, short_id=short_id)
    
    if election.organizer.user != request.user:
        messages.error(request, "Access denied.")
        return redirect('home')
    
    current_plan = election.get_plan_display()
    
    plans = PlanPricing.get_all_plans()
    
    return render(request, 'election_core/select_plan.html', {
        'election': election,
        'plans': plans,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    })


def activate_free_plan(request, short_id):
    election = get_object_or_404(Election, short_id=short_id)
    
    if election.organizer.user != request.user:
        messages.error(request, "Access denied.")
        return redirect('home')
    
    election.plan = 'FREE'
    election.save()
    
    ElectionPayment.objects.update_or_create(
        election=election,
        defaults={
            'plan': 'FREE',
            'email_count': 50,
            'amount': 0,
            'paystack_status': 'SUCCESS',
            'is_verified': True,
            'paid_at': timezone.now(),
        }
    )
    
    messages.success(request, "Free plan activated! You can upload up to 50 voter emails.")
    return redirect('manage_election', short_id=election.short_id)


def initialize_payment(request, short_id):
    if request.method != 'POST':
        return redirect('select_plan', short_id=short_id)
    
    election = get_object_or_404(Election, short_id=short_id)
    
    if election.organizer.user != request.user:
        messages.error(request, "Access denied.")
        return redirect('home')
    
    plan_name = request.POST.get('plan')
    email_count = int(request.POST.get('email_count', 0))
    custom_slug = request.POST.get('custom_slug', '').strip()
    
    try:
        plan_pricing = PlanPricing.objects.get(plan_name=plan_name)
    except PlanPricing.DoesNotExist:
        messages.error(request, "Invalid plan selected.")
        return redirect('select_plan', short_id=short_id)
    
    if plan_pricing.max_emails > 0 and email_count > plan_pricing.max_emails:
        messages.error(request, f"Maximum {plan_pricing.max_emails} emails allowed for {plan_pricing.get_plan_name_display()} plan.")
        return redirect('select_plan', short_id=short_id)
    
    if email_count < 1:
        messages.error(request, "Please enter a valid number of emails.")
        return redirect('select_plan', short_id=short_id)
    
    amount_naira = Decimal(email_count) * plan_pricing.price_per_email
    amount_kobo = int(amount_naira * 100)
    
    reference = f"ELEC-{election.id}-{uuid.uuid4().hex[:8].upper()}"
    
    payment = ElectionPayment.objects.create(
        election=election,
        plan=plan_name,
        email_count=email_count,
        amount=amount_naira,
        paystack_reference=reference,
        paystack_status='PENDING',
        is_verified=False,
    )
    
    if plan_name == 'PREMIUM' and custom_slug:
        election.custom_slug = custom_slug
        election.save()
    
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }
    
    payload = {
        'email': request.user.email,
        'amount': amount_kobo,
        'reference': reference,
        'callback_url': request.build_absolute_uri(f'/election/{short_id}/verify-payment/'),
        'metadata': {
            'election_id': election.id,
            'plan': plan_name,
            'email_count': email_count,
        }
    }
    
    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            json=payload,
            headers=headers,
            timeout=30
        )
        data = response.json()
        
        if data.get('status'):
            return redirect(data['data']['authorization_url'])
        else:
            messages.error(request, f"Payment initialization failed: {data.get('message', 'Unknown error')}")
            return redirect('select_plan', short_id=short_id)
    except requests.RequestException as e:
        messages.error(request, f"Could not connect to payment gateway. Please try again.")
        return redirect('select_plan', short_id=short_id)


def verify_payment(request, short_id):
    election = get_object_or_404(Election, short_id=short_id)
    reference = request.GET.get('reference') or request.GET.get('trxref')
    
    if not reference:
        messages.error(request, "No payment reference found.")
        return redirect('select_plan', short_id=short_id)
    
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
    }
    
    try:
        response = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers=headers,
            timeout=30
        )
        data = response.json()
        
        if data.get('status') and data['data']['status'] == 'success':
            try:
                payment = ElectionPayment.objects.get(paystack_reference=reference)
                payment.paystack_status = 'SUCCESS'
                payment.is_verified = True
                payment.paid_at = timezone.now()
                payment.save()
                
                election.plan = payment.plan
                election.save()
                
                try:
                    from .tasks import send_payment_receipt_task
                    
                    organizer_email = request.user.email
                    dashboard_url = request.build_absolute_uri('/dashboard/organizer/')
                    amount_str = f"₦{payment.amount:,.2f}"
                    
                    send_payment_receipt_task.delay(
                        email=organizer_email,
                        user_name=request.user.first_name,
                        election_title=election.title,
                        plan_name=payment.plan,
                        email_count=payment.email_count,
                        amount_str=amount_str,
                        dashboard_url=dashboard_url
                    )
                except Exception as e:
                    print(f"Failed to queue receipt email: {e}")

                messages.success(request, f"Payment successful! {payment.get_plan_display()} plan activated for your election.")
                return render(request, 'election_core/payment_success.html', {
                    'election': election,
                    'payment': payment,
                })
            except ElectionPayment.DoesNotExist:
                messages.error(request, "Payment record not found.")
                return redirect('select_plan', short_id=short_id)
        else:
            messages.error(request, "Payment verification failed. Please try again or contact support.")
            return redirect('select_plan', short_id=short_id)
    except requests.RequestException:
        messages.error(request, "Could not verify payment. Please try again.")
        return redirect('select_plan', short_id=short_id)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    paystack_signature = request.headers.get('X-Paystack-Signature', '')
    payload = request.body
    
    expected_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    if not hmac.compare_digest(paystack_signature, expected_signature):
        return HttpResponse(status=400)
    
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse(status=400)
    
    if event.get('event') == 'charge.success':
        data = event['data']
        reference = data.get('reference')
        
        try:
            payment = ElectionPayment.objects.get(paystack_reference=reference)
            if not payment.is_verified:
                payment.paystack_status = 'SUCCESS'
                payment.is_verified = True
                payment.paid_at = timezone.now()
                payment.save()
                
                election = payment.election
                election.plan = payment.plan
                election.save()
        except ElectionPayment.DoesNotExist:
            pass
    
    return HttpResponse(status=200)


def election_is_paid(election):
    if election.plan == 'FREE':
        return True
    return election.payments.filter(is_verified=True).exists()


def get_email_limit(election):
    from django.db.models import Sum
    total_paid = election.payments.filter(is_verified=True).aggregate(Sum('email_count'))['email_count__sum'] or 0
    
    if election.plan == 'FREE' and total_paid == 0:
        return 50  
        
    try:
        plan_pricing = PlanPricing.objects.get(plan_name=election.plan)
        if plan_pricing.max_emails == 0:
            return 0  
    except PlanPricing.DoesNotExist:
        pass

    return total_paid
