import logging
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Q, F, Prefetch
from datetime import datetime
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from users.models import WorkerProfile
from .models import ServiceOrder, WorkHoursLog, Message, Review
from .serializers import (
    ServiceOrderSerializer,
    ServiceOrderStatusSerializer,
    WorkHoursLogSerializer,
    WorkHoursLogUpdateSerializer,
    WorkHoursApprovalSerializer,
    MessageSerializer,
    ReviewSerializer,
    ReviewCreateSerializer,
    ReviewListSerializer
)
from .permissions import (
    IsOrderParticipant, 
    CanChangeOrderStatus, 
    IsOrderClient,
    IsOrderParticipantReadOnly
)
from .pagination import ReviewPagination
from .throttles import ReviewCreateThrottle

# Configuración del logger
logger = logging.getLogger(__name__)

# Configuración del logger
logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """
    Paginación estándar para listados.
    - page_size: 20 items por página por defecto
    - max_page_size: Máximo 100 items por página
    - page_size_query_param: Permite al cliente especificar tamaño con ?page_size=N
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ServiceOrderCreateView(generics.CreateAPIView):
    """
    POST /api/orders/
    Crea una nueva orden de servicio.
    Solo usuarios autenticados pueden crear órdenes.
    """
    queryset = ServiceOrder.objects.all()
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Asigna automáticamente el cliente actual a la orden."""
        order = serializer.save(client=self.request.user)
        logger.info(
            f"Orden #{order.id} creada por {self.request.user.email} "
            f"para trabajador {order.worker.user.email}"
        )

