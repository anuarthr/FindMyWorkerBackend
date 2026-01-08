from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='serviceorder',
            index=models.Index(
                fields=['worker', 'status', 'updated_at'], 
                name='order_metrics_idx'
            ),
        ),
    ]
