from rest_framework.throttling import UserRateThrottle


class ReviewCreateThrottle(UserRateThrottle):
    """
    Limita la creación de reviews a 10 por hora por usuario.
    Previene spam y abuse.
    """
    scope = 'reviews'
    
    def get_cache_key(self, request, view):
        """
        Cache key basado en user ID para tracking por usuario.
        """
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
