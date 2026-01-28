"""
Recommendation Engine para FindMyWorker - Sistema de Búsqueda Semántica Multiidioma

Implementa búsqueda semántica usando TF-IDF (Term Frequency-Inverse Document Frequency)
con estrategias híbridas para recomendación de trabajadores.
Soporta búsquedas en INGLÉS y ESPAÑOL.

Estrategias disponibles:
    - 'tfidf': Similitud coseno pura basada en contenido (baseline)
    - 'fallback': Geolocalización + Rating (sin ML, estrategia tradicional)
    - 'hybrid': Score combinado (50% tfidf + 30% rating + 20% proximidad)

Características:
    - ✅ Búsquedas multiidioma (inglés + español)
    - ✅ Stopwords personalizadas del dominio de servicios (ambos idiomas)
    - ✅ Expansión de sinónimos para mejorar recall (ambos idiomas)
    - ✅ Explicabilidad (XAI): keywords matched + score breakdown
    - ✅ Cache Redis con TTL 24h para vectores TF-IDF
    - ✅ Invalidación inteligente cuando se actualizan perfiles

Ejemplos de búsqueda:
    Inglés: "Need plumber to fix urgent leak in bathroom"
    Español: "Necesito plomero para reparar fuga urgente en baño"

Autor: FindMyWorker Team
Fecha: Enero 2026
"""

import re
import logging
import time
from typing import List, Dict, Tuple, Optional
from decimal import Decimal

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.core.cache import cache
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q
import joblib

