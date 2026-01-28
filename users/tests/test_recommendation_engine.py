"""
Tests unitarios para el motor de recomendación (RecommendationEngine).

Cubre:
    - Preprocesamiento de texto
    - Expansión de sinónimos
    - Entrenamiento del modelo TF-IDF
    - Estrategias de ranking (tfidf, fallback, hybrid)
    - Detección de profesiones
    - Explicabilidad (XAI)
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from users.models import WorkerProfile
from users.services import RecommendationEngine
from decimal import Decimal

User = get_user_model()


class RecommendationEngineTestCase(TestCase):
    """Tests para el motor de recomendación."""
    
    def setUp(self):
        """Configuración inicial para todos los tests."""
        self.engine = RecommendationEngine()
        
        # Crear usuarios y perfiles de trabajadores de prueba
        self.workers = []
        
        # Plomero con buena bio
        user1 = User.objects.create_user(
            email='plomero@test.com',
            password='test123',
            role='WORKER'
        )
        worker1 = WorkerProfile.objects.create(
            user=user1,
            profession='PLUMBER',
            bio='Plomero profesional con 10 años de experiencia en reparación de fugas, '
                'instalación de tuberías y mantenimiento de sistemas hidráulicos. '
                'Atención de emergencias 24/7.',
            years_experience=10,
            average_rating=Decimal('4.8'),
            location=Point(-74.0721, 4.7110, srid=4326)  # Bogotá
        )
        self.workers.append(worker1)
        
        # Electricista
        user2 = User.objects.create_user(
            email='electricista@test.com',
            password='test123',
            role='WORKER'
        )
        worker2 = WorkerProfile.objects.create(
            user=user2,
            profession='ELECTRICIAN',
            bio='Electricista certificado especializado en instalaciones residenciales y comerciales. '
                'Reparación de fallas eléctricas, cableado, iluminación y sistemas de seguridad.',
            years_experience=7,
            average_rating=Decimal('4.5'),
            location=Point(-74.0821, 4.7210, srid=4326)
        )
        self.workers.append(worker2)
        
        # Pintor
        user3 = User.objects.create_user(
            email='pintor@test.com',
            password='test123',
            role='WORKER'
        )
        worker3 = WorkerProfile.objects.create(
            user=user3,
            profession='PAINTER',
            bio='Pintor profesional con experiencia en pintura interior y exterior. '
                'Trabajos de calidad con garantía. Presupuestos sin compromiso.',
            years_experience=5,
            average_rating=Decimal('4.2'),
            location=Point(-74.0921, 4.7310, srid=4326)
        )
        self.workers.append(worker3)
    
    def test_preprocess_text(self):
        """Test del preprocesamiento de texto."""
        # Test 1: Limpieza básica
        text = "Necesito un PLOMERO urgente!!!"
        processed = self.engine.preprocess_text(text)
        
        # Debe estar en minúsculas y sin signos
        self.assertNotIn('!!!', processed)
        self.assertIn('plomero', processed.lower())
        
        # Test 2: Expansión de sinónimos
        text = "plomero urgente"
        processed = self.engine.preprocess_text(text)
        
        # Debe incluir sinónimos de plomero
        self.assertTrue(
            any(syn in processed for syn in ['fontanero', 'gasfiter']),
            "Debe expandir sinónimos de 'plomero'"
        )
        
        # Test 3: Remoción de stopwords
        text = "yo necesito hacer un trabajo de plomería"
        processed = self.engine.preprocess_text(text)
        
        # Stopwords del dominio deben removerse
        self.assertNotIn('trabajo', processed)
        self.assertIn('plomería', processed)
    
    def test_expand_synonyms(self):
        """Test de la expansión de sinónimos."""
        # Test con palabra que tiene sinónimos
        text = "fuga de agua"
        expanded = self.engine.expand_synonyms(text)
        
        self.assertIn('fuga', expanded)
        self.assertTrue(
            any(syn in expanded for syn in ['goteo', 'filtración', 'derrame']),
            "Debe expandir sinónimos de 'fuga'"
        )
        
        # Test con palabra sin sinónimos
        text = "palabra sin sinónimos definidos"
        expanded = self.engine.expand_synonyms(text)
        self.assertEqual(text + ' ' + text, expanded)  # Solo duplica el original
    
    def test_train_model(self):
        """Test del entrenamiento del modelo TF-IDF."""
        # Entrenar modelo
        metrics = self.engine.train_model(force_retrain=True)
        
        # Verificar métricas
        self.assertEqual(metrics['status'], 'trained')
        self.assertEqual(metrics['workers_count'], 3)  # 3 trabajadores creados
        self.assertGreater(metrics['vocabulary_size'], 0)
        self.assertGreater(metrics['training_time_ms'], 0)
        
        # Verificar que el modelo está cargado
        self.assertIsNotNone(self.engine.vectorizer)
        self.assertIsNotNone(self.engine.tfidf_matrix)
        self.assertEqual(len(self.engine.worker_ids), 3)
    
    def test_get_recommendations_tfidf(self):
        """Test de la estrategia TF-IDF pura."""
        # Entrenar modelo
        self.engine.train_model(force_retrain=True)
        
        # Query para plomero
        results = self.engine.get_recommendations(
            query="necesito reparar fuga de agua urgente",
            strategy='tfidf',
            top_n=3
        )
        
        # Verificar resultados
        self.assertGreater(len(results), 0)
        
        # El primer resultado debe ser el plomero (mayor similitud)
        top_worker = results[0]['worker']
        self.assertEqual(top_worker.profession, 'PLUMBER')
        
        # Verificar estructura del resultado
        self.assertIn('score', results[0])
        self.assertIn('relevance_percentage', results[0])
        self.assertIn('explanation', results[0])
        
        # Score debe estar entre 0 y 1
        self.assertGreaterEqual(results[0]['score'], 0)
        self.assertLessEqual(results[0]['score'], 1)
    
    def test_get_recommendations_fallback(self):
        """Test de la estrategia fallback (geo + rating)."""
        results = self.engine.get_recommendations(
            query="plomero",
            strategy='fallback',
            top_n=3
        )
        
        # Debe retornar resultados sin modelo entrenado
        self.assertGreater(len(results), 0)
        
        # Resultados deben estar ordenados por rating
        if len(results) >= 2:
            self.assertGreaterEqual(
                results[0]['worker'].average_rating,
                results[1]['worker'].average_rating
            )
    
    def test_get_recommendations_hybrid(self):
        """Test de la estrategia híbrida."""
        self.engine.train_model(force_retrain=True)
        
        # Query con filtros geográficos
        results = self.engine.get_recommendations(
            query="plomero para reparar tubería",
            strategy='hybrid',
            top_n=3,
            filters={
                'latitude': 4.7110,
                'longitude': -74.0721,
                'max_distance_km': 20
            }
        )
        
        self.assertGreater(len(results), 0)
        
        # Verificar que tiene score breakdown
        explanation = results[0]['explanation']
        self.assertIn('score_breakdown', explanation)
        self.assertIn('tfidf_score', explanation['score_breakdown'])
        self.assertIn('rating_boost', explanation['score_breakdown'])
        self.assertIn('proximity_boost', explanation['score_breakdown'])
    
    def test_get_recommendations_with_filters(self):
        """Test de filtros aplicados a las recomendaciones."""
        self.engine.train_model(force_retrain=True)
        
        # Filtro por rating mínimo
        results = self.engine.get_recommendations(
            query="trabajador profesional",
            strategy='tfidf',
            top_n=10,
            filters={'min_rating': Decimal('4.5')}
        )
        
        # Todos los resultados deben cumplir el filtro
        for result in results:
            self.assertGreaterEqual(result['worker'].average_rating, Decimal('4.5'))
        
        # Filtro por profesión
        results = self.engine.get_recommendations(
            query="trabajador",
            strategy='tfidf',
            top_n=10,
            filters={'profession': 'ELECTRICIAN'}
        )
        
        # Todos deben ser electricistas
        for result in results:
            self.assertEqual(result['worker'].profession, 'ELECTRICIAN')
    
    def test_detect_profession(self):
        """Test de detección de profesión en el texto."""
        # Test 1: Detectar plomero
        profession = self.engine._detect_profession('necesito un plomero urgente')
        self.assertEqual(profession, 'PLUMBER')
        
        # Test 2: Detectar electricista
        profession = self.engine._detect_profession('problema eléctrico con la luz')
        self.assertEqual(profession, 'ELECTRICIAN')
        
        # Test 3: Detectar pintor
        profession = self.engine._detect_profession('quiero pintar mi casa')
        self.assertEqual(profession, 'PAINTER')
        
        # Test 4: Sin profesión clara
        profession = self.engine._detect_profession('necesito ayuda con algo')
        self.assertIsNone(profession)
    
    def test_explain_tfidf(self):
        """Test de la explicabilidad (XAI) del modelo."""
        self.engine.train_model(force_retrain=True)
        
        query = "reparar fuga de agua"
        processed_query = self.engine.preprocess_text(query)
        
        # Obtener explicación para el plomero
        worker = self.workers[0]  # Plomero
        
        # Necesitamos vectorizar y calcular similitud
        query_vector = self.engine.vectorizer.transform([processed_query])
        worker_idx = self.engine.worker_ids.index(str(worker.id))
        worker_vector = self.engine.tfidf_matrix[worker_idx]
        
        from sklearn.metrics.pairwise import cosine_similarity
        similarity = cosine_similarity(query_vector, worker_vector)[0][0]
        
        explanation = self.engine._explain_tfidf(processed_query, worker, similarity)
        
        # Verificar estructura
        self.assertIn('method', explanation)
        self.assertIn('matched_keywords', explanation)
        self.assertIn('top_bio_terms', explanation)
        self.assertIn('similarity_score', explanation)
        
        # Debe tener keywords matched
        self.assertGreater(len(explanation['matched_keywords']), 0)
    
    def test_empty_query(self):
        """Test con query vacía."""
        self.engine.train_model(force_retrain=True)
        
        # Query vacía debe retornar lista vacía
        results = self.engine.get_recommendations(
            query="",
            strategy='tfidf',
            top_n=5
        )
        
        self.assertEqual(len(results), 0)
    
    def test_query_without_results(self):
        """Test con query que no debería tener resultados relevantes."""
        self.engine.train_model(force_retrain=True)
        
        # Query sobre algo que no existe en el corpus
        results = self.engine.get_recommendations(
            query="médico cirujano especialista en neurocirugía",
            strategy='tfidf',
            top_n=5
        )
        
        # Puede retornar resultados con score muy bajo o ninguno
        # Depende del threshold implícito
        if len(results) > 0:
            self.assertLess(results[0]['score'], 0.3)  # Score muy bajo
    
    def test_invalidate_cache(self):
        """Test de invalidación de cache."""
        # Entrenar y cachear modelo
        self.engine.train_model(force_retrain=True)
        self.assertIsNotNone(self.engine.vectorizer)
        
        # Invalidar cache
        self.engine.invalidate_cache()
        
        # Modelo debe limpiarse
        self.assertIsNone(self.engine.vectorizer)
        self.assertIsNone(self.engine.tfidf_matrix)
        self.assertEqual(len(self.engine.worker_ids), 0)


class RecommendationEngineEdgeCasesTestCase(TestCase):
    """Tests de casos extremos y edge cases."""
    
    def test_model_not_trained(self):
        """Test cuando el modelo no está entrenado."""
        engine = RecommendationEngine()
        
        # Sin entrenar, debe lanzar excepción o entrenar automáticamente
        try:
            results = engine.get_recommendations(
                query="test query",
                strategy='tfidf',
                top_n=5
            )
            # Si llegó aquí, entrenó automáticamente (comportamiento esperado)
            self.assertIsNotNone(engine.vectorizer)
        except ValueError:
            # O lanza error si no hay datos (también válido)
            pass
    
    def test_single_worker(self):
        """Test con un solo trabajador en el corpus."""
        # Crear un único trabajador
        user = User.objects.create_user(
            email='solo@test.com',
            password='test123',
            role='WORKER'
        )
        WorkerProfile.objects.create(
            user=user,
            profession='PLUMBER',
            bio='Único plomero disponible en el sistema para testing.',
            years_experience=5,
            average_rating=Decimal('4.0')
        )
        
        engine = RecommendationEngine()
        engine.train_model(force_retrain=True)
        
        results = engine.get_recommendations(
            query="plomero",
            strategy='tfidf',
            top_n=5
        )
        
        # Debe retornar exactamente 1 resultado
        self.assertEqual(len(results), 1)
    
    def test_workers_without_bio(self):
        """Test con trabajadores sin biografía."""
        # Crear trabajador sin bio
        user = User.objects.create_user(
            email='sinbio@test.com',
            password='test123',
            role='WORKER'
        )
        WorkerProfile.objects.create(
            user=user,
            profession='PLUMBER',
            bio='',  # Sin bio
            years_experience=3
        )
        
        engine = RecommendationEngine()
        
        # Entrenar debe fallar o ignorar trabajadores sin bio
        try:
            metrics = engine.train_model(force_retrain=True)
            # Si entrenó, verificar que ignoró el trabajador sin bio
            self.assertEqual(metrics['workers_count'], 0)
        except ValueError as e:
            # Error esperado: no hay trabajadores con bio
            self.assertIn('biografía', str(e).lower())
