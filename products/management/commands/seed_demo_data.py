import io
import json
import random
import urllib.parse
import urllib.request
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from users.models import User
from products.models import Category, Product, Rating
from orders.models import Cart, CartItem, Order, OrderItem

PLACEHOLDER_COLORS = [
    (241, 90, 90), (90, 141, 241), (90, 200, 140), (230, 180, 60),
    (170, 100, 220), (60, 190, 200), (240, 130, 70), (140, 140, 140),
]

USER_AGENT = "DemoDataSeeder/1.0 (asaduzzamancld@gmail.com)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


class Command(BaseCommand):
    help = "Populate the database with demo data for all tables"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing demo-generated data before seeding",
        )
        parser.add_argument(
            "--refresh-images",
            action="store_true",
            help="Re-fetch product images even if one is already attached",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing data...")
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            CartItem.objects.all().delete()
            Cart.objects.all().delete()
            Rating.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        users = self.seed_users()
        categories = self.seed_categories()
        products = self.seed_products(categories, refresh_images=options["refresh_images"])
        self.seed_ratings(products, users)
        self.seed_carts(users, products)
        self.seed_orders(users, products)

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))

    def seed_users(self):
        self.stdout.write("Seeding users...")
        demo_users = [
            {"username": "john_doe", "email": "john@example.com", "first_name": "John", "last_name": "Doe"},
            {"username": "jane_smith", "email": "jane@example.com", "first_name": "Jane", "last_name": "Smith"},
            {"username": "rahim_khan", "email": "rahim@example.com", "first_name": "Rahim", "last_name": "Khan"},
            {"username": "karim_ahmed", "email": "karim@example.com", "first_name": "Karim", "last_name": "Ahmed"},
            {"username": "sara_islam", "email": "sara@example.com", "first_name": "Sara", "last_name": "Islam"},
        ]
        users = []
        for data in demo_users:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "username": data["username"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                },
            )
            if created:
                user.set_password("demo12345")
                user.save()
            users.append(user)
        return users

    def seed_categories(self):
        self.stdout.write("Seeding categories...")
        names = ["Electronics", "Fashion", "Home & Kitchen", "Books", "Sports & Outdoors"]
        categories = []
        for name in names:
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={"description": f"Demo category for {name}"},
            )
            categories.append(category)
        return categories

    def seed_products(self, categories, refresh_images=False):
        self.stdout.write("Seeding products...")
        demo_products = [
            ("Wireless Mouse", "Electronics", "39.99", 50, "wireless computer mouse"),
            ("Bluetooth Headphones", "Electronics", "59.99", 30, "bluetooth headphones"),
            ("Smart Watch", "Electronics", "89.99", 20, "smartwatch"),
            ("Men's T-Shirt", "Fashion", "14.99", 100, "men t-shirt clothing"),
            ("Women's Handbag", "Fashion", "34.99", 40, "women handbag purse"),
            ("Running Shoes", "Sports & Outdoors", "49.99", 35, "running shoes sneakers"),
            ("Non-stick Frying Pan", "Home & Kitchen", "24.99", 25, "non-stick frying pan"),
            ("Coffee Maker", "Home & Kitchen", "44.99", 15, "coffee maker machine"),
            ("The Great Gatsby", "Books", "9.99", 60, "the great gatsby book cover"),
            ("Atomic Habits", "Books", "12.99", 80, "atomic habits book cover"),
            ("Yoga Mat", "Sports & Outdoors", "19.99", 45, "yoga mat"),
            ("Desk Lamp", "Home & Kitchen", "17.99", 55, "desk lamp"),
        ]
        category_map = {c.name: c for c in categories}
        products = []
        for name, cat_name, price, stock, search_term in demo_products:
            product, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": category_map[cat_name],
                    "description": f"This is a demo description for {name}.",
                    "price": Decimal(price),
                    "stock": stock,
                    "available": True,
                },
            )
            if not product.image or refresh_images:
                self.attach_demo_image(product, search_term)
            products.append(product)
        return products

    def attach_demo_image(self, product, search_term):
        image_bytes = self.fetch_online_image(search_term)
        if image_bytes is None:
            self.stdout.write(f"  Falling back to placeholder image for {product.name}")
            image_bytes = self.generate_placeholder_image(product.name)
        filename = f"{product.slug or product.id}.jpg"
        product.image.save(filename, ContentFile(image_bytes), save=True)

    def fetch_online_image(self, search_term):
        """Search Wikimedia Commons for a real photo matching the search term."""
        query = urllib.parse.quote(f"filetype:bitmap {search_term}")
        search_url = (
            f"{COMMONS_API}?action=query&generator=search&gsrsearch={query}"
            f"&gsrnamespace=6&gsrlimit=5&prop=imageinfo&iiprop=url&iiurlwidth=600"
            f"&format=json"
        )
        try:
            req = urllib.request.Request(search_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            pages = list(data.get("query", {}).get("pages", {}).values())
            if not pages:
                return None
            for page in pages:
                info = page.get("imageinfo", [{}])[0]
                image_url = info.get("thumburl") or info.get("url")
                if not image_url:
                    continue
                img_req = urllib.request.Request(image_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                    raw = img_resp.read()
                # Normalize to JPEG so all stored images share a consistent format.
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return buffer.getvalue()
        except Exception as exc:
            self.stdout.write(f"  Image fetch failed for '{search_term}': {exc}")
            return None
        return None

    def generate_placeholder_image(self, text):
        color = random.choice(PLACEHOLDER_COLORS)
        img = Image.new("RGB", (600, 400), color=color)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except OSError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((600 - text_w) / 2, (400 - text_h) / 2),
            text,
            fill=(255, 255, 255),
            font=font,
        )
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        return buffer.getvalue()

    def seed_ratings(self, products, users):
        self.stdout.write("Seeding ratings...")
        comments = [
            "Great product, highly recommended!",
            "Value for money.",
            "Works as expected.",
            "Could be better.",
            "Excellent quality and fast delivery.",
        ]
        for product in products:
            sampled_users = random.sample(users, k=min(3, len(users)))
            for user in sampled_users:
                Rating.objects.get_or_create(
                    product=product,
                    user=user,
                    defaults={
                        "rating": random.randint(3, 5),
                        "comment": random.choice(comments),
                    },
                )

    def seed_carts(self, users, products):
        self.stdout.write("Seeding carts...")
        for user in users[:3]:
            cart, _ = Cart.objects.get_or_create(user=user)
            sampled_products = random.sample(products, k=min(3, len(products)))
            for product in sampled_products:
                CartItem.objects.get_or_create(
                    cart=cart,
                    product=product,
                    defaults={"quantity": random.randint(1, 3)},
                )

    def seed_orders(self, users, products):
        self.stdout.write("Seeding orders...")
        statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
        cities = ["Dhaka", "Chittagong", "Khulna", "Rajshahi", "Sylhet"]

        for user in users:
            if Order.objects.filter(user=user).exists():
                continue
            order = Order.objects.create(
                user=user,
                first_name=user.first_name or "Demo",
                last_name=user.last_name or "User",
                email=user.email,
                address=f"{random.randint(1, 200)} Demo Street",
                postal_code=str(random.randint(1000, 9999)),
                city=random.choice(cities),
                status=random.choice(statuses),
                note="Demo order",
                paid=random.choice([True, False]),
                transaction_id=f"TXN{random.randint(100000, 999999)}",
            )
            sampled_products = random.sample(products, k=min(3, len(products)))
            for product in sampled_products:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    price=product.price,
                    quantity=random.randint(1, 3),
                )