from users.models import WorkerProfile

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Motor de recomendación semántica con TF-IDF y estrategias híbridas.
    Soporta búsquedas en INGLÉS y ESPAÑOL automáticamente.
    
    Attributes:
        cache_ttl (int): Tiempo de vida del cache en segundos (default: 24h)
        vectorizer (TfidfVectorizer): Vectorizador TF-IDF entrenado
        tfidf_matrix (np.ndarray): Matriz TF-IDF de todos los trabajadores
        worker_ids (List[str]): Lista de IDs de trabajadores en orden de la matriz
    
    Examples:
        >>> engine = RecommendationEngine()
        
        # Búsqueda en español
        >>> results = engine.get_recommendations(
        ...     query="Plomero urgente para reparar fuga",
        ...     strategy='hybrid',
        ...     top_n=5
        ... )
        
        # Búsqueda en inglés
        >>> results = engine.get_recommendations(
        ...     query="Need electrician to install solar panels",
        ...     strategy='hybrid',
        ...     top_n=5
        ... )
    """
    
    # Stopwords personalizadas del dominio (además de las NLTK estándar)
    # ESPAÑOL
    DOMAIN_STOPWORDS_ES = {
        # Genéricas del dominio
        'trabajo', 'servicio', 'experiencia', 'años', 'profesional',
        'atención', 'calidad', 'garantía', 'cliente', 'ofrezco',
        'brindo', 'realizo', 'hacer', 'ofrecer', 'brindar',
        
        # Verbos ultra-comunes
        'tengo', 'soy', 'estoy', 'puedo', 'hago',
        
        # Pronombres y artículos
        'mi', 'mis', 'yo', 'nosotros', 'nuestro', 'nuestra',
        
        # Términos de relleno
        'cuenta', 'dispone', 'además', 'también'
    }
    
    # INGLÉS
    DOMAIN_STOPWORDS_EN = {
        # Genéricas del dominio
        'work', 'service', 'experience', 'years', 'professional',
        'attention', 'quality', 'warranty', 'customer', 'client',
        'offer', 'provide', 'perform', 'doing', 'making',
        
        # Verbos ultra-comunes
        'have', 'has', 'had', 'am', 'is', 'are', 'can', 'could',
        'will', 'would', 'do', 'does', 'did', 'make', 'makes',
        
        # Pronombres y artículos
        'my', 'mine', 'our', 'ours', 'we', 'us',
        
        # Términos de relleno
        'also', 'available', 'additionally', 'furthermore'
    }
    
    # Combinar stopwords de ambos idiomas
    DOMAIN_STOPWORDS = DOMAIN_STOPWORDS_ES | DOMAIN_STOPWORDS_EN
    
    # Sinónimos para expansión de queries (mejora recall)
    # ESPAÑOL
    SYNONYMS_ES = {
        'plomero': ['fontanero', 'gasfiter', 'tubero', 'plomería', 'tuberías'],
        'electricista': ['eléctrico', 'luz', 'cableado', 'instalación eléctrica'],
        'albañil': ['construcción', 'mampostería', 'obra', 'maestro de obra'],
        'pintor': ['pintura', 'barnizado', 'decoración'],
        'carpintero': ['carpintería', 'madera', 'muebles'],
        'jardinero': ['jardinería', 'plantas', 'jardines', 'paisajismo'],
        'mecánico': ['mecánica', 'motor', 'auto', 'coche', 'vehículo'],
        
        # Tipos de problemas
        'fuga': ['goteo', 'filtración', 'derrame', 'pérdida'],
        'roto': ['quebrado', 'dañado', 'averiado', 'rompió'],
        'urgente': ['emergencia', 'rápido', 'inmediato', 'ya'],
        'reparar': ['arreglar', 'componer', 'solucionar', 'reparación'],
        
        # Lugares
        'baño': ['sanitario', 'wc', 'toilet', 'inodoro'],
        'cocina': ['cocineta', 'estufa'],
        'techo': ['tejado', 'azotea', 'cubierta'],
    }
    
    # INGLÉS
    SYNONYMS_EN = {
        'plumber': ['plumbing', 'pipes', 'pipework', 'drainage', 'waterworks'],
        'electrician': ['electrical', 'electric', 'wiring', 'power', 'electricity'],
        'mason': ['masonry', 'bricklayer', 'construction', 'builder'],
        'painter': ['painting', 'decorator', 'decoration'],
        'carpenter': ['carpentry', 'woodwork', 'joinery', 'furniture'],
        'gardener': ['gardening', 'landscaping', 'plants', 'lawn'],
        'mechanic': ['mechanical', 'auto', 'car', 'vehicle', 'engine'],
        
        # Tipos de problemas
        'leak': ['leaking', 'drip', 'seepage', 'water damage'],
        'broken': ['damaged', 'faulty', 'malfunctioning', 'not working'],
        'urgent': ['emergency', 'asap', 'immediate', 'quick', 'fast'],
        'repair': ['fix', 'fixing', 'mend', 'restore', 'service'],
        'install': ['installation', 'setup', 'mount', 'fit'],
        
        # Lugares
        'bathroom': ['toilet', 'wc', 'restroom', 'lavatory'],
        'kitchen': ['cooking area', 'galley'],
        'roof': ['roofing', 'ceiling', 'overhead'],
        'wall': ['walls', 'partition'],
        'floor': ['flooring', 'ground'],
    }
    
    # Combinar sinónimos de ambos idiomas
    SYNONYMS = {**SYNONYMS_ES, **SYNONYMS_EN}
    
    # Pesos para estrategia híbrida (deben sumar 1.0)
    HYBRID_WEIGHTS = {
        'tfidf_score': 0.5,      # 50% similitud semántica
        'rating_boost': 0.3,     # 30% rating del trabajador
        'proximity_boost': 0.2,  # 20% cercanía geográfica
    }
    
    # Configuración de TF-IDF
    TFIDF_CONFIG = {
        'ngram_range': (1, 2),      # Unigramas y bigramas
        'max_features': 1000,        # Límite de features para eficiencia
        'min_df': 1,                 # Frecuencia mínima en documentos
        'max_df': 0.8,               # Máximo 80% de documentos (evita términos ultra-comunes)
        'sublinear_tf': True,        # Escala logarítmica para TF
        'strip_accents': 'unicode',  # Remover acentos
        'lowercase': True,
    }
    
    def __init__(self, cache_ttl: int = 86400):
        """
        Inicializa el motor de recomendación.
        
        Args:
            cache_ttl: Tiempo de vida del cache en segundos (default: 24h)
        """
        self.cache_ttl = cache_ttl
        self.vectorizer = None
        self.tfidf_matrix = None
        self.worker_ids = []
        
        # Intentar cargar modelo desde cache
        self._load_from_cache()
    
    def _load_from_cache(self) -> bool:
        """
        Carga el modelo TF-IDF desde Redis cache.
        
        Returns:
            True si se cargó exitosamente, False si no existe en cache
        """
        try:
            cached_data = cache.get('recommendation_model_data')
            if cached_data:
                self.vectorizer = cached_data['vectorizer']
                self.tfidf_matrix = cached_data['tfidf_matrix']
                self.worker_ids = cached_data['worker_ids']
                logger.info("Modelo TF-IDF cargado desde cache exitosamente")
                return True
        except Exception as e:
            logger.warning(f"No se pudo cargar modelo desde cache: {e}")
        return False
    
    def _save_to_cache(self) -> None:
        """Guarda el modelo TF-IDF en Redis cache."""
        try:
            cache_data = {
                'vectorizer': self.vectorizer,
                'tfidf_matrix': self.tfidf_matrix,
                'worker_ids': self.worker_ids,
            }
            cache.set('recommendation_model_data', cache_data, self.cache_ttl)
            logger.info(f"Modelo TF-IDF guardado en cache (TTL: {self.cache_ttl}s)")
        except Exception as e:
            logger.error(f"Error al guardar modelo en cache: {e}")
    
    def expand_synonyms(self, text: str) -> str:
        """
        Expande la query con sinónimos para mejorar recall.
        
        Args:
            text: Texto original
            
        Returns:
            Texto con sinónimos agregados
            
        Examples:
            >>> engine.expand_synonyms("plomero urgente")
            "plomero urgente fontanero gasfiter emergencia rápido"
        """
        words = text.lower().split()
        expanded = [text]  # Mantener texto original
        
        for word in words:
            if word in self.SYNONYMS:
                expanded.extend(self.SYNONYMS[word])
        
        return ' '.join(expanded)
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocesa texto: limpieza, normalización y expansión de sinónimos.
        Soporta INGLÉS y ESPAÑOL.
        
        Steps:
            1. Convertir a minúsculas
            2. Remover caracteres especiales (mantiene letras en inglés y español)
            3. Expandir sinónimos (ambos idiomas)
            4. Remover stopwords personalizadas (ambos idiomas)
            5. Remover espacios múltiples
        
        Args:
            text: Texto a preprocesar (inglés o español)
            
        Returns:
            Texto limpio y normalizado
            
        Examples:
            >>> engine.preprocess_text("Need plumber ASAP")
            "need plumber asap plumbing pipes emergency quick fast"
            >>> engine.preprocess_text("Necesito plomero urgente")
            "necesito plomero urgente fontanero gasfiter emergencia rápido"
        """
        if not text:
            return ""
        
        # Convertir a minúsculas
        text = text.lower()
        
        # Remover caracteres especiales, mantener letras (inglés + español), números y espacios
        text = re.sub(r'[^a-záéíóúñü\s]', ' ', text)
        
        # Expandir sinónimos ANTES de remover stopwords (soporta ambos idiomas)
        text = self.expand_synonyms(text)
        
        # Remover stopwords personalizadas (español e inglés)
        words = text.split()
        words = [w for w in words if w not in self.DOMAIN_STOPWORDS]
        text = ' '.join(words)
        
        # Remover espacios múltiples
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def train_model(self, force_retrain: bool = False) -> Dict[str, any]:
        """
        Entrena el modelo TF-IDF con todos los trabajadores activos.
        
        Args:
            force_retrain: Si True, reentrenar aunque exista en cache
            
        Returns:
            Diccionario con métricas del entrenamiento
        """
        start_time = time.time()
        
        # Verificar si ya existe modelo en cache
        if not force_retrain and self.vectorizer is not None:
            logger.info("Modelo ya entrenado, usando cache")
            return {
                'status': 'cached',
                'workers_count': len(self.worker_ids),
                'training_time_ms': 0
            }
        
        # Obtener trabajadores con bio no vacía
        workers = WorkerProfile.objects.filter(
            user__is_active=True
        ).exclude(
            Q(bio='') | Q(bio__isnull=True)
        ).select_related('user')
        
        if workers.count() == 0:
            raise ValueError("No hay trabajadores con biografía para entrenar el modelo")
        
        # Preparar corpus
        corpus = []
        worker_ids = []
        
        for worker in workers:
            # Combinar bio + profession para contexto más rico
            profession_text = worker.get_profession_display()
            full_text = f"{worker.bio} {profession_text}"
            processed_text = self.preprocess_text(full_text)
            
            if processed_text:  # Solo agregar si quedó texto después de preprocesamiento
                corpus.append(processed_text)
                worker_ids.append(str(worker.id))
        
        if len(corpus) == 0:
            raise ValueError("Corpus vacío después de preprocesamiento")
        
        # Entrenar TF-IDF
        self.vectorizer = TfidfVectorizer(**self.TFIDF_CONFIG)
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.worker_ids = worker_ids
        
        # Guardar en cache
        self._save_to_cache()
        
        training_time = (time.time() - start_time) * 1000  # ms
        
        metrics = {
            'status': 'trained',
            'workers_count': len(worker_ids),
            'vocabulary_size': len(self.vectorizer.vocabulary_),
            'matrix_shape': self.tfidf_matrix.shape,
            'training_time_ms': round(training_time, 2)
        }
        
        logger.info(f"Modelo TF-IDF entrenado: {metrics}")
        return metrics
    
    def get_recommendations(
        self,
        query: str,
        strategy: str = 'tfidf',
        top_n: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Obtiene recomendaciones de trabajadores basadas en la query.
        
        Args:
            query: Texto de búsqueda del usuario
            strategy: Estrategia de ranking ('tfidf', 'fallback', 'hybrid')
            top_n: Número de recomendaciones a retornar
            filters: Filtros adicionales:
                - min_rating: Rating mínimo (Decimal)
                - max_distance_km: Distancia máxima en km (float)
                - latitude: Latitud del usuario (float)
                - longitude: Longitud del usuario (float)
                - profession: Filtrar por profesión específica (str)
        
        Returns:
            Lista de diccionarios con trabajadores recomendados y scores
        """
        start_time = time.time()
        filters = filters or {}
        
        # Validar que el modelo esté entrenado
        if self.vectorizer is None:
            logger.warning("Modelo no entrenado, entrenando ahora...")
            self.train_model()
        
        # Preprocesar query
        processed_query = self.preprocess_text(query)
        if not processed_query:
            logger.warning(f"Query vacía después de preprocesamiento: '{query}'")
            return []
        
        # Ejecutar estrategia correspondiente
        if strategy == 'tfidf':
            results = self._strategy_tfidf(processed_query, top_n, filters)
        elif strategy == 'fallback':
            results = self._strategy_fallback(processed_query, top_n, filters)
        elif strategy == 'hybrid':
            results = self._strategy_hybrid(processed_query, top_n, filters)
        else:
            raise ValueError(f"Estrategia no válida: {strategy}")
        
        # Agregar timing
        elapsed_ms = (time.time() - start_time) * 1000
        for result in results:
            result['query_time_ms'] = round(elapsed_ms, 2)
        
        return results
    
    def _strategy_tfidf(
        self,
        processed_query: str,
        top_n: int,
        filters: Dict
    ) -> List[Dict]:
        """
        Estrategia A: Ranking puro por similitud TF-IDF.
        """
        # Vectorizar query
        query_vector = self.vectorizer.transform([processed_query])
        
        # Calcular similitud coseno
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]
        
        # Obtener top N índices
        top_indices = similarities.argsort()[-top_n*3:][::-1]  # 3x para filtrado posterior
        
        # Obtener trabajadores
        candidate_ids = [self.worker_ids[i] for i in top_indices if similarities[i] > 0]
        workers = WorkerProfile.objects.filter(
            id__in=candidate_ids
        ).select_related('user')
        
        # Aplicar filtros
        workers = self._apply_filters(workers, filters)
        
        # Construir resultados con explicabilidad
        results = []
        for worker in workers[:top_n]:
            idx = self.worker_ids.index(str(worker.id))
            similarity = float(similarities[idx])
            
            result = {
                'worker': worker,
                'score': similarity,
                'relevance_percentage': round(similarity * 100, 1),
                'strategy': 'tfidf',
                'explanation': self._explain_tfidf(processed_query, worker, similarity)
            }
            results.append(result)
        
        return results
    
    def _strategy_fallback(
        self,
        processed_query: str,
        top_n: int,
        filters: Dict
    ) -> List[Dict]:
        """
        Estrategia B: Geolocalización + Rating (sin ML).
        """
        # Buscar por profesión mencionada en la query
        profession_filter = self._detect_profession(processed_query)
        
        workers = WorkerProfile.objects.filter(user__is_active=True)
        
        if profession_filter:
            workers = workers.filter(profession=profession_filter)
        
        # Aplicar filtros
        workers = self._apply_filters(workers, filters)
        
        # Ordenar por rating (descendente)
        workers = workers.order_by('-average_rating', '-years_experience')[:top_n]
        
        results = []
        for worker in workers:
            # Score basado en rating normalizado
            score = float(worker.average_rating) / 5.0  # Normalizar a 0-1
            
            result = {
                'worker': worker,
                'score': score,
                'relevance_percentage': round(score * 100, 1),
                'strategy': 'fallback',
                'explanation': {
                    'method': 'Geolocalización + Rating',
                    'rating': float(worker.average_rating),
                    'years_experience': worker.years_experience,
                }
            }
            results.append(result)
        
        return results
    
    def _strategy_hybrid(
        self,
        processed_query: str,
        top_n: int,
        filters: Dict
    ) -> List[Dict]:
        """
        Estrategia C: Score híbrido combinado (50% TF-IDF + 30% Rating + 20% Proximidad).
        """
        # Obtener candidatos por TF-IDF
        tfidf_results = self._strategy_tfidf(processed_query, top_n * 2, filters)
        
        # Calcular score híbrido para cada candidato
        hybrid_results = []
        
        user_location = filters.get('latitude') and filters.get('longitude')
        
        for result in tfidf_results:
            worker = result['worker']
            tfidf_score = result['score']
            
            # Componente 1: TF-IDF (ya normalizado 0-1)
            tfidf_component = tfidf_score * self.HYBRID_WEIGHTS['tfidf_score']
            
            # Componente 2: Rating normalizado
            rating_normalized = float(worker.average_rating) / 5.0
            rating_component = rating_normalized * self.HYBRID_WEIGHTS['rating_boost']
            
            # Componente 3: Proximidad (si hay geolocalización)
            proximity_component = 0
            distance_km = None
            
            if user_location and worker.location:
                user_point = Point(filters['longitude'], filters['latitude'], srid=4326)
                distance_km = worker.location.distance(user_point) * 111  # Convertir a km aprox
                
                # Normalizar distancia (inversa): cercano = 1, lejano = 0
                max_distance = filters.get('max_distance_km', 50)
                proximity_normalized = max(0, 1 - (distance_km / max_distance))
                proximity_component = proximity_normalized * self.HYBRID_WEIGHTS['proximity_boost']
            
            # Score híbrido final
            hybrid_score = tfidf_component + rating_component + proximity_component
            
            hybrid_result = {
                'worker': worker,
                'score': hybrid_score,
                'relevance_percentage': round(hybrid_score * 100, 1),
                'strategy': 'hybrid',
                'explanation': {
                    **result['explanation'],
                    'score_breakdown': {
                        'tfidf_score': round(tfidf_component, 3),
                        'rating_boost': round(rating_component, 3),
                        'proximity_boost': round(proximity_component, 3),
                        'total': round(hybrid_score, 3),
                    },
                    'distance_km': round(distance_km, 2) if distance_km else None,
                }
            }
            hybrid_results.append(hybrid_result)
        
        # Reordenar por score híbrido
        hybrid_results.sort(key=lambda x: x['score'], reverse=True)
        
        return hybrid_results[:top_n]
    
    def _explain_tfidf(
        self,
        processed_query: str,
        worker: WorkerProfile,
        similarity_score: float
    ) -> Dict:
        """
        Genera explicación de por qué se recomendó un trabajador (XAI).
        
        Returns:
            Diccionario con keywords matched y términos relevantes
        """
        # Obtener términos del vectorizador
        feature_names = self.vectorizer.get_feature_names_out()
        
        # Vectorizar query y bio del trabajador
        query_vector = self.vectorizer.transform([processed_query])
        
        worker_idx = self.worker_ids.index(str(worker.id))
        worker_vector = self.tfidf_matrix[worker_idx]
        
        # Encontrar términos con mayor peso en ambos
        query_terms = query_vector.toarray()[0]
        worker_terms = worker_vector.toarray()[0]
        
        # Keywords matched (términos presentes en ambos)
        matched_keywords = []
        for i, term in enumerate(feature_names):
            if query_terms[i] > 0 and worker_terms[i] > 0:
                matched_keywords.append({
                    'term': term,
                    'query_weight': round(float(query_terms[i]), 3),
                    'worker_weight': round(float(worker_terms[i]), 3),
                })
        
        # Ordenar por peso en query
        matched_keywords.sort(key=lambda x: x['query_weight'], reverse=True)
        
        # Top términos del trabajador (incluso si no matchearon)
        top_worker_terms = []
        worker_term_indices = worker_terms.argsort()[-10:][::-1]
        for i in worker_term_indices:
            if worker_terms[i] > 0:
                top_worker_terms.append(feature_names[i])
        
        return {
            'method': 'TF-IDF Cosine Similarity',
            'matched_keywords': [m['term'] for m in matched_keywords[:5]],
            'top_bio_terms': top_worker_terms[:5],
            'similarity_score': round(similarity_score, 3),
        }
    
    def _apply_filters(
        self,
        queryset,
        filters: Dict
    ):
        """
        Aplica filtros adicionales al queryset de trabajadores.
        """
        # Filtro por rating mínimo
        if 'min_rating' in filters:
            queryset = queryset.filter(average_rating__gte=filters['min_rating'])
        
        # Filtro por distancia geográfica
        if all(k in filters for k in ['latitude', 'longitude', 'max_distance_km']):
            user_point = Point(filters['longitude'], filters['latitude'], srid=4326)
            queryset = queryset.filter(
                location__distance_lte=(user_point, D(km=filters['max_distance_km']))
            )
        
        # Filtro por profesión
        if 'profession' in filters:
            queryset = queryset.filter(profession=filters['profession'])
        
        return queryset
    
    def _detect_profession(self, text: str) -> Optional[str]:
        """
        Detecta la profesión mencionada en el texto.
        
        Returns:
            Código de la profesión (ej: 'PLUMBER') o None
        """
        profession_keywords = {
            'PLUMBER': ['plomero', 'fontanero', 'gasfiter', 'tubería', 'fuga'],
            'ELECTRICIAN': ['electricista', 'luz', 'electricidad', 'cableado'],
            'MASON': ['albañil', 'construcción', 'mampostería', 'obra'],
            'PAINTER': ['pintor', 'pintura', 'barniz'],
            'CARPENTER': ['carpintero', 'carpintería', 'madera', 'mueble'],
        }
        
        text_lower = text.lower()
        
        for profession, keywords in profession_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return profession
        
        return None
    
    def invalidate_cache(self) -> None:
        """
        Invalida el cache del modelo (llamar cuando se actualizan perfiles).
        """
        cache.delete('recommendation_model_data')
        self.vectorizer = None
        self.tfidf_matrix = None
        self.worker_ids = []
        logger.info("Cache del modelo TF-IDF invalidado")
