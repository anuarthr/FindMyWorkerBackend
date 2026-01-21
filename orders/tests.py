from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch
from decimal import Decimal
from .models import ServiceOrder, Review
from users.models import WorkerProfile

User = get_user_model()


class ReviewSignalTestCase(TestCase):
    """Tests unitarios para los signals de Review"""
    
    def setUp(self):
        """Setup común para todos los tests"""
        # Crear cliente
        self.client_user = User.objects.create_user(
            email='cliente_test@test.com',
            password='password123',
            role='CLIENT',
            first_name='Cliente',
            last_name='Test'
        )
        
        # Crear worker
        self.worker_user = User.objects.create_user(
            email='worker_test@test.com',
            password='password123',
            role='WORKER',
            first_name='Worker',
            last_name='Test'
        )
        
        # Obtener worker profile auto-creado por signal y actualizarlo
        self.worker_profile = WorkerProfile.objects.get(user=self.worker_user)
        self.worker_profile.profession = 'ELECTRICIAN'
        self.worker_profile.hourly_rate = Decimal('50000.00')
        self.worker_profile.is_verified = True
        self.worker_profile.save()
    
    def _create_completed_order(self):
        """Helper para crear una orden completada"""
        order = ServiceOrder.objects.create(
            client=self.client_user,
            worker=self.worker_profile,
            description='Test order',
            status='COMPLETED',
            agreed_price=Decimal('100000.00')
        )
        return order
    
    @patch('orders.signals.logger')
    def test_signal_recalculates_rating_on_first_review(self, mock_logger):
        """✅ Signal calcula rating correctamente con la primera review"""
        order = self._create_completed_order()
        
        # Worker inicia con rating 0.00
        self.assertEqual(self.worker_profile.average_rating, Decimal('0.00'))
        
        # Crear primera review (rating=5)
        Review.objects.create(
            service_order=order,
            rating=5,
            comment='Excelente trabajo de electricidad'
        )
        
        # Verificar que el rating se actualizó
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('5.00'))
        
        # Verificar que el logger se llamó
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        self.assertIn('rating actualizado', call_args)
    
    @patch('orders.signals.logger')
    def test_signal_recalculates_average_with_multiple_reviews(self, mock_logger):
        """✅ Signal calcula promedio correctamente con múltiples reviews"""
        # Crear primera review (rating=5)
        order1 = self._create_completed_order()
        Review.objects.create(
            service_order=order1,
            rating=5,
            comment='Excelente trabajo'
        )
        
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('5.00'))
        
        # Crear segunda review (rating=3)
        order2 = self._create_completed_order()
        Review.objects.create(
            service_order=order2,
            rating=3,
            comment='Trabajo regular'
        )
        
        # Verificar promedio: (5+3)/2 = 4.00
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('4.00'))
        
        # Crear tercera review (rating=4)
        order3 = self._create_completed_order()
        Review.objects.create(
            service_order=order3,
            rating=4,
            comment='Buen trabajo'
        )
        
        # Verificar promedio: (5+3+4)/3 = 4.00
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('4.00'))
        
        # Verificar que el logger se llamó 3 veces
        self.assertEqual(mock_logger.info.call_count, 3)
    
    def test_signal_does_not_trigger_on_review_update(self):
        """❌ Signal NO debe recalcular en update (solo en create)"""
        order = self._create_completed_order()
        
        # Crear review inicial
        review = Review.objects.create(
            service_order=order,
            rating=5,
            comment='Excelente trabajo'
        )
        
        self.worker_profile.refresh_from_db()
        initial_rating = self.worker_profile.average_rating
        self.assertEqual(initial_rating, Decimal('5.00'))
        
        # Intentar actualizar rating de la review
        # Nota: Esto no debería ser posible en producción por validaciones,
        # pero lo probamos para asegurar que el signal no se dispara
        review.comment = 'Comentario actualizado'
        review.save()
        
        # El rating NO debe cambiar
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, initial_rating)
    
    @patch('orders.signals.logger')
    def test_signal_recalculates_on_review_deletion(self, mock_logger):
        """✅ Signal recalcula rating cuando se elimina una review"""
        # Crear 3 reviews
        order1 = self._create_completed_order()
        review1 = Review.objects.create(
            service_order=order1,
            rating=5,
            comment='Excelente trabajo'
        )
        
        order2 = self._create_completed_order()
        review2 = Review.objects.create(
            service_order=order2,
            rating=3,
            comment='Trabajo regular'
        )
        
        order3 = self._create_completed_order()
        review3 = Review.objects.create(
            service_order=order3,
            rating=4,
            comment='Buen trabajo'
        )
        
        # Promedio actual: (5+3+4)/3 = 4.00
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('4.00'))
        
        # Eliminar review de rating=3
        review2.delete()
        
        # Nuevo promedio: (5+4)/2 = 4.50
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('4.50'))
        
        # Verificar que el logger se llamó (3 creates + 1 delete)
        self.assertEqual(mock_logger.info.call_count, 4)
    
    @patch('orders.signals.logger')
    def test_signal_resets_to_zero_when_all_reviews_deleted(self, mock_logger):
        """✅ Signal resetea rating a 0.00 cuando se eliminan todas las reviews"""
        order = self._create_completed_order()
        review = Review.objects.create(
            service_order=order,
            rating=5,
            comment='Excelente trabajo'
        )
        
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('5.00'))
        
        # Eliminar la única review
        review.delete()
        
        # Rating debe volver a 0.00
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('0.00'))
        
        # Verificar log
        delete_log = mock_logger.info.call_args_list[-1][0][0]
        self.assertIn('rating recalculado tras eliminar review', delete_log)
        self.assertIn('0.0', delete_log)
    
    def test_signal_handles_cascade_deletion(self):
        """✅ Signal maneja correctamente eliminación en cascada de orden"""
        # Crear orden con review
        order = self._create_completed_order()
        Review.objects.create(
            service_order=order,
            rating=5,
            comment='Excelente trabajo'
        )
        
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('5.00'))
        
        # Eliminar la orden (cascada elimina la review)
        order.delete()
        
        # Rating debe volver a 0.00 por el signal post_delete
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.average_rating, Decimal('0.00'))


