# Generated by Django 4.1.2 on 2022-11-17 13:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('citation', models.CharField(max_length=20)),
                ('number', models.CharField(max_length=20)),
                ('item_order', models.PositiveSmallIntegerField()),
                ('body_order', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('num_elements', models.PositiveSmallIntegerField()),
                ('has_title', models.BooleanField(default=False)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='opp.item')),
            ],
        ),
        migrations.CreateModel(
            name='Paragraph',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body_order', models.PositiveSmallIntegerField()),
                ('text', models.CharField(max_length=4000)),
            ],
            options={
                'ordering': ['body_order'],
            },
        ),
        migrations.CreateModel(
            name='Table',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('has_header', models.BooleanField(default=False)),
                ('body_order', models.PositiveSmallIntegerField()),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='opp.item')),
            ],
            options={
                'ordering': ['body_order'],
            },
        ),
        migrations.CreateModel(
            name='Version',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('upload_date', models.DateField(auto_now_add=True)),
                ('source', models.CharField(max_length=30)),
                ('url', models.CharField(blank=True, max_length=300, null=True)),
                ('wordrefs_loaded', models.BooleanField(default=False)),
                ('definitions_loaded', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Word',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=50, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='WordRef',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sentence_number', models.PositiveSmallIntegerField()),
                ('word_number', models.PositiveSmallIntegerField()),
                ('char_offset', models.PositiveSmallIntegerField()),
                ('length', models.PositiveSmallIntegerField()),
                ('paragraph', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='opp.paragraph')),
                ('word', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='opp.word')),
            ],
            options={
                'ordering': ['sentence_number', 'word_number'],
            },
        ),
        migrations.CreateModel(
            name='TableCell',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row', models.PositiveSmallIntegerField()),
                ('col', models.PositiveSmallIntegerField()),
                ('table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='opp.table')),
            ],
            options={
                'ordering': ['row', 'col'],
            },
        ),
        migrations.CreateModel(
            name='Synonym',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('synonym', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='opp.word')),
                ('word', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='opp.word')),
            ],
        ),
        migrations.AddField(
            model_name='paragraph',
            name='cell',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='opp.tablecell'),
        ),
        migrations.AddField(
            model_name='paragraph',
            name='item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='opp.item'),
        ),
        migrations.AddField(
            model_name='item',
            name='version',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='opp.version'),
        ),
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(max_length=20)),
                ('char_offset', models.PositiveSmallIntegerField()),
                ('length', models.PositiveSmallIntegerField()),
                ('info', models.CharField(blank=True, max_length=20, null=True)),
                ('paragraph', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='opp.paragraph')),
            ],
            options={
                'ordering': ['char_offset'],
            },
        ),
        migrations.AddConstraint(
            model_name='wordref',
            constraint=models.UniqueConstraint(fields=('paragraph', 'word', 'sentence_number', 'word_number'), name='unique_wordref'),
        ),
        migrations.AddConstraint(
            model_name='tablecell',
            constraint=models.UniqueConstraint(fields=('table', 'row', 'col'), name='unique_table_cell'),
        ),
        migrations.AddConstraint(
            model_name='table',
            constraint=models.UniqueConstraint(fields=('item', 'body_order'), name='unique_table'),
        ),
        migrations.AddConstraint(
            model_name='synonym',
            constraint=models.UniqueConstraint(fields=('word', 'synonym'), name='unique_synonym'),
        ),
        migrations.AddConstraint(
            model_name='paragraph',
            constraint=models.UniqueConstraint(fields=('item', 'body_order'), name='unique_paragraph'),
        ),
        migrations.AddConstraint(
            model_name='item',
            constraint=models.UniqueConstraint(fields=('version', 'citation'), name='unique_item'),
        ),
    ]
