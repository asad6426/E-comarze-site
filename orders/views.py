from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
import uuid

from orders.models import Cart, CartItem, Order, OrderItem
from sslcommerz_lib import SSLCOMMERZ


@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return render(request, 'orders/cart.html', {'cart': cart})


@login_required
def checkout_view(request):
    cart = get_object_or_404(Cart, user=request.user)
    if not cart.items.exists():
        messages.warning(request, 'Your cart is empty!')
        return redirect('cart')

    if request.method == 'POST':
        order = Order.objects.create(
            user=request.user,
            first_name=request.POST['first_name'],
            last_name=request.POST['last_name'],
            email=request.POST['email'],
            address=request.POST['address'],
            postal_code=request.POST['postal_code'],
            city=request.POST['city'],
            note=request.POST.get('note', ''),
        )

        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                price=cart_item.product.price,
                quantity=cart_item.quantity,
            )

        tran_id = str(uuid.uuid4())
        order.transaction_id = tran_id
        order.save()

        settings_data = {
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_pass': settings.SSLCOMMERZ_STORE_PASS,
            'issandbox': settings.SSLCOMMERZ_IS_SANDBOX,
        }

        sslcz = SSLCOMMERZ(settings_data)

        post_body = {
            'total_amount': float(order.get_total()),
            'currency': "BDT",
            'tran_id': tran_id,
            'success_url': request.build_absolute_uri(reverse('payment_success')),
            'fail_url': request.build_absolute_uri(reverse('payment_fail')),
            'cancel_url': request.build_absolute_uri(reverse('payment_cancel')),
            'emi_option': 0,
            'cus_name': f"{order.first_name} {order.last_name}",
            'cus_email': order.email,
            'cus_phone': '01700000000',
            'cus_add1': order.address,
            'cus_city': order.city,
            'cus_postcode': order.postal_code,
            'cus_country': 'Bangladesh',
            'shipping_method': 'NO',
            'product_name': 'E-commerce Order',
            'product_category': 'General',
            'product_profile': 'general',
        }

        response = sslcz.createSession(post_body)

        if response.get('status') == 'SUCCESS':
            return redirect(response['GatewayPageURL'])
        else:
            order.delete()
            messages.error(request, 'Payment gateway error. Please try again.')
            return redirect('checkout')

    return render(request, 'orders/checkout.html', {'cart': cart})


@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id')
        status = request.POST.get('status')

        if status == 'VALID':
            try:
                order = Order.objects.get(transaction_id=tran_id)
                order.paid = True
                order.status = 'processing'
                order.save()
                Cart.objects.filter(user=order.user).delete()
                return render(request, 'orders/payment_success.html', {'order': order})
            except Order.DoesNotExist:
                pass

    return redirect('home')


@csrf_exempt
def payment_fail(request):
    tran_id = request.POST.get('tran_id', '')
    try:
        order = Order.objects.get(transaction_id=tran_id)
        order.delete()
    except Order.DoesNotExist:
        pass
    messages.error(request, 'Payment failed!')
    return render(request, 'orders/payment_fail.html')


@csrf_exempt
def payment_cancel(request):
    tran_id = request.POST.get('tran_id', '')
    try:
        order = Order.objects.get(transaction_id=tran_id)
        order.delete()
    except Order.DoesNotExist:
        pass
    messages.warning(request, 'Payment cancelled.')
    return render(request, 'orders/payment_cancel.html')


@login_required
def order_list_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})