class ReviewModelTestCase(TestCase):
    """Tests unitarios para el modelo Review"""
    
    def setUp(self):
        """Setup común para todos los tests"""
        self.client_user = User.objects.create_user(
            email='cliente@test.com',
            password='password123',
            role='CLIENT'
        )
        
        self.worker_user = User.objects.create_user(
            email='worker@test.com',
            password='password123',
            role='WORKER'
        )
        
        # Obtener worker profile auto-creado por signal y actualizarlo
        self.worker_profile = WorkerProfile.objects.get(user=self.worker_user)
        self.worker_profile.profession = 'PLUMBER'
        self.worker_profile.hourly_rate = Decimal('40000.00')
        self.worker_profile.is_verified = True
        self.worker_profile.save()
        
        self.order = ServiceOrder.objects.create(
            client=self.client_user,
            worker=self.worker_profile,
            description='Test order',
            status='COMPLETED',
            agreed_price=Decimal('80000.00')
        )
    
    def test_review_properties(self):
        """✅ Propiedades reviewer y worker funcionan correctamente"""
        review = Review.objects.create(
            service_order=self.order,
            rating=4,
            comment='Buen trabajo de plomería'
        )
        
        # Verificar reviewer
        self.assertEqual(review.reviewer, self.client_user)
        
        # Verificar worker
        self.assertEqual(review.worker, self.worker_profile)
    
    def test_can_edit_property_within_seven_days(self):
        """✅ can_edit retorna True dentro de los 7 días"""
        review = Review.objects.create(
            service_order=self.order,
            rating=4,
            comment='Buen trabajo'
        )
        
        # Recién creada, debe ser editable
        self.assertTrue(review.can_edit)
    
    def test_string_representation(self):
        """✅ __str__ retorna formato esperado"""
        review = Review.objects.create(
            service_order=self.order,
            rating=5,
            comment='Excelente trabajo'
        )
        
        expected = f"Review 5⭐ - Orden #{self.order.id}"
        self.assertEqual(str(review), expected)
