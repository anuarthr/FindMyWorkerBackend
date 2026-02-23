# Generated manually for feature/user-profile-management

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_portfolioitem_is_external_work_portfolioitem_order_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, verbose_name='Phone Number'),
        ),
        migrations.AddField(
            model_name='user',
            name='address',
            field=models.CharField(blank=True, max_length=255, verbose_name='Address'),
        ),
        migrations.AddField(
            model_name='user',
            name='city',
            field=models.CharField(blank=True, max_length=100, verbose_name='City'),
        ),
        migrations.AddField(
            model_name='user',
            name='state',
            field=models.CharField(blank=True, max_length=100, verbose_name='State/Province'),
        ),
        migrations.AddField(
            model_name='user',
            name='country',
            field=models.CharField(blank=True, default='México', max_length=100, verbose_name='Country'),
        ),
        migrations.AddField(
            model_name='user',
            name='postal_code',
            field=models.CharField(blank=True, max_length=10, verbose_name='Postal Code'),
        ),
    ]
