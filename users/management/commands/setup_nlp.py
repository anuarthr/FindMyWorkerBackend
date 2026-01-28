"""
Management command para configurar recursos NLP necesarios para el sistema de recomendación.

Descarga:
    - Stopwords en español de NLTK
    - Tokenizador punkt para español
    - Otros recursos de procesamiento de lenguaje natural

Usage:
    python manage.py setup_nlp
"""

from django.core.management.base import BaseCommand, CommandError
import nltk
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Descarga recursos NLTK necesarios para el sistema de recomendación'
    
    # Recursos NLTK requeridos
    REQUIRED_RESOURCES = [
        ('stopwords', 'corpus/stopwords'),
        ('punkt', 'tokenizers/punkt'),
        ('wordnet', 'corpora/wordnet'),  # Para lematización (opcional)
    ]
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar descarga aunque los recursos ya existan',
        )
    
    def handle(self, *args, **options):
        force_download = options['force']
        
        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write(self.style.WARNING('Configurando recursos NLP para FindMyWorker'))
        self.stdout.write(self.style.WARNING('='*70))
        
        success_count = 0
        error_count = 0
        
        for resource_name, resource_path in self.REQUIRED_RESOURCES:
            try:
                # Verificar si ya existe (a menos que sea --force)
                if not force_download:
                    try:
                        nltk.data.find(resource_path)
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ {resource_name} ya está instalado')
                        )
                        success_count += 1
                        continue
                    except LookupError:
                        pass  # No existe, proceder con descarga
                
                # Descargar recurso
                self.stdout.write(f'Descargando {resource_name}...')
                nltk.download(resource_name, quiet=False)
                
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {resource_name} descargado exitosamente')
                )
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error descargando {resource_name}: {e}')
                )
                error_count += 1
                logger.error(f"Error descargando {resource_name}: {e}")
        
        # Verificar stopwords español específicamente
        self.stdout.write('\n' + '='*70)
        self.stdout.write('Verificando stopwords en español...')
        
        try:
            from nltk.corpus import stopwords
            spanish_stopwords = stopwords.words('spanish')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Stopwords español disponibles: {len(spanish_stopwords)} palabras'
                )
            )
            
            # Mostrar muestra
            sample = ', '.join(spanish_stopwords[:10])
            self.stdout.write(f'  Muestra: {sample}...')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error verificando stopwords: {e}')
            )
            error_count += 1
        
        # Resumen final
        self.stdout.write('\n' + '='*70)
        self.stdout.write(f'Recursos descargados: {success_count}')
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f'Errores encontrados: {error_count}')
            )
            raise CommandError('Algunos recursos no se pudieron descargar')
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ Configuración NLP completada exitosamente')
            )
            self.stdout.write('\nAhora puedes entrenar el modelo con:')
            self.stdout.write('  python manage.py train_recommendation_model')
        
        self.stdout.write('='*70)