class ServiceOrderListView(generics.ListAPIView):
    """
    GET /api/orders/?status=PENDING
    Lista las órdenes del usuario autenticado (como cliente o trabajador).
    
    Query params:
    - status: Filtrar por estado (PENDING, ACCEPTED, IN_ESCROW, COMPLETED, CANCELLED)
    - page: Número de página
    - page_size: Cantidad de items por página (max 100)
    """
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Obtiene órdenes del usuario con optimización de queries."""
        user = self.request.user
        
        # Optimizar con select_related y prefetch_related
        queryset = ServiceOrder.objects.filter(
            Q(client=user) | Q(worker__user=user)
        ).select_related(
            'client', 'worker', 'worker__user'
        ).prefetch_related(
            Prefetch(
                'work_hours',
                queryset=WorkHoursLog.objects.filter(approved_by_client=True)
            )
        )

        # Filtrar por estado si se proporciona
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())
            logger.debug(f"Usuario {user.email} filtró órdenes por estado: {status_filter}")

        return queryset.order_by('-created_at')

class ServiceOrderDetailView(generics.RetrieveAPIView):
    """
    GET /api/orders/{id}/
    Obtiene los detalles de una orden específica.
    Solo accesible por el cliente o trabajador de la orden.
    """
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]

class ServiceOrderStatusUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/orders/{id}/status/
    Actualiza el estado de una orden.
    Las transiciones de estado están controladas por permisos.
    """
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant, CanChangeOrderStatus]

    def update(self, request, *args, **kwargs):
        """Actualiza el estado y retorna la orden completa."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_status = instance.status
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        new_status = instance.status
        logger.info(
            f"Orden #{instance.id} actualizada de {old_status} a {new_status} "
            f"por {request.user.email}"
        )

        # Retornar serializador completo con todos los campos
        full_serializer = ServiceOrderSerializer(instance)
        return Response(full_serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_metrics(request):
    """
    GET /api/orders/workers/me/metrics/
    
    Devuelve métricas completas del trabajador autenticado:
    - active_jobs: Trabajos activos (ACCEPTED + IN_ESCROW)
    - monthly_earnings: Ganancias del mes basadas en horas aprobadas
    - total_earnings: Ganancias totales de órdenes completadas
    - completed_jobs: Total de trabajos completados
    - average_rating: Rating promedio del trabajador
    
    Solo accesible por usuarios con rol WORKER.
    """
    # Validar que el usuario sea un trabajador
    if request.user.role != 'WORKER':
        logger.warning(
            f"Usuario {request.user.email} con rol {request.user.role} "
            f"intentó acceder a métricas de trabajador"
        )
        return Response(
            {'detail': _('Solo trabajadores pueden acceder a estas métricas.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Obtener perfil de trabajador
    try:
        worker_profile = WorkerProfile.objects.select_related('user').get(user=request.user)
    except WorkerProfile.DoesNotExist:
        logger.error(f"Perfil de trabajador no encontrado para {request.user.email}")
        return Response(
            {'detail': _('Perfil de trabajador no encontrado.')},
            status=status.HTTP_404_NOT_FOUND
        )
    
    now = timezone.now()
    current_month = now.month
    current_year = now.year
    
    # Obtener métricas de órdenes con una sola query optimizada
    order_metrics = ServiceOrder.objects.filter(
        worker=worker_profile
    ).aggregate(
        active_jobs=Count(
            'id', 
            filter=Q(status__in=['ACCEPTED', 'IN_ESCROW'])
        ),
        total_earnings=Sum(
            'agreed_price', 
            filter=Q(status='COMPLETED')
        ),
        completed_jobs=Count(
            'id', 
            filter=Q(status='COMPLETED')
        )
    )
    
    # Calcular ganancias del mes actual
    month_logs = WorkHoursLog.objects.filter(
        service_order__worker=worker_profile,
        approved_by_client=True,
        date__month=current_month,
        date__year=current_year
    ).select_related('service_order', 'service_order__worker')
    
    monthly_earnings = sum(log.calculated_payment for log in month_logs)
    
    metrics_data = {
        'active_jobs': order_metrics['active_jobs'] or 0,
        'monthly_earnings': float(monthly_earnings),
        'total_earnings': float(order_metrics['total_earnings'] or 0),
        'completed_jobs': order_metrics['completed_jobs'] or 0,
        'average_rating': float(worker_profile.average_rating)
    }
    
    logger.info(f"Métricas generadas para trabajador {request.user.email}")
    return Response(metrics_data, status=status.HTTP_200_OK)

class WorkHoursLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar registros de horas trabajadas.
    
    Endpoints:
    - list/create: GET/POST /api/orders/{order_id}/work-hours/
    - retrieve/update/destroy: GET/PATCH/DELETE /api/orders/{order_id}/work-hours/{id}/
    - approve: POST /api/orders/{order_id}/work-hours/{id}/approve/
    
    Solo participantes de la orden pueden acceder.
    Solo el trabajador puede crear/editar horas.
    Solo el cliente puede aprobar horas.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]
    serializer_class = WorkHoursLogSerializer

    def get_queryset(self):
        """Obtiene registros de horas para una orden específica."""
        order_id = self.kwargs.get('order_pk')
        return WorkHoursLog.objects.filter(
            service_order_id=order_id
        ).select_related(
            'service_order', 'service_order__worker', 'service_order__worker__user'
        ).order_by('-date', '-created_at')

    def get_serializer_class(self):
        """Usa serializador apropiado según la acción."""
        if self.action in ['update', 'partial_update']:
            return WorkHoursLogUpdateSerializer
        return WorkHoursLogSerializer

    def perform_create(self, serializer):
        """Crea un nuevo registro de horas. Solo el trabajador puede hacerlo."""
        order_id = self.kwargs.get('order_pk')
        order = get_object_or_404(ServiceOrder, pk=order_id)
        
        # Validar que solo el trabajador pueda registrar horas
        if order.worker.user != self.request.user:
            logger.warning(
                f"Usuario {self.request.user.email} intentó registrar horas "
                f"en orden {order_id} sin ser el trabajador"
            )
            raise PermissionDenied(_("Solo el trabajador puede registrar horas."))
        
        work_log = serializer.save(service_order=order)
        logger.info(
            f"Registro de horas #{work_log.id} creado para orden {order_id} "
            f"por {self.request.user.email}: {work_log.hours}h el {work_log.date}"
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, order_pk=None, pk=None):
        """
        POST /api/orders/{order_id}/work-hours/{id}/approve/
        
        El cliente aprueba o rechaza el registro de horas.
        
        Body: {"approved": true}
        
        Cuando se aprueba, actualiza automáticamente el precio acordado de la orden.
        """
        work_log = self.get_object()
        order = work_log.service_order
        
        # Validar que solo el cliente pueda aprobar
        if order.client != request.user:
            logger.warning(
                f"Usuario {request.user.email} intentó aprobar horas "
                f"en orden {order_pk} sin ser el cliente"
            )
            return Response(
                {'detail': _('Solo el cliente puede aprobar horas.')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar datos de entrada
        serializer = WorkHoursApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data['approved']
        
        # Actualizar estado de aprobación
        work_log.approved_by_client = approved
        work_log.save(update_fields=['approved_by_client', 'updated_at'])
        
        # Si se aprobó, actualizar precio de la orden
        if approved:
            order.update_agreed_price()
            logger.info(
                f"Horas #{work_log.id} aprobadas por {request.user.email}. "
                f"Precio orden actualizado a ${order.agreed_price}"
            )
        else:
            logger.info(f"Aprobación de horas #{work_log.id} revocada por {request.user.email}")
        
        return Response({
            'id': work_log.id,
            'approved_by_client': work_log.approved_by_client,
            'calculated_payment': float(work_log.calculated_payment),
            'order_agreed_price': float(order.agreed_price) if order.agreed_price else 0,
            'message': _('Horas aprobadas exitosamente') if approved else _('Aprobación revocada')
        })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_price_summary(request, pk):
    """
    GET /api/orders/{id}/price-summary/
    
    Devuelve un resumen detallado del precio calculado de la orden:
    - Horas totales (aprobadas y pendientes)
    - Pagos calculados (aprobados y pendientes)
    - Precio acordado actual
    - Indicador si la orden puede completarse
    
    Solo accesible por el cliente o trabajador de la orden.
    """
    order = get_object_or_404(
        ServiceOrder.objects.select_related('worker'),
        pk=pk
    )
    
    # Validar permisos
    if order.client != request.user and order.worker.user != request.user:
        logger.warning(
            f"Usuario {request.user.email} intentó acceder a resumen de precio "
            f"de orden {pk} sin permisos"
        )
        return Response(
            {'detail': _('No autorizado.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Obtener registros de horas optimizado
    work_hours = order.work_hours.all()
    
    # Calcular totales
    total_hours_approved = sum(
        log.hours for log in work_hours if log.approved_by_client
    )
    total_hours_pending = sum(
        log.hours for log in work_hours if not log.approved_by_client
    )
    
    payment_approved = sum(
        log.calculated_payment for log in work_hours if log.approved_by_client
    )
    payment_pending = sum(
        log.calculated_payment for log in work_hours if not log.approved_by_client
    )
    
    summary = {
        'order_id': order.id,
        'worker_hourly_rate': float(order.worker.hourly_rate or 0),
        'total_hours_approved': float(total_hours_approved),
        'total_hours_pending': float(total_hours_pending),
        'payment_approved': float(payment_approved),
        'payment_pending': float(payment_pending),
        'agreed_price': float(order.agreed_price) if order.agreed_price else 0,
        'can_complete_order': order.can_transition_to_completed()
    }
    
    logger.debug(f"Resumen de precio generado para orden {pk}")
    return Response(summary)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrderParticipant])
def order_messages(request, pk):
    """
    GET /api/orders/{id}/messages/?limit=50
    
    Devuelve el historial de mensajes de una orden específica.
    Solo accesible por el cliente o trabajador de la orden.
    
    Query params:
    - limit: Número máximo de mensajes a retornar (default: 50, max: 200)
    
    Retorna mensajes ordenados por timestamp ascendente (más antiguos primero).
    """
    order = get_object_or_404(
        ServiceOrder.objects.select_related('client', 'worker', 'worker__user'),
        pk=pk
    )
    
    # Validar permisos
    if order.client != request.user and order.worker.user != request.user:
        logger.warning(
            f"Usuario {request.user.email} intentó acceder a mensajes "
            f"de orden {pk} sin permisos"
        )
        return Response(
            {'detail': _('No tienes permiso para acceder a este chat.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Obtener límite de mensajes desde query params
    try:
        limit = int(request.query_params.get('limit', 50))
        limit = min(max(limit, 1), 200)  # Entre 1 y 200
    except (ValueError, TypeError):
        limit = 50
    
    # Obtener mensajes optimizado con select_related
    messages = Message.objects.filter(
        service_order=order
    ).select_related('sender').order_by('timestamp')[:limit]
    
    serializer = MessageSerializer(messages, many=True)
    
    logger.debug(
        f"Recuperados {len(messages)} mensajes para orden {pk} "
        f"por {request.user.email}"
    )
    
    return Response({
        'order_id': order.id,
        'total_messages': messages.count(),
        'limit_applied': limit,
        'messages': serializer.data
    }, status=status.HTTP_200_OK)


class CreateReviewView(generics.CreateAPIView):
    """
    Crea una review para una orden completada.
    
    **Throttling**: 10 requests/hour por usuario.
    
    **Restricciones**:
    - Solo el cliente de la orden puede crear la review
    - La orden debe estar en estado COMPLETED
    - Solo se permite una review por orden (OneToOneField)
    - Rating debe estar entre 1 y 5 estrellas
    - Comentario debe tener al menos 10 caracteres
    
    **Request Body**:
    ```json
    {
        "rating": 5,
        "comment": "Excelente trabajo, muy profesional y puntual"
    }
    ```
    
    **Response 201**:
    ```json
    {
        "id": 1,
        "service_order_id": 38,
        "reviewer": {
            "id": "6",
            "first_name": "Juan",
            "last_name": "Pérez",
            "email": "cliente@example.com"
        },
        "worker": {
            "id": "4",
            "profession": "ELECTRICIAN",
            "average_rating": "4.85"
        },
        "rating": 5,
        "comment": "Excelente trabajo...",
        "created_at": "2026-01-21T18:12:44Z",
        "can_edit": true
    }
    ```
    
    **Errores**:
    - 400: Orden no completada / Review duplicada / Validación fallida
    - 403: Usuario no es el cliente de la orden
    - 404: Orden no encontrada
    - 429: Rate limit excedido (más de 10 reviews/hora)
    """
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticated, IsOrderClient]
    throttle_classes = [ReviewCreateThrottle]
    
    def get_object(self):
        """Obtiene la orden de servicio desde la URL para validar permisos."""
        order_id = self.kwargs.get('order_id')
        order = get_object_or_404(
            ServiceOrder.objects.select_related('client', 'worker', 'worker__user'),
            pk=order_id
        )
        return order
    
    def create(self, request, *args, **kwargs):
        """
        Crea la review con validaciones.
        """
        service_order = self.get_object()
        
        # Verificar permisos a nivel de objeto
        self.check_object_permissions(request, service_order)
        
        # Pasar contexto al serializador
        serializer = self.get_serializer(
            data=request.data,
            context={
                'request': request,
                'service_order': service_order
            }
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        
        logger.info(
            f"Review creada: Orden #{service_order.id}, Rating {review.rating}⭐ "
            f"por {request.user.email}"
        )
        
        # Retornar serializador completo con toda la información
        full_serializer = ReviewSerializer(review)
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_reviews(request, worker_id):
    """
    Lista paginada de reviews de un trabajador.
    
    **Permisos**: Público para cualquier usuario autenticado.
    
    **Query Parameters**:
    - page: Número de página (default: 1)
    - page_size: Reviews por página (default: 10, max: 100)
    
    **Response 200**:
    ```json
    {
        "count": 48,
        "next": "http://example.com/api/workers/4/reviews/?page=2",
        "previous": null,
        "worker": {
            "id": "4",
            "name": "María García",
            "profession": "Electricista",
            "average_rating": "4.85",
            "total_reviews": 48
        },
        "results": [
            {
                "id": 1,
                "reviewer": {
                    "first_name": "Juan",
                    "last_name": "Pérez"
                },
                "rating": 5,
                "comment": "Excelente trabajo...",
                "created_at": "2026-01-21T16:45:00Z",
                "service_order_id": 32,
                "can_edit": false
            }
        ]
    }
    ```
    
    **Errores**:
    - 404: Trabajador no encontrado
    """
    # Obtener el trabajador
    worker = get_object_or_404(
        WorkerProfile.objects.select_related('user'),
        pk=worker_id
    )
    
    # Queryset optimizado
    queryset = Review.objects.filter(
        service_order__worker=worker
    ).select_related('service_order__client').order_by('-created_at')
    
    # Aplicar paginación
    paginator = ReviewPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    # Serializar reviews
    serializer = ReviewListSerializer(page, many=True)
    
    # Preparar datos del worker para el response
    worker_data = {
        'id': str(worker.id),
        'name': f"{worker.user.first_name} {worker.user.last_name}".strip() or worker.user.email,
        'profession': worker.get_profession_display(),
        'average_rating': str(worker.average_rating),
        'total_reviews': queryset.count()
    }
    
    # Pasar worker_data al paginador via contexto
    request.parser_context = {'worker_data': worker_data}
    
    logger.debug(
        f"Recuperadas {queryset.count()} reviews del trabajador {worker_id} "
        f"por {request.user.email}"
    )
    
    # Retornar response paginado
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_reviews(request):
    """
    Lista paginada de reviews filtradas por trabajador.
    
    **Endpoint:** GET /api/reviews/?worker={worker_id}&page={page}&page_size={page_size}
    
    **Query Parameters** (requeridos):
    - worker (int): ID del WorkerProfile (no User ID)
    - page (int, opcional): Número de página (default: 1)
    - page_size (int, opcional): Items por página (default: 10, max: 100)
    
    **Response 200**:
    ```json
    {
        "count": 25,
        "next": "http://...?page=2",
        "previous": null,
        "results": [
            {
                "id": 1,
                "reviewer": {
                    "id": 3,
                    "first_name": "Juan",
                    "last_name": "Pérez"
                },
                "rating": 5,
                "comment": "Excelente trabajo, muy profesional",
                "created_at": "2026-01-20T15:30:00Z",
                "service_order_id": 42
            }
        ],
        "worker": {
            "id": 8,
            "average_rating": "4.85",
            "total_reviews": 25
        }
    }
    ```
    
    **Errores**:
    - 400: Parámetro 'worker' requerido
    - 404: Trabajador no encontrado
    """
    # Validar que el parámetro worker esté presente
    worker_id = request.query_params.get('worker')
    
    if not worker_id:
        return Response(
            {'error': "El parámetro 'worker' es requerido"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Obtener el trabajador
    worker = get_object_or_404(
        WorkerProfile.objects.select_related('user'),
        pk=worker_id
    )
    
    # Queryset optimizado - solo reviews de órdenes completadas
    queryset = Review.objects.filter(
        service_order__worker=worker,
        service_order__status='COMPLETED'
    ).select_related('service_order__client').order_by('-created_at')
    
    # Aplicar paginación
    paginator = ReviewPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    # Serializar reviews con ID del reviewer
    reviews_data = []
    for review in page:
        reviews_data.append({
            'id': review.id,
            'reviewer': {
                'id': review.reviewer.id,
                'first_name': review.reviewer.first_name,
                'last_name': review.reviewer.last_name
            },
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.isoformat(),
            'service_order_id': review.service_order.id
        })
    
    # Preparar datos del worker
    worker_data = {
        'id': worker.id,
        'average_rating': str(worker.average_rating),
        'total_reviews': queryset.count()
    }
    
    # Pasar worker_data al paginador via contexto
    request.parser_context = {'worker_data': worker_data}
    
    logger.info(
        f"Recuperadas {len(reviews_data)} reviews del worker {worker_id} "
        f"(total: {queryset.count()}) por {request.user.email}"
    )
    
    # Retornar response paginado customizado
    return Response({
        'count': paginator.page.paginator.count,
        'next': paginator.get_next_link(),
        'previous': paginator.get_previous_link(),
        'results': reviews_data,
        'worker': worker_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrderParticipantReadOnly])
def get_order_review(request, order_id):
    """
    Obtiene la review de una orden específica.
    
    **Endpoint:** GET /api/orders/{order_id}/review/
    
    **Permisos:**
    - Solo el cliente o trabajador de la orden pueden ver la review
    - La review es pública una vez creada (para participantes)
    
    **Response 200 OK** - Review existe:
    ```json
    {
        "id": 15,
        "reviewer": {
            "id": 6,
            "first_name": "Juan",
            "last_name": "Pérez"
        },
        "rating": 5,
        "comment": "Excelente trabajo, muy profesional y puntual",
        "created_at": "2026-01-22T18:30:00Z",
        "service_order_id": 42
    }
    ```
    
    **Response 404 Not Found** - No existe review para esta orden:
    ```json
    {
        "detail": "No se encontró una evaluación para esta orden."
    }
    ```
    
    **Notas:**
    - Solo existe una review por orden
    - Solo el cliente puede crear la review
    - La orden debe estar en estado COMPLETED para tener review
    - El reviewer debe ser el cliente de la orden (reviewer_id == order.client_id)
    """
    # Obtener la orden y verificar existencia
    order = get_object_or_404(
        ServiceOrder.objects.select_related('client', 'worker__user'),
        pk=order_id
    )
    
    # Verificar permisos manualmente (el decorador verifica has_permission, 
    # pero necesitamos verificar has_object_permission)
    permission = IsOrderParticipantReadOnly()
    if not permission.has_object_permission(request, None, order):
        logger.warning(
            f"Usuario {request.user.email} intentó acceder a review de orden {order_id} "
            f"sin ser participante"
        )
        return Response(
            {'detail': 'No tienes permiso para ver esta información.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Intentar obtener la review
    try:
        review = Review.objects.select_related('service_order__client').get(
            service_order=order
        )
        
        # Serializar la review
        response_data = {
            'id': review.id,
            'reviewer': {
                'id': review.reviewer.id,
                'first_name': review.reviewer.first_name,
                'last_name': review.reviewer.last_name
            },
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.isoformat(),
            'service_order_id': review.service_order.id
        }
        
        logger.info(
            f"Review #{review.id} de orden {order_id} recuperada por {request.user.email}"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Review.DoesNotExist:
        logger.info(
            f"No se encontró review para orden {order_id}. Usuario: {request.user.email}"
        )
        return Response(
            {'detail': 'No se encontró una evaluación para esta orden.'},
            status=status.HTTP_404_NOT_FOUND
        )