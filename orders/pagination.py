from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ReviewPagination(PageNumberPagination):
    """
    Paginación personalizada para reviews.
    Permite al frontend controlar page_size via query param.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100  # Máximo 100 reviews por request
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """
        Customiza el response para incluir worker info + paginación.
        """
        # Extraer worker_data del contexto (pasado desde la vista)
        worker_data = self.request.parser_context.get('worker_data', {})
        
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'worker': worker_data,
            'results': data  # Array de reviews
        })
