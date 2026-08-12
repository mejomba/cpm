from django.conf import settings
from django.db import models
from django.utils import timezone


class ActiveObjectsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    

class BaseModel(models.Model):
    extra = None
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    delete_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = ActiveObjectsManager()
    default_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.delete_date = timezone.now()
        self.save(update_fields=['is_deleted', 'delete_date'])

        # soft delete مربوط‌ها (اگر بخوای cascade رو شبیه‌سازی کنی)
        for related in self._meta.related_objects:
            accessor_name = related.get_accessor_name()
            related_manager = getattr(self, accessor_name, None)
            if related_manager:
                related_qs = related_manager.all()
                for obj in related_qs:
                    if hasattr(obj, 'is_deleted'):
                        obj.delete()

    def jcreated_date(self):
        return 'return jalali created date...'

    def jupdate_date(self):
        return 'return jalali update date...'
    

class BaseModelWithUser(BaseModel):
    creator_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.DO_NOTHING, related_name='%(app_label)s_creator_%(model_name)s')
    editor_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.DO_NOTHING, related_name='%(app_label)s_editor_%(model_name)s')

    class Meta:
        abstract = True

    def save(
            self,
            *args,
            force_insert=False,
            force_update=False,
            using=None,
            update_fields=None,
    ):
        if self.extra and hasattr(self.extra, 'user'):
            user = self.extra.user
            self.editor_user = user
            if not self.creator_user:
                self.creator_user = user
        super().save(*args, force_insert=force_insert, force_update=force_update, using=using,
                     update_fields=update_fields, )