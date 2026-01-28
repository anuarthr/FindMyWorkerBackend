"""
Management command para entrenar el modelo TF-IDF del sistema de recomendación.

Este comando:
    1. Obtiene todos los trabajadores activos con biografía
    2. Entrena el vectorizador TF-IDF con sus bios
    3. Cachea el modelo en Redis con TTL 24h
    4. Genera métricas del entrenamiento

Se debe ejecutar:
    - Inicialmente después de setup_nlp
    - Periódicamente (ej: cada noche con cron)
    - Después de agregar/actualizar muchos trabajadores

Usage:
    python manage.py train_recommendation_model
    python manage.py train_recommendation_model --force  # Forzar reentrenamiento
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.core.cache import cache
from users.services import RecommendationEngine
from users.models import WorkerProfile
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Entrena el modelo TF-IDF para el sistema de recomendación'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar reentrenamiento aunque ya exista modelo en cache',
        )
        
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validar corpus antes de entrenar',
        )
    
    def handle(self, *args, **options):
        force_retrain = options['force']
        validate_first = options['validate']
        
        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write(self.style.WARNING('Entrenamiento del Modelo de Recomendación TF-IDF'))
        self.stdout.write(self.style.WARNING('='*70))
        
        # 1. Validación opcional del corpus
        if validate_first:
            self.stdout.write('\n📊 Validando corpus...')
            self._validate_corpus()
        
        # 2. Verificar trabajadores disponibles
        self.stdout.write('\n📝 Verificando trabajadores disponibles...')
        active_workers = WorkerProfile.objects.filter(user__is_active=True)
        workers_with_bio = active_workers.exclude(bio='').exclude(bio__isnull=True)
        
        self.stdout.write(f'  Total trabajadores activos: {active_workers.count()}')
        self.stdout.write(f'  Con biografía: {workers_with_bio.count()}')
        
        if workers_with_bio.count() == 0:
            raise CommandError(
                '✗ No hay trabajadores con biografía para entrenar el modelo.\n'
                'Ejecuta: python manage.py validate_corpus --fix-empty'
            )
        
        if workers_with_bio.count() < 10:
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠ Solo {workers_with_bio.count()} trabajadores. '
                    'El modelo funcionará mejor con más datos.'
                )
            )
        
        # 3. Entrenar modelo
        self.stdout.write('\n🤖 Entrenando modelo TF-IDF...')
        
        try:
            engine = RecommendationEngine()
            metrics = engine.train_model(force_retrain=force_retrain)
            
            if metrics['status'] == 'cached':
                self.stdout.write(
                    self.style.WARNING(
                        '⚠ Modelo ya existe en cache. Usa --force para reentrenar.'
                    )
                )
                return
            
            # 4. Mostrar métricas
            self.stdout.write('\n' + '='*70)
            self.stdout.write(self.style.SUCCESS('✓ Modelo entrenado exitosamente'))
            self.stdout.write('='*70)
            
            self.stdout.write(f'  Trabajadores en corpus: {metrics["workers_count"]}')
            self.stdout.write(f'  Tamaño del vocabulario: {metrics["vocabulary_size"]} términos')
            self.stdout.write(f'  Dimensión de la matriz: {metrics["matrix_shape"]}')
            self.stdout.write(f'  Tiempo de entrenamiento: {metrics["training_time_ms"]:.2f}ms')
            
            # 5. Guardar metadata
            cache.set('recommendation_model_metadata', {
                'trained_at': timezone.now().isoformat(),
                'workers_count': metrics["workers_count"],
                'vocabulary_size': metrics["vocabulary_size"],
            }, 86400)  # 24h
            
            # 6. Test rápido del modelo
            self.stdout.write('\n🧪 Realizando test del modelo...')
            self._test_model(engine)
            
            # 7. Recomendaciones finales
            self.stdout.write('\n' + '='*70)
            self.stdout.write(self.style.SUCCESS('✓ Sistema de recomendación listo para uso'))
            self.stdout.write('='*70)
            self.stdout.write('\n📌 Endpoints disponibles:')
            self.stdout.write('  POST /api/users/workers/recommend/')
            self.stdout.write('  GET  /api/users/workers/recommendation-analytics/')
            self.stdout.write('  GET  /api/users/workers/recommendation-health/')
            
            self.stdout.write('\n📌 Próximos pasos:')
            self.stdout.write('  1. Probar endpoint: POST /api/users/workers/recommend/')
            self.stdout.write('  2. Monitorear health: GET /api/users/workers/recommendation-health/')
            self.stdout.write('  3. Configurar cron para reentrenar periódicamente (recomendado: diario)')
            
            self.stdout.write('\n' + '='*70)
            
        except ValueError as e:
            raise CommandError(f'✗ Error de validación: {e}')
        
        except Exception as e:
            logger.exception(f"Error entrenando modelo: {e}")
            raise CommandError(f'✗ Error inesperado: {e}')
    
    def _validate_corpus(self):
        """Validación rápida del corpus."""
        from django.db.models import Q
        
        MIN_BIO_LENGTH = 50
        
        active_workers = WorkerProfile.objects.filter(user__is_active=True)
        total = active_workers.count()
        
        # Bios vacías
        empty_bio = active_workers.filter(
            Q(bio='') | Q(bio__isnull=True)
        ).count()
        
        # Bios cortas
        short_bio = active_workers.exclude(
            Q(bio='') | Q(bio__isnull=True)
        ).extra(
            where=[f"LENGTH(bio) < {MIN_BIO_LENGTH}"]
        ).count()
        
        # Sin ubicación
        no_location = active_workers.filter(location__isnull=True).count()
        
        issues = []
        if empty_bio > 0:
            issues.append(f'{empty_bio} sin biografía')
        if short_bio > 0:
            issues.append(f'{short_bio} con biografía corta')
        if no_location > 0:
            issues.append(f'{no_location} sin ubicación')
        
        if issues:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Problemas encontrados: {", ".join(issues)}')
            )
            self.stdout.write(
                '  Ejecuta: python manage.py validate_corpus --detailed'
            )
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ Corpus en buen estado'))
    
    def _test_model(self, engine):
        """Realiza un test básico del modelo."""
        test_queries = [
            'plomero urgente',
            'electricista profesional',
            'pintor para casa',
        ]
        
        success_count = 0
        
        for query in test_queries:
            try:
                results = engine.get_recommendations(
                    query=query,
                    strategy='tfidf',
                    top_n=3
                )
                
                if len(results) > 0:
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ "{query}" → {len(results)} resultados'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠ "{query}" → Sin resultados (puede ser normal si no hay trabajadores de ese tipo)'
                        )
                    )
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ "{query}" → Error: {e}')
                )
        
        if success_count == len(test_queries):
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Test completado: {success_count}/{len(test_queries)} exitosos')
            )
        elif success_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠ Test parcial: {success_count}/{len(test_queries)} exitosos'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR('  ✗ Test fallido: Ninguna query funcionó correctamente')
            )
