"""
Recommendation Response Presenter.

Handles the presentation layer for recommendation results.
Transforms ML engine output into API-friendly response format.
"""
from typing import List, Dict, Any
from decimal import Decimal


class RecommendationPresenter:
    """
    Prepares recommendation data for API responses.
    
    Responsibilities:
        - Enrich worker objects with recommendation metadata
        - Generate human-readable explanations
        - Format response structure
    """
    
    @staticmethod
    def prepare_worker_data(results: List[Dict[str, Any]]) -> tuple[List, List[str]]:
        """
        Enrich worker objects with recommendation metadata.
        
        Args:
            results: List of dicts with 'worker', 'score', 'explanation' keys
            
        Returns:
            Tuple of (enriched_workers, worker_ids)
        """
        recommendations_data = []
        worker_ids = []
        
        for result in results:
            worker = result['worker']
            worker_ids.append(str(worker.id))
            
            # Store complete recommendation data as private attribute
            worker._recommendation_data = {
                'score': result['score'],
                'relevance_percentage': result['relevance_percentage'],
                'matched_keywords': result['explanation'].get('matched_keywords', []),
                'distance_km': result['explanation'].get('distance_km'),
                'distance_factor': result['explanation'].get('distance_factor'),
                'normalized_score': result.get('normalized_score', result['score']),
            }
            
            # Add flat fields for frontend compatibility
            worker.recommendation_score = result['score']
            worker.matched_keywords = result['explanation'].get('matched_keywords', [])
            
            # Generate human-readable explanation
            worker.explanation = RecommendationPresenter._build_explanation(result)
            
            recommendations_data.append(worker)
        
        return recommendations_data, worker_ids
    
    @staticmethod
    def _build_explanation(result: Dict[str, Any]) -> str:
        """
        Build human-readable explanation from ML result.
        
        Args:
            result: Dict with 'relevance_percentage', 'explanation' keys
            
        Returns:
            String like "87% relevante - coincide con: fuga, agua - a 2.5km"
        """
        relevance_pct = result['relevance_percentage']
        keywords = result['explanation'].get('matched_keywords', [])
        distance = result['explanation'].get('distance_km')
        
        explanation_parts = []
        
        if relevance_pct > 0:
            explanation_parts.append(f"{relevance_pct:.0f}% relevante")
        
        if keywords:
            keywords_str = ', '.join(keywords[:3])  # Max 3 keywords
            explanation_parts.append(f"coincide con: {keywords_str}")
        
        if distance is not None:
            explanation_parts.append(f"a {distance:.1f}km")
        
        return " - ".join(explanation_parts) if explanation_parts else "Recomendado por filtros"
    
    @staticmethod
    def build_response(
        query: str,
        processed_query: str,
        strategy: str,
        recommendations_serialized: List[Dict],
        elapsed_ms: float,
        cache_hit: bool,
        log_id: str
    ) -> Dict[str, Any]:
        """
        Build the final API response structure.
        
        Args:
            query: Original search query
            processed_query: Preprocessed query
            strategy: Strategy used (tfidf/fallback/hybrid)
            recommendations_serialized: Serialized worker data
            elapsed_ms: Response time in milliseconds
            cache_hit: Whether result came from cache
            log_id: UUID of the recommendation log
            
        Returns:
            Complete API response dict
        """
        return {
            'query': query,
            'processed_query': processed_query,
            'strategy_used': strategy,
            'total_results': len(recommendations_serialized),
            'recommendations': recommendations_serialized,
            'performance_ms': round(elapsed_ms, 2),
            'cache_hit': cache_hit,
            'log_id': log_id,
        }
