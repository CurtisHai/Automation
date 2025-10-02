from django.db import migrations


def unpublish_mp4_workflow(apps, schema_editor):
    Workflow = apps.get_model("bookings", "Workflow")
    (Workflow.objects
        .filter(name__iexact="MP4", is_published=True)
        .update(is_published=False, published_by=None, published_at=None))


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0035_rename_step_type_workflowstep_action"),
    ]

    operations = [
        migrations.RunPython(unpublish_mp4_workflow, migrations.RunPython.noop),
    ]
