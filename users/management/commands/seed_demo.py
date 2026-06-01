"""
Management command to seed demo data for portfolio showcase.

Creates realistic demo users (1 client + 3 verified workers) with orders,
reviews, and portfolio items so the app looks populated on first visit.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --reset   # Deletes existing demo data first
"""

import io
from decimal import Decimal

from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from orders.models import Message, Review, ServiceOrder
from users.models import PortfolioItem, User, WorkerProfile

DEMO_CLIENT_EMAIL = "demo_cliente@findmyworker.com"
DEMO_PASSWORD = "Demo1234!"

WORKERS = [
    {
        "email": "carlos.plomero@findmyworker.com",
        "first_name": "Carlos",
        "last_name": "Ramírez",
        "profession": "PLUMBER",
        "bio": (
            "Plomero profesional con 8 años de experiencia en instalaciones "
            "residenciales y comerciales. Especializado en detección de fugas, "
            "instalación de tuberías y reparación de calentadores de agua."
        ),
        "years_experience": 8,
        "hourly_rate": Decimal("350.00"),
        "city": "Ciudad de México",
        "average_rating": Decimal("4.80"),
        "color": (41, 128, 185),
        "portfolio": [
            {
                "title": "Reparación de fuga en cocina",
                "description": "Detección y reparación de fuga oculta bajo el fregadero. Se reemplazaron las conexiones y se verificó la presión del sistema.",
            },
            {
                "title": "Instalación de calentador solar",
                "description": "Instalación completa de calentador solar de 200L, incluyendo tuberías de cobre y conexión al sistema existente.",
            },
        ],
        "orders": [
            {
                "description": "Fuga de agua en el baño principal, gotea del tubo bajo el lavabo.",
                "status": "COMPLETED",
                "agreed_price": Decimal("800.00"),
                "review_rating": 5,
                "review_comment": "Excelente trabajo, llegó a tiempo y resolvió el problema rápidamente. Muy recomendado.",
            },
            {
                "description": "Cambio de llave de paso y revisión general de tuberías.",
                "status": "COMPLETED",
                "agreed_price": Decimal("600.00"),
                "review_rating": 5,
                "review_comment": "Muy profesional y honesto con el precio. El trabajo quedó perfecto.",
            },
            {
                "description": "Instalación de regadera nueva en el baño de visitas.",
                "status": "ACCEPTED",
                "agreed_price": Decimal("1200.00"),
            },
        ],
    },
    {
        "email": "lucia.electricista@findmyworker.com",
        "first_name": "Lucía",
        "last_name": "Mendoza",
        "profession": "ELECTRICIAN",
        "bio": (
            "Electricista certificada con 6 años de experiencia. "
            "Instalaciones eléctricas residenciales, tableros de distribución, "
            "iluminación LED y automatización del hogar. Trabajo con garantía."
        ),
        "years_experience": 6,
        "hourly_rate": Decimal("400.00"),
        "city": "Guadalajara",
        "average_rating": Decimal("4.90"),
        "color": (231, 76, 60),
        "portfolio": [
            {
                "title": "Instalación de panel solar doméstico",
                "description": "Instalación eléctrica completa para sistema fotovoltaico de 3kW. Incluye tablero de distribución y medidor bidireccional.",
            },
            {
                "title": "Automatización de iluminación",
                "description": "Instalación de sistema de iluminación inteligente con control por app en sala, cocina y recámaras.",
            },
        ],
        "orders": [
            {
                "description": "Cortocircuito en la cocina, se van los fusibles cuando se enciende el horno.",
                "status": "COMPLETED",
                "agreed_price": Decimal("1500.00"),
                "review_rating": 5,
                "review_comment": "Lucía identificó el problema en minutos. Trabajo limpio y precio justo. 100% recomendada.",
            },
            {
                "description": "Instalación de 4 contactos adicionales en la sala de trabajo.",
                "status": "COMPLETED",
                "agreed_price": Decimal("900.00"),
                "review_rating": 4,
                "review_comment": "Buen trabajo, muy puntual. Los contactos quedaron perfectamente instalados.",
            },
        ],
    },
    {
        "email": "miguel.pintor@findmyworker.com",
        "first_name": "Miguel",
        "last_name": "Torres",
        "profession": "PAINTER",
        "bio": (
            "Pintor profesional con 12 años de experiencia en pintura "
            "residencial y comercial. Especializado en acabados finos, "
            "texturizados, murales y pintura epóxica para pisos."
        ),
        "years_experience": 12,
        "hourly_rate": Decimal("280.00"),
        "city": "Monterrey",
        "average_rating": Decimal("4.70"),
        "color": (39, 174, 96),
        "portfolio": [
            {
                "title": "Remodelación de sala comedor",
                "description": "Pintura completa de sala-comedor con técnica de esponjado y acento de color en pared principal. Área de 45m².",
            },
            {
                "title": "Fachada residencial",
                "description": "Pintura exterior de casa de dos plantas. Preparación de superficie, sellador, dos manos de pintura elastomérica.",
            },
        ],
        "orders": [
            {
                "description": "Pintar dos recámaras y el pasillo, paredes y techo. Aproximadamente 60m².",
                "status": "COMPLETED",
                "agreed_price": Decimal("3500.00"),
                "review_rating": 5,
                "review_comment": "El resultado fue increíble, mejor de lo esperado. Miguel es muy detallista y dejó todo limpio al terminar.",
            },
        ],
    },
]


