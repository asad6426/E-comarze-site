from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from products.models import Product, Category, Rating
from orders.models import Cart, CartItem

def home_view(request):
    products = Product.objects.filter(available=True)
    categories = Category.objects.all()
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    return render(request, 'products/home.html', {
        'products': products,
        'categories': categories,
    })

def product_detail_view(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    ratings = product.ratings.all()
    return render(request, 'products/detail.html', {
        'product': product,
        'ratings': ratings,
    })

@login_required
def add_rating_view(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        rating_val = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        Rating.objects.update_or_create(
            product=product, user=request.user,
            defaults={'rating': rating_val, 'comment': comment}
        )
        messages.success(request, 'Rating submitted!')
    return redirect('product_detail', slug=slug)

@login_required
def add_to_cart_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    messages.success(request, f'"{product.name}" added to cart!')
    return redirect('cart')

@login_required
def remove_from_cart_view(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    return redirect('cart')