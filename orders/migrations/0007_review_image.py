from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='image',
            field=models.ImageField(
                blank=True,
                help_text='Foto opcional del trabajo realizado (máx. 5 MB)',
                null=True,
                upload_to='reviews/',
                verbose_name='Review Image',
            ),
        ),
    ]