def _make_placeholder_image(label: str, color: tuple, size=(800, 600)) -> ContentFile:
    img = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(img)
    # Gradient-like overlay
    for i in range(size[1]):
        alpha = int(80 * (1 - i / size[1]))
        draw.line([(0, i), (size[0], i)], fill=(0, 0, 0, alpha))
    # Text
    draw.rectangle([40, size[1] - 90, size[0] - 40, size[1] - 40], fill=(0, 0, 0, 120))
    draw.text((60, size[1] - 78), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return ContentFile(buf.read())


class Command(BaseCommand):
    help = "Seed demo data for portfolio showcase"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo users and their data before seeding",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        client = self._get_or_create_client()
        for worker_data in WORKERS:
            self._create_worker(client, worker_data)

        self.stdout.write(self.style.SUCCESS(
            "\nDemo seed complete.\n"
            f"  Client login : {DEMO_CLIENT_EMAIL} / {DEMO_PASSWORD}\n"
            "  Workers      : carlos, lucia, miguel @findmyworker.com / Demo1234!\n"
        ))

    def _reset(self):
        emails = [DEMO_CLIENT_EMAIL] + [w["email"] for w in WORKERS]
        deleted, _ = User.objects.filter(email__in=emails).delete()
        self.stdout.write(f"Deleted {deleted} existing demo records.")

    def _get_or_create_client(self):
        user, created = User.objects.get_or_create(
            email=DEMO_CLIENT_EMAIL,
            defaults={
                "first_name": "Ana",
                "last_name": "González",
                "role": User.Role.CLIENT,
                "phone_number": "+52 55 1234 5678",
                "city": "Ciudad de México",
                "country": "México",
                "is_active": True,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.stdout.write(f"Created client: {user.email}")
        return user

    def _create_worker(self, client: User, data: dict):
        user, created = User.objects.get_or_create(
            email=data["email"],
            defaults={
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "role": User.Role.WORKER,
                "phone_number": "+52 33 9876 5432",
                "city": data["city"],
                "country": "México",
                "is_active": True,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()

        profile, _ = WorkerProfile.objects.get_or_create(
            user=user,
            defaults={
                "profession": data["profession"],
                "bio": data["bio"],
                "years_experience": data["years_experience"],
                "hourly_rate": data["hourly_rate"],
                "location": Point(-99.1332, 19.4326, srid=4326),
                "is_verified": True,
                "average_rating": data["average_rating"],
            },
        )

        for portfolio_data in data.get("portfolio", []):
            if not PortfolioItem.objects.filter(worker=profile, title=portfolio_data["title"]).exists():
                item = PortfolioItem(
                    worker=profile,
                    title=portfolio_data["title"],
                    description=portfolio_data["description"],
                    is_external_work=True,
                )
                img_content = _make_placeholder_image(portfolio_data["title"], data["color"])
                item.image.save(
                    f"demo_{user.first_name.lower()}_{PortfolioItem.objects.filter(worker=profile).count()}.jpg",
                    img_content,
                    save=True,
                )

        for order_data in data.get("orders", []):
            order, order_created = ServiceOrder.objects.get_or_create(
                client=client,
                worker=profile,
                description=order_data["description"],
                defaults={
                    "status": order_data["status"],
                    "agreed_price": order_data.get("agreed_price"),
                },
            )

            if order_created and order_data.get("review_rating"):
                Review.objects.get_or_create(
                    service_order=order,
                    defaults={
                        "rating": order_data["review_rating"],
                        "comment": order_data.get("review_comment", ""),
                    },
                )

            if order_created and order_data["status"] == "ACCEPTED":
                Message.objects.create(
                    service_order=order,
                    sender=client,
                    content="Hola, ¿cuándo podría venir a revisar el trabajo?",
                )
                Message.objects.create(
                    service_order=order,
                    sender=user,
                    content="Buenos días, puedo ir mañana en la mañana entre 9 y 11. ¿Le queda bien?",
                )

        self.stdout.write(f"Seeded worker: {user.email}")
