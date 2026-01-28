"""
Management command para validar la calidad del corpus de trabajadores.

Verifica:
    - Trabajadores sin biografía
    - Biografías muy cortas (< 50 caracteres)
    - Trabajadores sin ubicación geográfica
    - Distribución de profesiones
    - Calidad general de los datos para ML

Usage:
    python manage.py validate_corpus
    python manage.py validate_corpus --fix-empty  # Generar bios básicas
"""

from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from users.models import WorkerProfile
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Valida la calidad del corpus de trabajadores para el sistema de recomendación'
    
    MIN_BIO_LENGTH = 50  # Caracteres mínimos para una bio útil
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-empty',
            action='store_true',
            help='Genera biografías básicas para trabajadores sin bio',
        )
        
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Muestra información detallada de trabajadores con problemas',
        )
    
    def handle(self, *args, **options):
        fix_empty = options['fix_empty']
        detailed = options['detailed']
        
        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write(self.style.WARNING('Validando Corpus de Trabajadores'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))
        
        # Estadísticas generales
        total_workers = WorkerProfile.objects.count()
        active_workers = WorkerProfile.objects.filter(user__is_active=True).count()
        
        self.stdout.write(f'Total de trabajadores: {total_workers}')
        self.stdout.write(f'Trabajadores activos: {active_workers}\n')
        
        # 1. Validar biografías
        self._validate_bios(fix_empty, detailed)
        
        # 2. Validar ubicaciones
        self._validate_locations(detailed)
        
        # 3. Distribución de profesiones
        self._analyze_professions()
        
        # 4. Estadísticas de ratings
        self._analyze_ratings()
        
        # 5. Resumen de calidad
        self._quality_summary()
    
    def _validate_bios(self, fix_empty: bool, detailed: bool):
        """Valida calidad de biografías."""
        self.stdout.write(self.style.HTTP_INFO('\n📝 Validación de Biografías:'))
        self.stdout.write('-' * 70)
        
        # Trabajadores sin bio
        empty_bio = WorkerProfile.objects.filter(
            Q(bio='') | Q(bio__isnull=True),
            user__is_active=True
        )
        empty_count = empty_bio.count()
        
        # Biografías muy cortas
        short_bio = WorkerProfile.objects.filter(
            user__is_active=True
        ).exclude(
            Q(bio='') | Q(bio__isnull=True)
        ).extra(
            where=[f"LENGTH(bio) < {self.MIN_BIO_LENGTH}"]
        )
        short_count = short_bio.count()
        
        # Biografías útiles
        good_bio = WorkerProfile.objects.filter(
            user__is_active=True
        ).extra(
            where=[f"LENGTH(bio) >= {self.MIN_BIO_LENGTH}"]
        )
        good_count = good_bio.count()
        
        # Mostrar resultados
        if empty_count > 0:
            self.stdout.write(
                self.style.ERROR(f'✗ Sin biografía: {empty_count} trabajadores')
            )
            if detailed:
                for worker in empty_bio[:5]:
                    self.stdout.write(f'  - {worker.user.email} ({worker.get_profession_display()})')
        else:
            self.stdout.write(self.style.SUCCESS('✓ Todos tienen biografía'))
        
        if short_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠ Biografía corta (< {self.MIN_BIO_LENGTH} chars): {short_count} trabajadores'
                )
            )
            if detailed:
                for worker in short_bio[:5]:
                    bio_len = len(worker.bio) if worker.bio else 0
                    self.stdout.write(
                        f'  - {worker.user.email}: "{worker.bio[:40]}..." ({bio_len} chars)'
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Biografías útiles (>= {self.MIN_BIO_LENGTH} chars): {good_count} trabajadores'
            )
        )
        
        # Fix biografías vacías si se solicitó
        if fix_empty and empty_count > 0:
            self.stdout.write('\n🔧 Generando biografías básicas...')
            fixed = 0
            for worker in empty_bio:
                worker.bio = self._generate_basic_bio(worker)
                worker.save()
                fixed += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ {fixed} biografías generadas')
            )
    
    def _validate_locations(self, detailed: bool):
        """Valida ubicaciones geográficas."""
        self.stdout.write(self.style.HTTP_INFO('\n📍 Validación de Ubicaciones:'))
        self.stdout.write('-' * 70)
        
        no_location = WorkerProfile.objects.filter(
            location__isnull=True,
            user__is_active=True
        )
        no_location_count = no_location.count()
        
        with_location = WorkerProfile.objects.filter(
            location__isnull=False,
            user__is_active=True
        )
        with_location_count = with_location.count()
        
        if no_location_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠ Sin ubicación: {no_location_count} trabajadores'
                )
            )
            if detailed:
                for worker in no_location[:5]:
                    self.stdout.write(f'  - {worker.user.email}')
        else:
            self.stdout.write(self.style.SUCCESS('✓ Todos tienen ubicación'))
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Con ubicación: {with_location_count} trabajadores')
        )
    
    def _analyze_professions(self):
        """Analiza distribución de profesiones."""
        self.stdout.write(self.style.HTTP_INFO('\n👷 Distribución de Profesiones:'))
        self.stdout.write('-' * 70)
        
        professions = WorkerProfile.objects.filter(
            user__is_active=True
        ).values(
            'profession'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        for prof in professions:
            profession_name = dict(WorkerProfile.ProfessionChoices.choices).get(
                prof['profession'], prof['profession']
            )
            bar = '█' * (prof['count'] // 2)
            self.stdout.write(f'  {profession_name:20} | {bar} {prof["count"]}')
    
    def _analyze_ratings(self):
        """Analiza estadísticas de ratings."""
        self.stdout.write(self.style.HTTP_INFO('\n⭐ Estadísticas de Ratings:'))
        self.stdout.write('-' * 70)
        
        from django.db.models import Avg, Min, Max
        
        stats = WorkerProfile.objects.filter(
            user__is_active=True
        ).aggregate(
            avg=Avg('average_rating'),
            min=Min('average_rating'),
            max=Max('average_rating')
        )
        
        no_rating = WorkerProfile.objects.filter(
            average_rating=0,
            user__is_active=True
        ).count()
        
        self.stdout.write(f'  Rating promedio: {stats["avg"]:.2f}')
        self.stdout.write(f'  Rating mínimo: {stats["min"]:.2f}')
        self.stdout.write(f'  Rating máximo: {stats["max"]:.2f}')
        
        if no_rating > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Sin rating: {no_rating} trabajadores')
            )
    
    def _quality_summary(self):
        """Resumen de calidad general."""
        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.WARNING('📊 Resumen de Calidad del Corpus'))
        self.stdout.write(self.style.WARNING('='*70))
        
        active_workers = WorkerProfile.objects.filter(user__is_active=True)
        total = active_workers.count()
        
        # Trabajadores "listos para ML"
        ml_ready = active_workers.extra(
            where=[f"LENGTH(bio) >= {self.MIN_BIO_LENGTH}"]
        ).filter(
            location__isnull=False
        ).count()
        
        if total > 0:
            percentage = (ml_ready / total) * 100
            
            self.stdout.write(f'\nTrabajadores listos para ML: {ml_ready}/{total} ({percentage:.1f}%)')
            
            if percentage >= 80:
                self.stdout.write(
                    self.style.SUCCESS('✓ Corpus en excelente estado para entrenar modelo')
                )
            elif percentage >= 60:
                self.stdout.write(
                    self.style.WARNING('⚠ Corpus aceptable, pero se recomienda mejorar datos')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Corpus necesita mejoras significativas')
                )
            
            # Recomendaciones
            if ml_ready < total:
                self.stdout.write('\n📌 Recomendaciones:')
                
                needs_bio = active_workers.filter(
                    Q(bio='') | Q(bio__isnull=True)
                ).count()
                
                needs_location = active_workers.filter(
                    location__isnull=True
                ).count()
                
                if needs_bio > 0:
                    self.stdout.write(f'  - Agregar biografías a {needs_bio} trabajadores')
                    self.stdout.write('    Usa: python manage.py validate_corpus --fix-empty')
                
                if needs_location > 0:
                    self.stdout.write(f'  - Agregar ubicación a {needs_location} trabajadores')
        
        self.stdout.write('\n' + '='*70)
    
    def _generate_basic_bio(self, worker: WorkerProfile) -> str:
        """Genera una biografía básica para un trabajador."""
        profession = worker.get_profession_display()
        years = worker.years_experience
        
        bio_parts = [
            f"Profesional {profession.lower()} especializado en servicios de calidad.",
        ]
        
        if years > 0:
            bio_parts.append(f"Cuento con {years} años de experiencia en el rubro.")
        
        bio_parts.append(
            "Ofrezco atención personalizada y trabajo garantizado. "
            "Disponible para presupuestos sin compromiso."
        )
        
        return ' '.join(bio_parts)
